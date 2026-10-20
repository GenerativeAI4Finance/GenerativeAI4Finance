"""Name and identifier normalisation for company records."""

import re
import unicodedata
from dataclasses import dataclass

# Legal form suffixes, matched at the end of a name. Longer forms first so
# "private limited" wins over "limited".
LEGAL_FORMS = [
    (("limited", "liability", "partnership"), "llp"),
    (("private", "limited"), "private limited"),
    (("private", "ltd"), "private limited"),
    (("pvt", "limited"), "private limited"),
    (("pvt", "ltd"), "private limited"),
    (("pte", "ltd"), "private limited"),
    (("pty", "limited"), "private limited"),
    (("pty", "ltd"), "private limited"),
    (("pty",), "private limited"),
    (("limited",), "limited"),
    (("ltd",), "limited"),
    (("llp",), "llp"),
    (("llc",), "llc"),
    (("plc",), "plc"),
    (("incorporated",), "inc"),
    (("inc",), "inc"),
    (("corporation",), "corp"),
    (("corp",), "corp"),
    (("company",), "company"),
    (("co",), "company"),
    (("gmbh",), "gmbh"),
    (("bv",), "bv"),
    (("srl",), "srl"),
    (("sarl",), "sarl"),
    (("ag",), "ag"),
    (("nv",), "nv"),
    (("spa",), "spa"),
    (("sa",), "sa"),
    (("a", "s"), "as"),
    (("as",), "as"),
]

ABBREVIATIONS = {
    "intl": "international",
    "mfg": "manufacturing",
    "mfrs": "manufacturers",
    "bros": "brothers",
    "svcs": "services",
    "engg": "engineering",
    "inds": "industries",
}

# Placeholder table for transliteration variants. Each spelling maps to one
# canonical form. Extend this per jurisdiction; it is not a transliteration
# engine.
TRANSLITERATIONS = {
    "shree": "sri",
    "shri": "sri",
    "laxmi": "lakshmi",
    "mohd": "mohammed",
    "muhammad": "mohammed",
    "mohamed": "mohammed",
}

STOPWORDS = {"the", "and", "of"}

# Legal forms that can describe the same kind of entity. "company" on its own
# says little, so it has no family and never counts as a disagreement.
LEGAL_FAMILIES = {
    "private limited": "limited",
    "limited": "limited",
    "plc": "limited",
    "inc": "corporation",
    "corp": "corporation",
    "llp": "partnership",
    "llc": "llc",
    "gmbh": "private company",
    "bv": "private company",
    "srl": "private company",
    "sarl": "private company",
    "ag": "joint stock",
    "nv": "joint stock",
    "spa": "joint stock",
    "sa": "joint stock",
    "as": "joint stock",
}

# Letters that do not decompose under Unicode normalisation.
_LETTER_FOLDS = str.maketrans(
    {
        "ø": "o",
        "ł": "l",
        "đ": "d",
        "ð": "d",
        "þ": "th",
        "æ": "ae",
        "œ": "oe",
        "ı": "i",
        "ħ": "h",
    }
)

# Common alternative codes for the same jurisdiction. Not exhaustive.
JURISDICTION_ALIASES = {
    "UK": "GB",
    "GBR": "GB",
    "USA": "US",
    "IND": "IN",
    "SGP": "SG",
    "DEU": "DE",
    "FRA": "FR",
    "IRL": "IE",
}

# Identifier values that stand for "no identifier".
_PLACEHOLDER_IDS = {"NA", "NONE", "NULL", "NIL", "UNKNOWN", "TBD", "MISSING"}

# An initialism written with dots ("P.V.T.", "S.p.A.") is one token, while
# "Pvt.Ltd." is two. A dot only joins single letters on both of its sides.
_DOTTED_INITIALS = re.compile(r"(?<=\b[^\W\d_])\.(?=[^\W\d_](?:\.|\b))")
_APOSTROPHES = re.compile(r"['’ʼ`´]")


