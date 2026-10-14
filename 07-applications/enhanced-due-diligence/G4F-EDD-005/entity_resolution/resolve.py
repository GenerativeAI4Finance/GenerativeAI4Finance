"""Candidate generation and pair scoring for company records.

Nothing here decides that two records are the same company. The output is a
list of scored candidate pairs with the evidence behind each score, for an
analyst to confirm or reject.
"""

import json
from dataclasses import asdict, dataclass, field
from itertools import combinations
from pathlib import Path

from rapidfuzz import fuzz

from .normalize import LEGAL_FAMILIES, normalize_identifier, normalize_name

LIKELY_MATCH = "likely match"
NEEDS_REVIEW = "needs review"
NO_MATCH = "no match"

# Tokens too common in company names to be useful as blocking keys.
GENERIC_TOKENS = {
    "agro",
    "brothers",
    "enterprises",
    "exports",
    "global",
    "group",
    "holdings",
    "india",
    "industries",
    "international",
    "logistics",
    "manufacturing",
    "services",
    "solutions",
    "sri",
    "technologies",
    "traders",
    "trading",
}


@dataclass
class Record:
    record_id: str
    name: str
    source: str = ""
    aliases: list[str] = field(default_factory=list)
    registration_id: str | None = None
    jurisdiction: str | None = None
    city: str | None = None


@dataclass
class MatchConfig:
    likely_match: float = 80.0
    needs_review: float = 55.0
    name_weight: float = 0.65
    id_match_bonus: float = 25.0
    jurisdiction_match_bonus: float = 10.0
    jurisdiction_mismatch_penalty: float = 15.0
    city_match_bonus: float = 5.0
    legal_form_mismatch_penalty: float = 5.0
    # Score ceiling when both records carry different registration IDs in
    # the same jurisdiction. Kept below needs_review so it acts as a veto.
    id_conflict_cap: float = 30.0
    max_block_size: int = 50

    def __post_init__(self):
        if not 0 <= self.needs_review <= self.likely_match <= 100:
            raise ValueError(
                "thresholds must satisfy 0 <= needs_review <= likely_match <= 100"
            )

    @classmethod
    def from_file(cls, path: str | Path) -> "MatchConfig":
        return cls(**json.loads(Path(path).read_text()))


@dataclass
class MatchResult:
    left_id: str
    right_id: str
    score: float
    label: str
    evidence: dict
    status: str = "unconfirmed"

    def to_dict(self) -> dict:
        return asdict(self)


def load_records(path: str | Path) -> list[Record]:
    data = json.loads(Path(path).read_text())
    return [Record(**row) for row in data["records"]]


def _name_variants(record: Record) -> list[tuple[str, bool]]:
    return [(record.name, False)] + [(a, True) for a in record.aliases]


def _blocking_keys(record: Record) -> set[str]:
    keys = set()
    reg = normalize_identifier(record.registration_id)
    if reg:
        keys.add(f"id:{reg}")
    for name, _ in _name_variants(record):
        for token in normalize_name(name).tokens:
            if token not in GENERIC_TOKENS and len(token) > 1:
                keys.add(f"tok:{token}")
    return keys


def generate_candidates(
    records: list[Record], config: MatchConfig | None = None
) -> list[tuple[Record, Record]]:
    """Return record pairs that share at least one blocking key.

    This step only narrows down what gets scored. Pairs with no shared
    identifier or distinctive name token are never compared, so a match that
    only differs in every token (for example a full rename) will be missed.
    """
    config = config or MatchConfig()
    blocks: dict[str, list[int]] = {}
    for i, record in enumerate(records):
        for key in _blocking_keys(record):
            blocks.setdefault(key, []).append(i)

    pairs = set()
    for members in blocks.values():
        if len(members) > config.max_block_size:
            continue
        pairs.update(combinations(members, 2))
    return [(records[i], records[j]) for i, j in sorted(pairs)]


