"""
WFCatalog Collector metric computation.

The single place where ObsPy's mSEED quality control is called, guarded by
the per-file processing timeout from the configuration.
"""

import signal
import warnings

from src.config import CONFIG


def handler(signum, frame):
    raise Exception("Metric calculation has timed out")


# ObsPy mSEED-QC is required
try:
    from obspy.signal.quality_control import MSEEDMetadata
except ImportError:
    raise ImportError("Failure to load MSEEDMetadata; ObsPy mSEED-QC is required.")


def computeMetadata(files, start, end, granule, flags, csegs):
    """
    metrics.computeMetadata
    wrapper function to call obspy.signal.MSEEDMetdata
    """

    # Throw an exception after the timeout (UNIX only)
    signal.signal(signal.SIGALRM, handler)
    signal.alarm(CONFIG["PROCESSING_TIMEOUT"])

    try:
        # Catch mSEED reading warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # Skip continuous segments for hourly granules
            if granule == "daily":
                metadata = MSEEDMetadata(
                    files,
                    starttime=start,
                    endtime=end,
                    add_flags=flags,
                    add_c_segments=csegs,
                )
            elif granule == "hourly":
                metadata = MSEEDMetadata(
                    files,
                    starttime=start,
                    endtime=end,
                    add_flags=flags,
                    add_c_segments=False,
                )

            metadata.meta.update({"warnings": len(w) > 0})

    finally:
        # Disable alarm
        signal.alarm(0)

    return metadata.meta
