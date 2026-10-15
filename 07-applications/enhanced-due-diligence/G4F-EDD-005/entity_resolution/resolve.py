"""Candidate generation and pair scoring for company records.

Nothing here decides that two records are the same company. The output is a
list of scored candidate pairs with the evidence behind each score, for an
analyst to confirm or reject.
"""

import difflib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from functools import cached_property
from itertools import combinations
from pathlib import Path
from types import MappingProxyType

from rapidfuzz import fuzz

from .normalize import (
    LEGAL_FAMILIES,
    NormalizedName,
    normalize_city,
    normalize_identifier,
    normalize_jurisdiction,
    normalize_name,
    normalize_scheme,
)

LIKELY_MATCH = "likely match"
NEEDS_REVIEW = "needs review"
NO_MATCH = "no match"
UNCONFIRMED = "unconfirmed"


class InputError(ValueError):
    """Invalid records, config or arguments, with a message saying what to fix."""


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


def _number(name: str, value, low: float, high: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"config {name} must be a number, got {value!r}")
    if not low <= value <= high:
        raise InputError(f"config {name} must be between {low} and {high}, got {value}")


@dataclass(frozen=True)
class MatchConfig:
    """Thresholds, weights and limits. Frozen so a checked config stays checked."""

    # Score at or above which a pair is a likely match, and at or above which
    # it needs review. Everything lower is "no match".
    likely_match: float = 80.0
    needs_review: float = 55.0
    name_weight: float = 0.65
    id_match_bonus: float = 25.0
    jurisdiction_match_bonus: float = 10.0
    jurisdiction_mismatch_penalty: float = 15.0
    city_match_bonus: float = 5.0
    legal_form_mismatch_penalty: float = 5.0
    # Score ceiling when both records carry different registration IDs from
    # the same scheme. Must be below needs_review so it acts as a veto, unless
    # allow_id_conflict_review is set.
    id_conflict_cap: float = 30.0
    # Opt-out for the rule above: allows id_conflict_cap to reach needs_review
    # or higher, so a conflicting pair can still be queued for review.
    allow_id_conflict_review: bool = False
    # Score ceiling for pairs without a matching registration ID, so name,
    # city and jurisdiction alone never make a likely match. None means just
    # under likely_match. If set, it must be at least needs_review and below
    # likely_match.
    no_id_cap: float | None = None
    # Names where less than this share of the characters survived
    # normalisation are not trusted enough for a likely match.
    min_name_coverage: float = 0.5
    # Largest name-token block that is compared. Larger blocks are skipped and
    # reported, never dropped silently.
    max_block_size: int = 50
    # Same for blocks of records sharing a registration ID. IDs are strong
    # evidence, so the default is much higher.
    max_id_block_size: int = 1000

    def __post_init__(self):
        for name in (
            "likely_match",
            "needs_review",
            "id_match_bonus",
            "jurisdiction_match_bonus",
            "jurisdiction_mismatch_penalty",
            "city_match_bonus",
            "legal_form_mismatch_penalty",
            "id_conflict_cap",
        ):
            _number(name, getattr(self, name), 0, 100)
        _number("name_weight", self.name_weight, 0, 1)
        _number("min_name_coverage", self.min_name_coverage, 0, 1)
        if self.no_id_cap is not None:
            _number("no_id_cap", self.no_id_cap, 0, 100)
        for name in ("max_block_size", "max_id_block_size"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 2:
                raise InputError(f"config {name} must be an integer of at least 2")
        if not isinstance(self.allow_id_conflict_review, bool):
            raise InputError("config allow_id_conflict_review must be true or false")

        if not self.needs_review < self.likely_match:
            raise InputError(
                "thresholds must satisfy 0 <= needs_review < likely_match <= 100"
            )
        if self.id_conflict_cap >= self.needs_review and not (
            self.allow_id_conflict_review
        ):
            raise InputError(
                f"id_conflict_cap ({self.id_conflict_cap}) must be below needs_review "
                f"({self.needs_review}) so a registration ID conflict rules a pair out; "
                "set allow_id_conflict_review to allow conflicting pairs into review"
            )
        if self.no_id_cap is not None and not (
            self.needs_review <= self.no_id_cap < self.likely_match
        ):
            raise InputError(
                f"no_id_cap ({self.no_id_cap}) must be at least needs_review "
                f"({self.needs_review}) and below likely_match ({self.likely_match})"
            )

    @property
    def review_ceiling(self) -> float:
        """Highest score a pair can have and still go to a human, not auto-match."""
        return max(self.needs_review, round(self.likely_match - 0.1, 4))

    @property
    def effective_no_id_cap(self) -> float:
        return self.review_ceiling if self.no_id_cap is None else self.no_id_cap

    @classmethod
    def from_file(cls, path: str | Path) -> "MatchConfig":
        data = _read_json(path)
        if not isinstance(data, dict):
            raise InputError(f"{path}: config must be a JSON object")
        known = [f.name for f in fields(cls)]
        for key in data:
            if key not in known:
                hint = difflib.get_close_matches(key, known, n=1)
                suggestion = f" (did you mean {hint[0]!r}?)" if hint else ""
                raise InputError(
                    f"{path}: unknown config key {key!r}{suggestion}; "
                    f"valid keys: {', '.join(known)}"
                )
        return cls(**data)


@dataclass(frozen=True)
class _Variant:
    text: str
    norm: NormalizedName
    is_alias: bool


@dataclass(frozen=True)
class Record:
    record_id: str
    name: str
    source: str = ""
    aliases: tuple[str, ...] = ()
    registration_id: str | None = None
    jurisdiction: str | None = None
    city: str | None = None
    # Which registry or scheme registration_id comes from, for example
    # "companies house" or "CIN". Two different IDs only count as a conflict
    # when both records name the same scheme.
    id_scheme: str | None = None

    def __post_init__(self):
        if not isinstance(self.record_id, str) or not self.record_id.strip():
            raise InputError(
                f"record_id must be a non-empty string, got {self.record_id!r}"
            )
        label = f"record {self.record_id!r}"
        self._check_text(label, "name", self.name, required=True)
        for key in ("source", "registration_id", "jurisdiction", "city", "id_scheme"):
            self._check_text(label, key, getattr(self, key))
        if self.source is None:
            object.__setattr__(self, "source", "")

        aliases = self.aliases
        if aliases is None:
            aliases = ()
        if isinstance(aliases, (str, bytes)) or not isinstance(aliases, (list, tuple)):
            raise InputError(
                f"{label}: aliases must be a list of strings, got {type(aliases).__name__}"
            )
        for alias in aliases:
            self._check_text(label, "alias", alias, required=True)
        object.__setattr__(self, "aliases", tuple(aliases))
        for variant in self._variants:
            if not any(char.isalnum() for char in variant.norm.core):
                raise InputError(
                    f"{label}: name {variant.text!r} has no letters or digits"
                )

    @staticmethod
    def _check_text(label, key, value, required=False):
        if value is None:
            if required:
                raise InputError(f"{label}: {key} is required")
            return
        if not isinstance(value, str):
            raise InputError(
                f"{label}: {key} must be a string, got {type(value).__name__}"
            )
        if required and not value.strip():
            raise InputError(f"{label}: {key} must not be blank")

    # Normalised forms are computed once per record, not once per pair.

    @cached_property
    def _variants(self) -> tuple[_Variant, ...]:
        names = [(self.name, False)] + [(a, True) for a in self.aliases]
        return tuple(
            _Variant(text, normalize_name(text), alias) for text, alias in names
        )

    @cached_property
    def _id_key(self) -> str | None:
        return normalize_identifier(self.registration_id)

    @cached_property
    def _scheme_key(self) -> str | None:
        return normalize_scheme(self.id_scheme)

    @cached_property
    def _jurisdiction_key(self) -> str | None:
        return normalize_jurisdiction(self.jurisdiction)

    @cached_property
    def _city_key(self) -> str | None:
        return normalize_city(self.city)

    @cached_property
    def _blocking_tokens(self) -> frozenset[str]:
        return frozenset(
            token
            for variant in self._variants
            for token in variant.norm.tokens
            if token not in GENERIC_TOKENS and len(token) > 1
        )


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    return value


def _plain(value):
    if isinstance(value, Mapping):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


@dataclass(frozen=True)
class MatchResult:
    """A scored candidate pair. Immutable, and never confirmed by the matcher.

    Confirming or rejecting a pair is a separate act, recorded by
    `record_decision`. The result itself always reads as unconfirmed.
    """

    left_id: str
    right_id: str
    score: float
    label: str
    evidence: Mapping

    @property
    def status(self) -> str:
        return UNCONFIRMED

    def to_dict(self) -> dict:
        return {
            "left_id": self.left_id,
            "right_id": self.right_id,
            "score": self.score,
            "label": self.label,
            "evidence": _plain(self.evidence),
            "status": self.status,
        }


@dataclass(frozen=True)
class SkippedBlock:
    """A block of records that was too large to compare exhaustively."""

    kind: str
    key: str
    size: int
    limit: int
    omitted_pairs: int | None = None

    @property
    def pairs_not_compared(self) -> int:
        if self.omitted_pairs is not None:
            return self.omitted_pairs
        return self.size * (self.size - 1) // 2

    def describe(self) -> str:
        return (
            f"{self.kind} block {self.key!r} has {self.size} records "
            f"(limit {self.limit}); up to {self.pairs_not_compared} pairs from it "
            "were not compared"
        )

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "key": self.key,
            "size": self.size,
            "limit": self.limit,
            "pairs_not_compared": self.pairs_not_compared,
        }


