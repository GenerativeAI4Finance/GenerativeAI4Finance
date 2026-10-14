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
    "gmbh": "gmbh",
}


@dataclass(frozen=True)
class NormalizedName:
    raw: str
    core: str
    legal_form: str | None

    @property
    def tokens(self) -> list[str]:
        return self.core.split()


def _ascii_fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def tokenize(text: str) -> list[str]:
    text = _ascii_fold(text).lower().replace("&", " and ")
    # Drop dots without a space so "p.v.t." becomes "pvt" and "l.l.p." becomes "llp".
    text = text.replace(".", "")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.split()


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
    tokens = tokenize(name)
    tokens = [ABBREVIATIONS.get(t, t) for t in tokens]
    tokens = [TRANSLITERATIONS.get(t, t) for t in tokens]
    tokens, legal_form = _strip_legal_form(tokens)
    tokens = [t for t in tokens if t not in STOPWORDS]
    return NormalizedName(raw=name, core=" ".join(tokens), legal_form=legal_form)


def normalize_identifier(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"[^A-Z0-9]", "", value.upper())
    return cleaned or None
