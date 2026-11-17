"""
Tests for src/FastMSEEDMetadata.py (pull request #45 by Roman Racine).

ObsPy 1.5 computes the standard deviation as sqrt(mean(x**2) - mean(x)**2).
The two terms are huge and nearly equal when the data has a large offset, so
the difference loses its digits: a dead channel gets a standard deviation
that is not zero, or NaN. FastMSEEDMetadata computes it from the deviations
and stays exact. Every other metric must be the same as ObsPy's.
"""

import math
import warnings

import numpy as np
import pytest
from obspy import Stream, Trace, UTCDateTime
from obspy.signal.quality_control import MSEEDMetadata

from src import metrics
from src.FastMSEEDMetadata import FastMSEEDMetadata

START = UTCDateTime(2020, 1, 1)
END = START + 3600
RATE = 20.0
NPTS = int(RATE * 3600)

BUNDLED = "archive/2017/NL/HGN/LHZ.D/NL.HGN.02.LHZ.D.2017.022"

# The metrics computed by the method that FastMSEEDMetadata replaces
SAMPLE_METRICS = (
    "sample_min",
    "sample_max",
    "sample_mean",
    "sample_median",
    "sample_lower_quartile",
    "sample_upper_quartile",
    "sample_rms",
    "sample_stdev",
)


def write_hour(tmp_path, data):
    """Write one hour of samples to a miniSEED file and return its path."""
    header = dict(network="XX", station="TEST", channel="BHZ", sampling_rate=RATE, starttime=START)
    path = str(tmp_path / "XX.TEST..BHZ.D.2020.001")
    Stream([Trace(np.asarray(data, dtype=np.int32), header=header)]).write(
        path, format="MSEED", encoding="INT32", reclen=4096
    )
    return path


def exact_stdev(data):
    """Population standard deviation with Python integers, so nothing is rounded."""
    values = [int(v) for v in data]
    n = len(values)
    total = sum(values)
    squares = sum(v * v for v in values)
    return math.sqrt(squares * n - total * total) / n


def noise_on(offset):
    rng = np.random.default_rng(7)
    return offset + rng.integers(-1, 2, NPTS)


@pytest.mark.parametrize("value", [8388607, -5000001, 2000000000])
def test_dead_channel_has_zero_stdev(tmp_path, value):
    path = write_hour(tmp_path, np.full(NPTS, value))

    meta = FastMSEEDMetadata([path], starttime=START, endtime=END).meta

    assert meta["sample_stdev"] == 0.0


@pytest.mark.parametrize("offset", [8000000, 2000000000])
def test_stdev_is_exact_with_a_large_offset(tmp_path, offset):
    data = noise_on(offset)
    path = write_hour(tmp_path, data)

    meta = FastMSEEDMetadata([path], starttime=START, endtime=END).meta

    assert meta["sample_stdev"] == pytest.approx(exact_stdev(data), rel=1e-12)


def test_obspy_alone_gets_this_case_wrong(tmp_path):
    """Documents why the subclass is needed. If this fails, ObsPy fixed its formula."""
    data = noise_on(2000000000)
    path = write_hour(tmp_path, data)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        meta = MSEEDMetadata([path], starttime=START, endtime=END).meta

    # NaN or a value far from the truth, depending on how the rounding falls
    assert meta["sample_stdev"] != pytest.approx(exact_stdev(data), rel=1e-3)


def test_other_metrics_equal_obspy_on_a_bundled_file():
    start = UTCDateTime(2017, 1, 22)
    arguments = dict(starttime=start, endtime=start + 86400, add_flags=True, add_c_segments=True)

    fast = FastMSEEDMetadata([BUNDLED], **arguments).meta
    obspy = MSEEDMetadata([BUNDLED], **arguments).meta

    assert set(fast) == set(obspy)
    for key, expected in obspy.items():
        if key in SAMPLE_METRICS:
            assert float(fast[key]) == pytest.approx(float(expected), rel=1e-12), key
        elif key not in ("wfmetadata_id", "c_segments"):
            assert fast[key] == expected, key


def test_collector_computes_metrics_with_the_fast_class(tmp_path):
    path = write_hour(tmp_path, np.full(NPTS, -5000001))

    meta = metrics.computeMetadata([path], START, END, "daily", False, False)

    assert meta["sample_stdev"] == 0.0
    assert meta["warnings"] is False
