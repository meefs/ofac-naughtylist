"""Tests for src/readme.py — README snapshot section updating."""

import json
import os
import tempfile

import pytest

from src.readme import update_readme

_STALE_README = """# OFAC Naughty List

Some intro text.

## Current sanctions snapshot

> Last updated: **2020-01-01** | **2 addresses** across **1 sanctioned entities**

| Chain | Addresses | Last Added | File |
| ----- | --------: | ---------- | ---- |
| Bitcoin | 1 | 2019-01-01 | `data/chains/bitcoin.json` |
| Ethereum | 1 | 2019-01-01 | `data/chains/ethereum.json` |

Additional supported chains text stays put.

## Output schema
"""


@pytest.fixture
def repo(tmp_path):
    data_dir = tmp_path / "data"
    chains_dir = data_dir / "chains"
    chains_dir.mkdir(parents=True)

    (data_dir / "metadata.json").write_text(json.dumps({
        "last_updated": "2026-07-02T01:13:03Z",
        "total_addresses": 5,
        "total_unique_entities": 3,
        "chains": {"bitcoin": 3, "ethereum": 2},
    }))
    (chains_dir / "bitcoin.json").write_text(json.dumps({
        "addresses": [{"date_listed": "2026-03-12"}, {"date_listed": "2021-01-01"}],
    }))
    (chains_dir / "ethereum.json").write_text(json.dumps({
        "addresses": [{"date_listed": "2026-05-20"}],
    }))

    readme = tmp_path / "README.md"
    readme.write_text(_STALE_README)
    return tmp_path, readme, data_dir


def test_updates_header_and_table(repo):
    tmp_path, readme, data_dir = repo
    changed = update_readme(str(readme), str(data_dir))
    assert changed is True

    text = readme.read_text()
    assert "> Last updated: **2026-07-02** | **5 addresses** across **3 sanctioned entities**" in text
    # Highest count first, correct per-chain counts and last-added dates.
    assert "| Bitcoin | 3 | 2026-03-12 | `data/chains/bitcoin.json` |" in text
    assert "| Ethereum | 2 | 2026-05-20 | `data/chains/ethereum.json` |" in text
    # Surrounding content is preserved.
    assert "Additional supported chains text stays put." in text
    assert "## Output schema" in text
    # Stale numbers are gone.
    assert "2 addresses" not in text
    assert "2020-01-01" not in text


def test_idempotent(repo):
    tmp_path, readme, data_dir = repo
    assert update_readme(str(readme), str(data_dir)) is True
    # Running again against unchanged data makes no further modification.
    assert update_readme(str(readme), str(data_dir)) is False


def test_missing_readme_is_noop(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    assert update_readme(str(tmp_path / "nope.md"), str(data_dir)) is False
