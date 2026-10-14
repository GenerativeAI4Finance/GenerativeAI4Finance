import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from synthetic import make_panel

VALID_START = "2022-07-01"
TEST_START = "2023-04-01"


@pytest.fixture
def panel():
    return make_panel(seed=0)
