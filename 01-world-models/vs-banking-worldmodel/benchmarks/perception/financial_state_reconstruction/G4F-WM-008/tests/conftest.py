import copy
import sys
from functools import cache
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from synthetic import make_panel

VALID_START = "2022-07-01"
TEST_START = "2023-04-01"


@cache
def _panel(**kwargs):
    return make_panel(**kwargs)


def cached_panel(**kwargs):
    """make_panel, built once per argument set. Callers get their own copy."""
    df, spec = _panel(**kwargs)
    return df.copy(), copy.deepcopy(spec)


@pytest.fixture
def panel():
    return cached_panel(seed=0)