@dataclass(frozen=True)
class Candidates:
    pairs: list[tuple[Record, Record]] = field(default_factory=list)
    skipped_blocks: list[SkippedBlock] = field(default_factory=list)


@dataclass(frozen=True)
class Resolution:
    matches: list[MatchResult]
    skipped_blocks: list[SkippedBlock]

    def to_dict(self) -> dict:
        return {
            "matches": [m.to_dict() for m in self.matches],
            "skipped_blocks": [b.to_dict() for b in self.skipped_blocks],
        }


def _read_json(path: str | Path):
    try:
        text = Path(path).read_text(encoding="utf-8")
        return json.loads(text.removeprefix("﻿"))
    except json.JSONDecodeError as exc:
        raise InputError(f"{path}: not valid JSON ({exc})") from exc
    except UnicodeDecodeError as exc:
        raise InputError(f"{path}: not valid UTF-8 ({exc})") from exc


def load_records(path: str | Path) -> list[Record]:
    data = _read_json(path)
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        raise InputError(f"{path}: expected a JSON object with a 'records' list")
    known = [f.name for f in fields(Record)]
    records = []
    for index, row in enumerate(data["records"]):
        if not isinstance(row, dict):
            raise InputError(f"{path}: record #{index + 1} must be a JSON object")
        label = f"record {row.get('record_id', f'#{index + 1}')!r}"
        unknown = [key for key in row if key not in known]
        if unknown:
            raise InputError(
                f"{path}: {label} has unknown field(s) {', '.join(map(repr, unknown))}; "
                f"valid fields: {', '.join(known)}"
            )
        missing = [key for key in ("record_id", "name") if key not in row]
        if missing:
            raise InputError(f"{path}: {label} is missing {', '.join(missing)}")
        try:
            records.append(Record(**row))
        except InputError as exc:
            raise InputError(f"{path}: {exc}") from exc
    try:
        _check_unique(records)
    except InputError as exc:
        raise InputError(f"{path}: {exc}") from exc
    return records


