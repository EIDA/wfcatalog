"""
Characterisation test for the collector pipeline.

Runs the collector on the bundled day files under collector/archive/ with the
database disabled and every optional metric enabled, and compares the printed
documents with a frozen copy in tests/expected/.

The test does not check that the numbers are right (ObsPy is trusted for
that). It checks that a change to the collector does not alter them by
accident. If a change is meant to alter the output, regenerate the frozen
copy with:

    UPDATE_EXPECTED=1 uv run pytest tests/test_collector_output.py

and review the resulting diff in the pull request.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

COLLECTOR_DIR = Path(__file__).resolve().parent.parent
EXPECTED_FILE = Path(__file__).resolve().parent / "expected" / "bundled_archive_output.txt"

# ObsPy assigns a fresh random UUID to every document; it is the only
# nondeterministic value in the output.
UUID_RE = re.compile(r"smi:local/qc/[0-9a-f-]{36}")
FILE_ID_RE = re.compile(r"'fileId': '([^']+)'")


def run_collector(tmp_path):
    """Run the collector as a subprocess and return the printed document lines."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("WFCAT_")}
    env.update(
        {
            # Empty directory: no config.json, so the WFCAT_* variables apply.
            "WFCAT_CONF_DIR": str(tmp_path),
            # Relative path on purpose, so the frozen output has no machine-specific paths.
            "WFCAT_ARCHIVE_ROOT": "archive/",
            "WFCAT_MONGO_ENABLED": "false",
        }
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.WFCatalogCollector",
            "--dir",
            "archive/",
            "--csegs",
            "--flags",
            "--hourly",
        ],
        cwd=COLLECTOR_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    # One document line per processed file; everything else is logging.
    docs = [line for line in result.stdout.splitlines() if line.startswith("{'daily'")]
    docs = [UUID_RE.sub("smi:local/qc/UUID", line) for line in docs]
    # Directory walk order differs between filesystems; sort by fileId.
    docs.sort(key=lambda line: FILE_ID_RE.search(line).group(1))
    return docs


def test_bundled_archive_output_is_unchanged(tmp_path):
    actual = run_collector(tmp_path)
    assert len(actual) == 3, "expected one document per bundled day file"

    if os.environ.get("UPDATE_EXPECTED") == "1":
        EXPECTED_FILE.write_text("\n".join(actual) + "\n")

    expected = EXPECTED_FILE.read_text().splitlines()
    if actual != expected:
        raise AssertionError(
            "Collector output changed. If intended, regenerate with "
            "UPDATE_EXPECTED=1 and review the diff.\n" + first_difference(expected, actual)
        )


def first_difference(expected, actual, context=120):
    """Describe the first differing value; each document is one very long line."""
    if len(expected) != len(actual):
        return f"{len(expected)} expected document(s), {len(actual)} actual"
    for n, (exp, act) in enumerate(zip(expected, actual)):
        if exp == act:
            continue
        i = 0
        while i < min(len(exp), len(act)) and exp[i] == act[i]:
            i += 1
        lo = max(0, i - context)
        return (
            f"document {n} ({FILE_ID_RE.search(exp).group(1)}), first difference at char {i}:\n"
            f"  expected: ...{exp[lo:i + context]}...\n"
            f"  actual:   ...{act[lo:i + context]}..."
        )
    return ""