@dataclass(frozen=True)
class NormalizedName:
    raw: str
    core: str
    legal_form: str | None
    # Scripts of the letters in the core name ("LATIN", "CYRILLIC", ...).
    scripts: frozenset[str] = frozenset()
    # Share of the name's characters that survived tokenising. Below 1.0 when
    # symbols or unassigned characters were dropped.
    coverage: float = 1.0

    @property
    def tokens(self) -> list[str]:
        return self.core.split()

    @property
    def non_latin_scripts(self) -> frozenset[str]:
        return self.scripts - {"LATIN"}


def _fold(text: str) -> str:
    """Casefold and strip accents from Latin letters.

    Marks on other scripts are kept, so "й" stays distinct from "и" and
    Devanagari vowel signs stay attached.
    """
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    kept = []
    base_is_latin = False
    for char in decomposed:
        if unicodedata.category(char).startswith("M"):
            if base_is_latin:
                continue
        else:
            base_is_latin = unicodedata.name(char, "").startswith("LATIN")
        kept.append(char)
    return unicodedata.normalize("NFC", "".join(kept)).translate(_LETTER_FOLDS)


def _script(char: str) -> str:
    return unicodedata.name(char, "UNKNOWN").split()[0]


def _tokenize(text: str) -> tuple[list[str], int, int]:
    """Split a name into tokens. Returns (tokens, kept chars, lost chars)."""
    text = _fold(text).replace("&", " and ")
    text = _APOSTROPHES.sub("", text)
    text = _DOTTED_INITIALS.sub("", text)
    kept = lost = 0
    chars = []
    for char in text:
        category = unicodedata.category(char)
        if category[0] in "LN":
            kept += 1
            chars.append(char)
        elif category[0] == "M":
            chars.append(char)
        else:
            if category[0] == "S" or category in ("Co", "Cn", "Cs"):
                lost += 1
            chars.append(" ")
    return "".join(chars).split(), kept, lost


def tokenize(text: str) -> list[str]:
    return _tokenize(text)[0]


def _strip_legal_form(tokens: list[str]) -> tuple[list[str], str | None]:
    found = []
    changed = True
    while changed and tokens:
        changed = False
        for pattern, canonical in LEGAL_FORMS:
            n = len(pattern)
            if len(tokens) > n and tuple(tokens[-n:]) == pattern:
                tokens = tokens[:-n]
                found.append(canonical)
                changed = True
                break
    # The last suffix is the legal form; "Co Ltd" is still a limited company.
    return tokens, found[0] if found else None


def normalize_name(name: str) -> NormalizedName:
    if not isinstance(name, str):
        raise TypeError(f"name must be a string, not {type(name).__name__}")
    tokens, kept, lost = _tokenize(name)
    tokens = [ABBREVIATIONS.get(t, t) for t in tokens]
    tokens = [TRANSLITERATIONS.get(t, t) for t in tokens]
    tokens, legal_form = _strip_legal_form(tokens)
    # A name made only of stopwords ("The") keeps them rather than vanishing.
    tokens = [t for t in tokens if t not in STOPWORDS] or tokens
    core = " ".join(tokens)
    scripts = frozenset(_script(c) for c in core if unicodedata.category(c)[0] == "L")
    total = kept + lost
    coverage = kept / total if total else 0.0
    return NormalizedName(
        raw=name, core=core, legal_form=legal_form, scripts=scripts, coverage=coverage
    )


def normalize_identifier(value: str | None) -> str | None:
    """Uppercase an identifier and drop separators and placeholder values.

    All-digit identifiers also lose leading zeros, so "00445790" equals
    "445790". Identifiers that contain letters keep their zeros.
    """
    if not value:
        return None
    cleaned = re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", value)).upper()
    if cleaned in _PLACEHOLDER_IDS:
        return None
    if re.fullmatch(r"[0-9]+", cleaned):
        cleaned = cleaned.lstrip("0")
    return cleaned or None


def normalize_scheme(value: str | None) -> str | None:
    """Reduce an identifier scheme label ("Companies House") to a comparable key."""
    if not value:
        return None
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", value)).upper() or None


def normalize_jurisdiction(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    code = value.strip().upper()
    return JURISDICTION_ALIASES.get(code, code)


def normalize_city(value: str | None) -> str | None:
    if not value:
        return None
    return " ".join(tokenize(value)) or None