def _check_unique(records: list[Record]) -> None:
    seen = set()
    for record in records:
        if not isinstance(record, Record):
            raise InputError(f"expected Record objects, got {type(record).__name__}")
        if record.record_id in seen:
            raise InputError(f"duplicate record_id {record.record_id!r}")
        seen.add(record.record_id)


def generate_candidates(
    records: list[Record], config: MatchConfig | None = None
) -> Candidates:
    """Return record pairs that share at least one blocking key.

    Records sharing a registration ID, jurisdiction and compatible scheme
    form ID blocks. Records sharing a distinctive name token form name blocks.
    The two kinds have separate size limits. An oversized compatible block is
    not compared, and is listed in `skipped_blocks` so the gap is visible.

    This step only narrows down what gets scored. Pairs with no shared
    identifier or distinctive name token are never compared, so a match that
    only differs in every token (for example a full rename) will be missed.
    """
    config = config or MatchConfig()
    _check_unique(records)
    id_blocks: dict[tuple[str, str], dict[str | None, list[int]]] = {}
    token_blocks: dict[str, list[int]] = {}
    for i, record in enumerate(records):
        if record._id_key:
            id_key = (record._jurisdiction_key or "", record._id_key)
            schemes = id_blocks.setdefault(id_key, {})
            schemes.setdefault(record._scheme_key, []).append(i)
        for token in record._blocking_tokens:
            token_blocks.setdefault(token, []).append(i)

    pairs: set[tuple[int, int]] = set()
    skipped = []
    for (jurisdiction, reg_id), schemes in id_blocks.items():
        for scheme, members in schemes.items():
            key = f"{jurisdiction or '(no jurisdiction)'}:{reg_id}"
            if scheme:
                key = f"{jurisdiction or '(no jurisdiction)'}:{scheme}:{reg_id}"
            if len(members) > config.max_id_block_size:
                skipped.append(
                    SkippedBlock(
                        "registration ID", key, len(members), config.max_id_block_size
                    )
                )
            else:
                pairs.update(combinations(members, 2))

        # A record without a scheme can still match an equal ID from a named
        # scheme, as score_pair treats that exact ID as a match. Compare only
        # those compatible cross-scheme pairs; two different named schemes are
        # never combined into one oversized block.
        unlabelled = schemes.get(None, [])
        for scheme, members in schemes.items():
            if scheme is None or not unlabelled:
                continue
            size = len(unlabelled) + len(members)
            key = f"{jurisdiction or '(no jurisdiction)'}:{reg_id}:unlabelled+{scheme}"
            if size > config.max_id_block_size:
                skipped.append(
                    SkippedBlock(
                        "registration ID",
                        key,
                        size,
                        config.max_id_block_size,
                        omitted_pairs=len(unlabelled) * len(members),
                    )
                )
            else:
                pairs.update(
                    (min(i, j), max(i, j)) for i in unlabelled for j in members
                )
    for token, members in token_blocks.items():
        if len(members) > config.max_block_size:
            skipped.append(
                SkippedBlock("name token", token, len(members), config.max_block_size)
            )
            continue
        pairs.update(combinations(members, 2))
    skipped.sort(key=lambda b: (b.kind, b.key))
    return Candidates([(records[i], records[j]) for i, j in sorted(pairs)], skipped)


