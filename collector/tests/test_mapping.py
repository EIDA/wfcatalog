"""
Tests for src/mapping.py: ObsPy metadata dictionary to MongoDB document.

The expected documents in tests/expected/mapped_documents.json were produced
from the frozen ObsPy output in bundled_archive_output.txt by the collector
before the mapping code was moved into its own module. "created" is masked
because it is the current time.
"""

import json
import os
from collections import OrderedDict
from pathlib import Path

import numpy as np
from obspy import UTCDateTime

from src import mapping
from src.WFCatalogCollector import WFCatalogCollector

EXPECTED_DIR = Path(__file__).resolve().parent / "expected"


def load_frozen_obspy_documents():
    """The three {'daily': ..., 'hourly': [...]} dictionaries printed by the collector."""
    namespace = {"UTCDateTime": UTCDateTime, "OrderedDict": OrderedDict, "np": np, "nan": float("nan")}
    with open(EXPECTED_DIR / "bundled_archive_output.txt") as f:
        return [eval(line, namespace) for line in f if line.startswith("{'daily'")]


def as_json(obj):
    return json.loads(json.dumps(obj, default=str))


def test_mapped_documents_are_unchanged(monkeypatch):
    # Checksums are computed from the bundled files, relative to the collector dir.
    monkeypatch.chdir(EXPECTED_DIR.parent.parent)
    collector = WFCatalogCollector()

    actual = []
    for doc in load_frozen_obspy_documents():
        daily = mapping.getDatabaseKeyMap(doc["daily"], None, flags=True)
        daily.update(collector._getFileChecksums(doc["daily"]["files"]))
        hourly = []
        for h in doc["hourly"]:
            m = mapping.getDatabaseKeyMap(h, "STREAMID", flags=True)
            m.update(collector._getFileChecksums(h["files"]))
            hourly.append(m)
        segs = [mapping.getDatabaseKeyMapContinuous(s, "STREAMID") for s in doc["daily"]["c_segments"]]
        for m in [daily] + hourly:
            m["created"] = "MASKED"
        actual.append({"daily": daily, "hourly": hourly, "c_segments": segs})
    actual.sort(key=lambda x: x["daily"]["fileId"])

    expected = json.load(open(EXPECTED_DIR / "mapped_documents.json"))
    assert as_json(actual) == expected


def test_flags_are_omitted_when_not_requested():
    doc = load_frozen_obspy_documents()[0]["daily"]
    without = mapping.getDatabaseKeyMap(doc, None, flags=False)
    with_flags = mapping.getDatabaseKeyMap(doc, None, flags=True)
    assert "io_flags" not in without and "tqmin" not in without
    assert "io_flags" in with_flags and "tqmin" in with_flags


def test_continuous_segment_keys():
    seg = load_frozen_obspy_documents()[0]["daily"]["c_segments"][0]
    mapped = mapping.getDatabaseKeyMapContinuous(seg, "STREAMID")
    assert set(mapped) == {
        "streamId", "smin", "smax", "smean", "smedian", "stdev", "rms",
        "supper", "slower", "nsam", "srate", "ts", "te", "slen",
    }
    assert mapped["streamId"] == "STREAMID"
    assert mapped["nsam"] == seg["num_samples"]
