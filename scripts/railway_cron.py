#!/usr/bin/env python3
"""
Railway cron job script.

Runs the OFAC pipeline, then commits and pushes any data changes to GitHub.

Required environment variables:
    GITHUB_TOKEN    - Personal access token with repo write access
    GITHUB_REPO     - Repository in "owner/repo" format (e.g. "cylon56/ofac-naughtylist")
    GITHUB_BRANCH   - Branch to push to (default: "main")
"""

import json
import logging
import os
import re
import subprocess
import sys
import tempfile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a shell command and log it."""
    logger.info("$ %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.stdout:
        logger.info(result.stdout.rstrip())
    if result.returncode != 0 and result.stderr:
        logger.error(result.stderr.rstrip())
    return result


_CHAIN_DISPLAY_NAMES = {
    "bitcoin_cash": "Bitcoin Cash",
    "bitcoin_gold": "Bitcoin Gold",
    "bitcoin_sv": "Bitcoin SV",
}


def _chain_label(chain: str) -> str:
    return _CHAIN_DISPLAY_NAMES.get(chain, chain.replace("_", " ").title())


def update_readme(repo_dir: str, data_dir: str) -> None:
    """Rewrite the 'Current sanctions snapshot' section of README.md from metadata."""
    readme_path = os.path.join(repo_dir, "README.md")

    with open(os.path.join(data_dir, "metadata.json")) as f:
        meta = json.load(f)

    last_updated = meta["last_updated"][:10]
    total_addresses = meta["total_addresses"]
    total_entities = meta["total_unique_entities"]

    chains_dir = os.path.join(data_dir, "chains")
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

    rows.sort(key=lambda r: (-r[1], r[0]))

    table = "\n".join([
        "| Chain | Addresses | Last Added | File |",
        "| ----- | --------: | ---------- | ---- |",
        *[
            f"| {_chain_label(c)} | {n} | {d} | `data/chains/{c}.json` |"
            for c, n, d in rows
        ],
    ])

    with open(readme_path) as f:
        readme = f.read()

    updated = re.sub(
        r"> Last updated:.*",
        f"> Last updated: **{last_updated}** | **{total_addresses} addresses** across **{total_entities} sanctioned entities**",
        readme,
    )
    updated = re.sub(
        r"\| Chain \| Addresses \| Last Added \| File \|.*?(?=\n\n)",
        table,
        updated,
        flags=re.DOTALL,
    )

    if updated != readme:
        with open(readme_path, "w") as f:
            f.write(updated)
        logger.info("Updated README snapshot section")
    else:
        logger.info("README snapshot section already up to date")


def main() -> int:
    github_token = os.environ.get("GITHUB_TOKEN")
    github_repo = os.environ.get("GITHUB_REPO")
    github_branch = os.environ.get("GITHUB_BRANCH", "main")

    if not github_token or not github_repo:
        logger.error("GITHUB_TOKEN and GITHUB_REPO environment variables are required")
        return 1

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_url = f"https://x-access-token:{github_token}@github.com/{github_repo}.git"

        # Clone repo
        result = run(["git", "clone", "--depth=1", f"--branch={github_branch}", repo_url, tmpdir])
        if result.returncode != 0:
            logger.error("Failed to clone repository")
            return 1

        # Run pipeline inside the cloned repo
        logger.info("Running OFAC pipeline...")
        result = run(
            [sys.executable, "-m", "src.main", "--output-dir", os.path.join(tmpdir, "data")],
            cwd=tmpdir,
            env={**os.environ, "PYTHONPATH": tmpdir},
        )
        if result.returncode != 0:
            logger.error("Pipeline failed")
            return 1

        # Update README snapshot section to reflect new data
        update_readme(tmpdir, os.path.join(tmpdir, "data"))

        # Check for changes
        result = run(["git", "diff", "--quiet", "data/", "README.md"], cwd=tmpdir)
        if result.returncode == 0:
            logger.info("No changes detected — data is up to date")
            return 0

        # Read metadata for commit message
        try:
            with open(os.path.join(tmpdir, "data", "metadata.json")) as f:
                meta = json.load(f)
            addr_count = meta["total_addresses"]
        except Exception:
            addr_count = "unknown"

        # Commit and push
        run(["git", "config", "user.name", "Naughtylist Bot"], cwd=tmpdir)
        run(["git", "config", "user.email", "naughtylist-bot@users.noreply.github.com"], cwd=tmpdir)
        run(["git", "add", "data/", "README.md"], cwd=tmpdir)

        from datetime import datetime, timezone
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        commit_msg = f"naughtylist updated — {timestamp} — {addr_count} addresses checked twice"

        result = run(["git", "commit", "-m", commit_msg], cwd=tmpdir)
        if result.returncode != 0:
            logger.error("Commit failed")
            return 1

        result = run(["git", "push", "origin", github_branch], cwd=tmpdir)
        if result.returncode != 0:
            logger.error("Push failed")
            return 1

        logger.info("Successfully pushed updated data")
        return 0


if __name__ == "__main__":
    sys.exit(main())
