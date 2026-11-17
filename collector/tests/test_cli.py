"""
Tests for the command line of the collector, run as a subprocess the way an
operator starts it.
"""

import importlib.metadata
import os
import subprocess
import sys
from pathlib import Path

COLLECTOR_DIR = Path(__file__).resolve().parent.parent


def run_collector(tmp_path, *arguments):
    env = {k: v for k, v in os.environ.items() if not k.startswith("WFCAT_")}
    # Empty directory: no config.json, so the defaults apply.
    env["WFCAT_CONF_DIR"] = str(tmp_path)
    return subprocess.run(
        [sys.executable, "-m", "src.WFCatalogCollector", *arguments],
        cwd=COLLECTOR_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


def test_version_prints_the_package_version(tmp_path):
    result = run_collector(tmp_path, "--version")

    assert result.returncode == 0
    assert result.stdout.strip() == importlib.metadata.version("wfcatalog-collector")
