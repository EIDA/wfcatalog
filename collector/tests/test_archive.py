"""
Unit tests for src/archive.py on the bundled SDS day files.

The archive layout is read from CONFIG at import time, and the test
environment has no config.json, so these tests cover the SDS layout only.
"""

import datetime
import os

from src import archive

BUNDLED = "NL.HGN.02.LHZ.D.2017.021"


def test_stats_from_sds_filename():
    stats = archive.getStatsObject(BUNDLED)
    assert stats == {
        "network": "NL",
        "station": "HGN",
        "location": "02",
        "channel": "LHZ",
        "dtype": "D",
        "year": "2017",
        "jday": "021",
    }


def test_filename_round_trips():
    assert archive.getFilename(archive.getStatsObject(BUNDLED)) == BUNDLED


def test_sds_directory_layout():
    path = archive.getFileDirectory(archive.getStatsObject(BUNDLED))
    assert path == os.path.join("2017", "NL", "HGN", "LHZ.D", BUNDLED)
    assert archive.getFullPath(BUNDLED) == path


def test_next_and_previous_day_file():
    assert archive.getNextFile(BUNDLED, 1).endswith("NL.HGN.02.LHZ.D.2017.022")
    assert archive.getNextFile(BUNDLED, -1).endswith("NL.HGN.02.LHZ.D.2017.020")


def test_next_file_rolls_over_the_year():
    last = "NL.HGN.02.LHZ.D.2017.365"
    assert archive.getNextFile(last, 1).endswith("NL.HGN.02.LHZ.D.2018.001")


def test_date_from_file():
    assert archive.getDateFromFile(BUNDLED) == datetime.datetime(2017, 1, 21)


def test_collect_files_from_date(monkeypatch):
    monkeypatch.setitem(archive.CONFIG, "ARCHIVE_ROOT", "archive/")
    monkeypatch.chdir(os.path.dirname(os.path.dirname(__file__)))
    files = archive.collectFilesFromDate(datetime.datetime(2017, 1, 22))
    assert [os.path.basename(f) for f in files] == ["NL.HGN.02.LHZ.D.2017.022"]
    assert archive.collectFilesFromDate(datetime.datetime(2017, 1, 25)) == []
