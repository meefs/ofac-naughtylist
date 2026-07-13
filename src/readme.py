"""Update the 'Current sanctions snapshot' section of README.md from generated data.

Kept as part of the core pipeline (rather than a deploy script) so that the
snapshot is refreshed on every ``python -m src.main`` run, regardless of which
runner (GitHub Actions, Railway cron, or a local invocation) executes it.
"""

import json
import logging
import os
import re

logger = logging.getLogger(__name__)

_CHAIN_DISPLAY_NAMES = {
    "bitcoin_cash": "Bitcoin Cash",
    "bitcoin_gold": "Bitcoin Gold",
    "bitcoin_sv": "Bitcoin SV",
}

_TABLE_HEADER = "| Chain | Addresses | Last Added | File |"
_TABLE_DIVIDER = "| ----- | --------: | ---------- | ---- |"


def _chain_label(chain: str) -> str:
    return _CHAIN_DISPLAY_NAMES.get(chain, chain.replace("_", " ").title())


def _build_table(meta: dict, chains_dir: str) -> str:
    rows = []
    for chain, count in meta["chains"].items():
        try:
            with open(os.path.join(chains_dir, f"{chain}.json")) as f:
                chain_data = json.load(f)
            last_added = max(
                (a["date_listed"] for a in chain_data["addresses"] if a.get("date_listed")),
                default="unknown",
            )
        except (FileNotFoundError, json.JSONDecodeError):
            last_added = "unknown"
        rows.append((chain, count, last_added))

    # Sort by descending count, then chain name, for a stable, readable table.
    rows.sort(key=lambda r: (-r[1], r[0]))

    return "\n".join([
        _TABLE_HEADER,
        _TABLE_DIVIDER,
        *[
            f"| {_chain_label(c)} | {n} | {d} | `data/chains/{c}.json` |"
            for c, n, d in rows
        ],
    ])


def update_readme(readme_path: str, data_dir: str) -> bool:
    """Rewrite the snapshot header and chain table of README.md from metadata.

    Args:
        readme_path: Path to the README.md to update.
        data_dir: Directory containing metadata.json and the chains/ subdir.

    Returns:
        True if the README file was modified, False if it was already current
        or could not be updated (missing README/metadata).
    """
    if not os.path.exists(readme_path):
        logger.warning("README not found at %s; skipping snapshot update", readme_path)
        return False

    metadata_path = os.path.join(data_dir, "metadata.json")
    try:
        with open(metadata_path) as f:
            meta = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning("metadata.json not readable at %s; skipping README update", metadata_path)
        return False

    last_updated = meta["last_updated"][:10]
    total_addresses = meta["total_addresses"]
    total_entities = meta["total_unique_entities"]

    table = _build_table(meta, os.path.join(data_dir, "chains"))

    with open(readme_path) as f:
        readme = f.read()

    updated = re.sub(
        r"> Last updated:.*",
        f"> Last updated: **{last_updated}** | **{total_addresses} addresses** "
        f"across **{total_entities} sanctioned entities**",
        readme,
        count=1,
    )
    # Replace the existing table block (header through its final row). The block
    # runs until a blank line or end of file. re.escape avoids treating the
    # replacement text as a regex template.
    updated = re.sub(
        re.escape(_TABLE_HEADER) + r".*?(?=\n\n|\Z)",
        lambda _m: table,
        updated,
        count=1,
        flags=re.DOTALL,
    )

    if updated != readme:
        with open(readme_path, "w") as f:
            f.write(updated)
        logger.info("Updated README snapshot section")
        return True

    logger.info("README snapshot section already up to date")
    return False