def _best_name_score(left: Record, right: Record) -> dict:
    best = {"score": -1.0}
    for lname, l_alias in _name_variants(left):
        ln = normalize_name(lname)
        for rname, r_alias in _name_variants(right):
            rn = normalize_name(rname)
            score = (
                fuzz.token_sort_ratio(ln.core, rn.core) if ln.core and rn.core else 0.0
            )
            if score > best["score"]:
                best = {
                    "score": round(score, 1),
                    "left": lname,
                    "right": rname,
                    "left_normalized": ln.core,
                    "right_normalized": rn.core,
                    "alias_used": l_alias or r_alias,
                }
    return best


def _legal_family(name: str) -> str | None:
    form = normalize_name(name).legal_form
    return LEGAL_FAMILIES.get(form) if form else None


def _label(score: float, config: MatchConfig) -> str:
    if score >= config.likely_match:
        return LIKELY_MATCH
    if score >= config.needs_review:
        return NEEDS_REVIEW
    return NO_MATCH


def score_pair(
    left: Record, right: Record, config: MatchConfig | None = None
) -> MatchResult:
    config = config or MatchConfig()
    notes = []

    name = _best_name_score(left, right)
    score = name["score"] * config.name_weight
    notes.append(
        f"name similarity {name['score']} ({name['left_normalized']!r} vs {name['right_normalized']!r})"
    )
    if name["alias_used"]:
        notes.append(
            f"best name match uses an alias: {name['left']!r} / {name['right']!r}"
        )

    same_jurisdiction = None
    if left.jurisdiction and right.jurisdiction:
        same_jurisdiction = left.jurisdiction.upper() == right.jurisdiction.upper()
        if same_jurisdiction:
            score += config.jurisdiction_match_bonus
            notes.append(f"same jurisdiction ({left.jurisdiction})")
        else:
            score -= config.jurisdiction_mismatch_penalty
            notes.append(
                f"different jurisdictions ({left.jurisdiction} vs {right.jurisdiction})"
            )

    left_reg = normalize_identifier(left.registration_id)
    right_reg = normalize_identifier(right.registration_id)
    id_status = "not comparable"
    if left_reg and right_reg and same_jurisdiction:
        id_status = "match" if left_reg == right_reg else "conflict"
    elif not (left_reg and right_reg):
        id_status = "missing"

    if id_status == "match":
        score += config.id_match_bonus
        notes.append(f"registration ID matches ({left.registration_id})")
    elif id_status == "conflict":
        notes.append(
            f"registration IDs conflict ({left.registration_id} vs {right.registration_id}), "
            f"score capped at {config.id_conflict_cap}"
        )
    elif id_status == "missing":
        notes.append("registration ID missing on at least one record")
    else:
        notes.append(
            "registration IDs not compared (jurisdictions differ or are unknown)"
        )

    if left.city and right.city and left.city.lower() == right.city.lower():
        score += config.city_match_bonus
        notes.append(f"same city ({left.city})")

    left_family, right_family = _legal_family(left.name), _legal_family(right.name)
    if left_family and right_family and left_family != right_family:
        score -= config.legal_form_mismatch_penalty
        notes.append(f"legal forms differ ({left_family} vs {right_family})")

    if id_status == "conflict":
        score = min(score, config.id_conflict_cap)
    score = round(max(0.0, min(100.0, score)), 1)

    evidence = {
        "name": name,
        "registration_id": id_status,
        "same_jurisdiction": same_jurisdiction,
        "notes": notes,
    }
    return MatchResult(
        left.record_id, right.record_id, score, _label(score, config), evidence
    )


def resolve(
    records: list[Record], config: MatchConfig | None = None
) -> list[MatchResult]:
    config = config or MatchConfig()
    results = [
        score_pair(a, b, config) for a, b in generate_candidates(records, config)
    ]
    return sorted(results, key=lambda r: (-r.score, r.left_id, r.right_id))


def record_decision(
    result: MatchResult, reviewer: str, accepted: bool, note: str = ""
) -> dict:
    """Build the review record for an analyst's decision on a candidate pair.

    The score and label are kept alongside the decision so a later reviewer
    can see what the analyst was shown.
    """
    if not reviewer:
        raise ValueError("a reviewer is required to confirm or reject a match")
    return {
        "left_id": result.left_id,
        "right_id": result.right_id,
        "score": result.score,
        "label": result.label,
        "status": "confirmed" if accepted else "rejected",
        "reviewer": reviewer,
        "note": note,
    }