def _scripts_label(scripts: frozenset[str]) -> str:
    return "+".join(sorted(s.title() for s in scripts)) or "Latin"


def _best_name_score(left: Record, right: Record) -> dict:
    """Best similarity across names and aliases of comparable scripts.

    Names in different scripts (Cyrillic against Latin, say) cannot be compared
    by character similarity, so those pairs are skipped. If every combination
    is cross-script the result has no score and is flagged for human review.
    """
    best: dict | None = None
    for lv in left._variants:
        for rv in right._variants:
            if lv.norm.non_latin_scripts != rv.norm.non_latin_scripts:
                continue
            score = fuzz.token_sort_ratio(lv.norm.core, rv.norm.core)
            if best is None or score > best["score"]:
                best = {
                    "score": score,
                    "left": lv.text,
                    "right": rv.text,
                    "left_normalized": lv.norm.core,
                    "right_normalized": rv.norm.core,
                    "alias_used": lv.is_alias or rv.is_alias,
                    "cross_script": False,
                    "coverage": min(lv.norm.coverage, rv.norm.coverage),
                }
    if best is not None:
        return best
    lv, rv = left._variants[0], right._variants[0]
    return {
        "score": None,
        "left": lv.text,
        "right": rv.text,
        "left_normalized": lv.norm.core,
        "right_normalized": rv.norm.core,
        "alias_used": False,
        "cross_script": True,
        "left_scripts": sorted(lv.norm.scripts),
        "right_scripts": sorted(rv.norm.scripts),
        "coverage": min(lv.norm.coverage, rv.norm.coverage),
    }


