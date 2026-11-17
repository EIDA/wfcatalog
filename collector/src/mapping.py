"""
WFCatalog Collector document mapping.

Turns the metadata dictionary returned by ObsPy into the compact documents
stored in MongoDB (short keys such as "rms", "nsam", "avail"). Pure
functions: no database, no filesystem.
"""

import datetime
import importlib.metadata


def getDatabaseKeyMap(trace, id, flags):
    """
    mapping.getDatabaseKeyMap
    > document parser for daily and hourly granules
    """

    nSegments = len(trace.get("c_segments") or [])

    # Source document for granules
    source = {
        "created": datetime.datetime.now(),
        "collector": importlib.metadata.version("wfcatalog-collector"),
        "warnings": trace["warnings"],
        "status": "open",
        "format": "mSEED",
        "fileId": trace["fileId"],
        "type": "seismic",
        "nseg": nSegments,
        "cont": trace["num_gaps"] == 0,
        "net": trace["network"],
        "sta": trace["station"],
        "cha": trace["channel"],
        "loc": trace["location"],
        "qlt": trace["quality"],
        "ts": trace["start_time"].datetime,
        "te": trace["end_time"].datetime,
        "enc": trace["encoding"],
        "srate": trace["sample_rate"],
        "rlen": trace["record_length"],
        "nrec": int(trace["num_records"])
        if trace["num_records"] is not None
        else None,
        "nsam": int(trace["num_samples"]),
        "smin": int(trace["sample_min"]),
        "smax": int(trace["sample_max"]),
        "smean": float(trace["sample_mean"]),
        "smedian": float(trace["sample_median"]),
        "supper": float(trace["sample_upper_quartile"]),
        "slower": float(trace["sample_lower_quartile"]),
        "rms": float(trace["sample_rms"]),
        "stdev": float(trace["sample_stdev"]),
        "ngaps": int(trace["num_gaps"]),
        "glen": float(trace["sum_gaps"]),
        "nover": int(trace["num_overlaps"]),
        "olen": float(trace["sum_overlaps"]),
        "gmax": float(trace["max_gap"]) if trace["max_gap"] is not None else None,
        "omax": float(trace["max_overlap"])
        if trace["max_overlap"] is not None
        else None,
        "avail": float(trace["percent_availability"]),
        "sgap": trace["start_gap"] is not None,
        "egap": trace["end_gap"] is not None,
    }

    # Add parent streamId if it is given, this links
    # the daily stream to hourly granules
    if id is not None:
        source.update({"streamId": id})

    # Add the miniseed header percentages and timing quality
    if flags:
        source.update(getTimingQuality(trace))
        source.update(getFlags(trace))

    return source


def getDatabaseKeyMapContinuous(trace, id):
    """
    mapping.getDatabaseKeyMapContinuous
    > Document parser for continuous segments
    """

    # Source object for a continuous segment
    source = {
        "streamId": id,
        "smin": int(trace["sample_min"]),
        "smax": int(trace["sample_max"]),
        "smean": float(trace["sample_mean"]),
        "smedian": float(trace["sample_median"]),
        "stdev": float(trace["sample_stdev"]),
        "rms": float(trace["sample_rms"]),
        "supper": float(trace["sample_upper_quartile"]),
        "slower": float(trace["sample_lower_quartile"]),
        "nsam": int(trace["num_samples"]),
        "srate": float(trace["sample_rate"]),
        "ts": trace["start_time"].datetime,
        "te": trace["end_time"].datetime,
        "slen": float(trace["segment_length"]),
    }

    return source


def getTimingQuality(trace):
    """
    mapping.getTimingQuality
    writes timing quality parameters and correction to source document
    """

    trace = trace["miniseed_header_percentages"]

    # Add the timing correction
    source = {"tcorr": float(trace["timing_correction"])}

    # Check if the minimum is None, so is the rest
    # otherwise convert to floats
    if trace["timing_quality_min"] is None:
        source.update(
            {
                "tqmin": None,
                "tqmax": None,
                "tqmean": None,
                "tqmedian": None,
                "tqupper": None,
                "tqlower": None,
            }
        )

    else:
        source.update(
            {
                "tqmin": float(trace["timing_quality_min"]),
                "tqmax": float(trace["timing_quality_max"]),
                "tqmean": float(trace["timing_quality_mean"]),
                "tqmedian": float(trace["timing_quality_median"]),
                "tqupper": float(trace["timing_quality_upper_quartile"]),
                "tqlower": float(trace["timing_quality_lower_quartile"]),
            }
        )

    return source


def getFlags(trace):
    """
    mapping.getFlags
    writes mSEED header flag percentages to source document
    """

    header = trace["miniseed_header_percentages"]

    source = {
        "io_flags": getFlagKeys(header, "io_and_clock_flags"),
        "dq_flags": getFlagKeys(header, "data_quality_flags"),
        "ac_flags": getFlagKeys(header, "activity_flags"),
    }

    return source


def getFlagKeys(trace, flag_type):
    """
    mapping.getFlagKeys
    returns MongoDB document structure for miniseed header percentages
    """

    trace = trace[flag_type]

    if flag_type == "activity_flags":
        source = {
            "cas": trace["calibration_signal"],
            "tca": trace["time_correction_applied"],
            "evb": trace["event_begin"],
            "eve": trace["event_end"],
            "eip": trace["event_in_progress"],
            "pol": trace["positive_leap"],
            "nel": trace["negative_leap"],
        }

    elif flag_type == "data_quality_flags":
        source = {
            "asa": trace["amplifier_saturation"],
            "dic": trace["digitizer_clipping"],
            "spi": trace["spikes"],
            "gli": trace["glitches"],
            "mpd": trace["missing_padded_data"],
            "tse": trace["telemetry_sync_error"],
            "dfc": trace["digital_filter_charging"],
            "stt": trace["suspect_time_tag"],
        }

    elif flag_type == "io_and_clock_flags":
        source = {
            "svo": trace["station_volume"],
            "lrr": trace["long_record_read"],
            "srr": trace["short_record_read"],
            "sts": trace["start_time_series"],
            "ets": trace["end_time_series"],
            "clo": trace["clock_locked"],
        }

    else:
        raise Exception("Unknown flag type in mapping.getFlagKeys")

    # Make sure the flags are floats
    for flag in source:
        source[flag] = float(source[flag])

    return source
