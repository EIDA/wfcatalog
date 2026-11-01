"""
Issue #22: --delete must accept files that are no longer in the archive,
because deleting the metadata of a removed file is the main use of --delete.
"""

import json
import pytest

from src.WFCatalogCollector import WFCatalogCollector

MISSING = "/nowhere/NL.HGN.02.LHZ.D.2017.022"


def collector_with(**options):
    collector = WFCatalogCollector()
    collector._setOptions(options)
    return collector


def test_delete_keeps_missing_file():
    collector = collector_with(file=MISSING, delete=True)
    collector._getFiles()
    assert collector.files == [MISSING]


def test_delete_keeps_missing_files_from_list():
    collector = collector_with(list=json.dumps([MISSING]), delete=True)
    collector._getFiles()
    assert collector.files == [MISSING]


def test_process_still_rejects_missing_file():
    collector = collector_with(file=MISSING)
    with pytest.raises(Exception, match="valid file"):
        collector._getFiles()


def test_process_still_drops_missing_files_from_list():
    collector = collector_with(list=json.dumps([MISSING]))
    collector._getFiles()
    assert collector.files == []