def _legal_family(record: Record) -> str | None:
    form = record._variants[0].norm.legal_form
    return LEGAL_FAMILIES.get(form) if form else None


def _label(score: float, config: MatchConfig) -> str:
    if score >= config.likely_match:
        return LIKELY_MATCH
    if score >= config.needs_review:
        return NEEDS_REVIEW
    return NO_MATCH


def _compare_ids(left: Record, right: Record, same_jurisdiction: bool | None) -> str:
    """Classify the registration IDs of a pair.

    "conflict" needs the same jurisdiction and the same named scheme. If the
    scheme is not given on both sides, two different IDs might simply be
    different kinds of number (a company number and a tax number), so they are
    "unverified" rather than a veto.
    """
    if not (left._id_key and right._id_key):
        return "missing"
    if not same_jurisdiction:
        return "not comparable"
    if left._scheme_key and right._scheme_key and left._scheme_key != right._scheme_key:
        return "not comparable"
    if left._id_key == right._id_key:
        return "match"
    if left._scheme_key and right._scheme_key:
        return "conflict"
    return "unverified"


def score_pair(
    left: Record, right: Record, config: MatchConfig | None = None
) -> MatchResult:
    config = config or MatchConfig()
    notes = []

    name = _best_name_score(left, right)
    cross_script = name["cross_script"]
    score = 0.0
    if cross_script:
        notes.append(
            f"names are in different scripts ({_scripts_label(frozenset(name['left_scripts']))} "
            f"vs {_scripts_label(frozenset(name['right_scripts']))}): "
            f"{name['left']!r} vs {name['right']!r} cannot be scored by spelling, "
            "so the pair goes to human review"
        )
    else:
        score = name["score"] * config.name_weight
        notes.append(
            f"name similarity {round(name['score'], 1)} ({name['left_normalized']!r} vs {name['right_normalized']!r})"
        )
        if name["alias_used"]:
            notes.append(
                f"best name match uses an alias: {name['left']!r} / {name['right']!r}"
            )

    same_jurisdiction = None
    if left._jurisdiction_key and right._jurisdiction_key:
        same_jurisdiction = left._jurisdiction_key == right._jurisdiction_key
        if same_jurisdiction:
            score += config.jurisdiction_match_bonus
            notes.append(f"same jurisdiction ({left._jurisdiction_key})")
        else:
            score -= config.jurisdiction_mismatch_penalty
            notes.append(
                f"different jurisdictions ({left._jurisdiction_key} vs {right._jurisdiction_key})"
            )

    id_status = _compare_ids(left, right, same_jurisdiction)
    if id_status == "match":
        score += config.id_match_bonus
        notes.append(f"registration ID matches ({left.registration_id})")
    elif id_status == "conflict":
        notes.append(
            f"registration IDs conflict ({left.registration_id} vs {right.registration_id}, "
            f"same scheme), score capped at {config.id_conflict_cap}"
        )
    elif id_status == "unverified":
        notes.append(
            f"registration IDs differ ({left.registration_id} vs {right.registration_id}) "
            "but the ID scheme is not given on both records, so this is not treated "
            "as a conflict"
        )
    elif id_status == "missing":
        notes.append("registration ID missing on at least one record")
    elif same_jurisdiction:
        notes.append(
            f"registration IDs not compared (different ID schemes: {left.id_scheme} vs {right.id_scheme})"
        )
    else:
        notes.append(
            "registration IDs not compared (jurisdictions differ or are unknown)"
        )

    if left._city_key and right._city_key and left._city_key == right._city_key:
        score += config.city_match_bonus
        notes.append(f"same city ({left.city})")

    left_family, right_family = _legal_family(left), _legal_family(right)
    if left_family and right_family and left_family != right_family:
        score -= config.legal_form_mismatch_penalty
        notes.append(f"legal forms differ ({left_family} vs {right_family})")

    score_floor, score_ceiling = 0.0, 100.0
    if id_status == "conflict":
        score_ceiling = config.id_conflict_cap
        score = min(score, config.id_conflict_cap)
    else:
        if id_status != "match":
            cap = config.effective_no_id_cap
            score_ceiling = min(score_ceiling, cap)
            if score > cap:
                score = cap
                notes.append(
                    f"no matching registration ID, so the score is capped at {cap} "
                    "and cannot be a likely match"
                )
        if name["coverage"] < config.min_name_coverage:
            score_ceiling = min(score_ceiling, config.review_ceiling)
            notes.append(
                f"only {name['coverage']:.0%} of a name survived normalisation, "
                "so the score is limited and the pair needs a human check"
            )
            score = min(score, config.review_ceiling)
        if cross_script:
            score_floor = config.needs_review
            score_ceiling = min(score_ceiling, config.review_ceiling)
            score = min(max(score, config.needs_review), config.review_ceiling)
        if id_status == "match":
            score_floor = config.needs_review
            name_score = name["score"]
            if name_score is not None and name_score < config.needs_review:
                notes.append(
                    f"registration ID matches but the names differ (similarity {round(name_score, 1)}); "
                    "this may be a renamed company, or a wrong ID, so it needs review"
                )
            score = max(score, config.needs_review)
    exact_score = max(0.0, min(100.0, score))
    display_score = max(score_floor, min(score_ceiling, round(exact_score, 1)))
    label = _label(exact_score, config)
    if _label(display_score, config) != label:
        # Keep a displayed score from crossing a configured label boundary.
        display_score = exact_score

    evidence = _freeze(
        {
            "name": name,
            "registration_id": id_status,
            "same_jurisdiction": same_jurisdiction,
            "cross_script": cross_script,
            "notes": notes,
        }
    )
    return MatchResult(left.record_id, right.record_id, display_score, label, evidence)


def resolve(records: list[Record], config: MatchConfig | None = None) -> Resolution:
    config = config or MatchConfig()
    candidates = generate_candidates(records, config)
    results = [score_pair(a, b, config) for a, b in candidates.pairs]
    results.sort(key=lambda r: (-r.score, r.left_id, r.right_id))
    return Resolution(results, candidates.skipped_blocks)


def record_decision(
    result: MatchResult, reviewer: str, accepted: bool, note: str = ""
) -> dict:
    """Build the review record for an analyst's decision on a candidate pair.

    This is the only place a pair becomes "confirmed" or "rejected". The
    MatchResult is not changed; the returned record carries the decision.
    The score and label are kept alongside it so a later reviewer can see
    what the analyst was shown.
    """
    if not isinstance(result, MatchResult):
        raise TypeError("result must be a MatchResult")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise InputError("a reviewer is required to confirm or reject a match")
    if not isinstance(accepted, bool):
        raise TypeError("accepted must be True (confirm) or False (reject)")
    return {
        "left_id": result.left_id,
        "right_id": result.right_id,
        "score": result.score,
        "label": result.label,
        "status": "confirmed" if accepted else "rejected",
        "reviewer": reviewer.strip(),
        "note": note,
    }
