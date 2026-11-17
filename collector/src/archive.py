"""
WFCatalog Collector archive layout.

Everything that turns a day file name into network, station, location,
channel, year and day, and back into a path on disk, for the three supported
archive layouts (SDS, SDSbynet, ODC). Also finds the files of a given date.
"""

import os
import datetime
import logging

from src.config import CONFIG

if CONFIG["STRUCTURE"] == "SDSbynet":
    # SDSbynet structure starts with an extended network code.
    # so we need to add the ability to extend a network code
    from fdsnnetextender.fdsnnetextender import FdsnNetExtender

    fne = FdsnNetExtender()


def getStatsObject(file):
    """
    archive.getStatsObject
    returns object with stream metadata depending on archive struture
    """

    statsArray = file.split(".")

    if CONFIG["STRUCTURE"] == "ODC":
        stats_object = {
            "jday": statsArray.pop(),
            "year": statsArray.pop(),
            "network": statsArray.pop(),
            "channel": statsArray.pop(),
            "station": statsArray.pop(),
        }

    elif CONFIG["STRUCTURE"] == "SDS" or CONFIG["STRUCTURE"] == "SDSbynet":
        stats_object = {
            "jday": statsArray.pop(),
            "year": statsArray.pop(),
            "dtype": statsArray.pop(),
            "channel": statsArray.pop(),
            "location": statsArray.pop(),
            "station": statsArray.pop(),
            "network": statsArray.pop(),
        }

    else:
        raise Exception(
            "Unknown directory structure in archive.getStatsObject"
        )

    return stats_object


def getFilename(stats):
    """
    archive.getFilename
    Returns filename based on structure ODC/SDS
    """

    if CONFIG["STRUCTURE"] == "ODC":
        filename = ".".join(
            [
                stats["station"],
                stats["channel"],
                stats["network"],
                stats["year"],
                stats["jday"],
            ]
        )

    elif CONFIG["STRUCTURE"] == "SDS" or CONFIG["STRUCTURE"] == "SDSbynet":
        filename = ".".join(
            [
                stats["network"],
                stats["station"],
                stats["location"],
                stats["channel"],
                stats["dtype"],
                stats["year"],
                stats["jday"],
            ]
        )

    else:
        raise Exception(
            "Unknown directory structure in archive.getFilename"
        )

    return filename


def getFileDirectory(stats):
    """
    archive.getFileDirectory
    > Returns the directory for a stream at a given date
    """

    if CONFIG["STRUCTURE"] == "ODC":
        filepath = os.path.join(
            stats["year"], stats["jday"], getFilename(stats)
        )

    elif CONFIG["STRUCTURE"] == "SDS":
        filepath = os.path.join(
            stats["year"],
            stats["network"],
            stats["station"],
            stats["channel"] + "." + stats["dtype"],
            getFilename(stats),
        )

    # SDSbynet starts with the extended networkcode
    elif CONFIG["STRUCTURE"] == "SDSbynet":
        try:
            extnet = fne.extend(stats["network"], stats["year"])
        except Exception as e:
            logging.error("Unable to extend network code")
            logging.error(e)
            raise e
        filepath = os.path.join(
            extnet,
            stats["year"],
            stats["station"],
            stats["channel"] + "." + stats["dtype"],
            getFilename(stats),
        )

    else:
        raise Exception(
            "Unknown directory structure in CONFIG (expected ODC or SDS or SDSbynet)"
        )

    return os.path.join(CONFIG["ARCHIVE_ROOT"], filepath)


def getFullPath(file):
    """
    archive.getFullPath
    > returns full path based on the archive root directory
    > for file basename and directory stucture (config)
    """

    return getFileDirectory(getStatsObject(file))


def getNextFile(file, direction):
    """
    archive.getNextFile
    > gets previous or next dayfile depending on direction (-1, +1)
    """

    stats = getStatsObject(os.path.basename(file))
    current_date = datetime.datetime.strptime(
        stats["year"] + " " + stats["jday"], "%Y %j"
    )
    new_date = current_date + datetime.timedelta(days=direction)

    stats["year"] = new_date.strftime("%Y")
    stats["jday"] = new_date.strftime("%j")

    return getFileDirectory(stats)


def getDateFromFile(file):
    """
    archive.getDateFromFile
    > returns datetime object of the day a file based on jday/year
    """

    stats = getStatsObject(os.path.basename(file))
    return datetime.datetime.strptime(stats["year"] + " " + stats["jday"], "%Y %j")


def collectFilesFromDate(date):
    """
    archive.collectFilesFromDate
    > collects the files for a given year and day
    """

    # Get the year & day of year
    jday = date.strftime("%j")
    year = date.strftime("%Y")

    # ODC directory structure makes it simple to loop over years and days
    if CONFIG["STRUCTURE"] == "ODC":
        directory = os.path.join(CONFIG["ARCHIVE_ROOT"], year, jday)
        collectedFiles = [
            os.path.join(directory, f)
            for f in os.listdir(directory)
            if os.path.isfile(os.path.join(directory, f))
        ]

    # SDS structure is slightly more complex, loop over all directories
    # in a year and extract files ending with a given jday
    elif CONFIG["STRUCTURE"] == "SDS":
        collectedFiles = []
        directory = os.path.join(CONFIG["ARCHIVE_ROOT"], year)
        for subdir, dirs, files in os.walk(directory, followlinks=True):
            for file in files:
                if file.endswith(jday) and os.path.isfile(
                    os.path.join(subdir, file)
                ):
                    collectedFiles.append(os.path.join(subdir, file))

    # SDSbynet structure is slightly more complex, loop over all network directories
    # in a year and extract files ending with a given jday
    elif CONFIG["STRUCTURE"] == "SDSbynet":
        collectedFiles = []
        # First, loop over all networks
        for netdir in next(os.walk(CONFIG["ARCHIVE_ROOT"]))[1]:
            # Then find all files
            for subdir, dirs, files in os.walk(
                os.path.join(CONFIG["ARCHIVE_ROOT"], netdir, year), followlinks=True
            ):
                for file in files:
                    if file.endswith(jday) and os.path.isfile(
                        os.path.join(subdir, file)
                    ):
                        collectedFiles.append(os.path.join(subdir, file))

    else:
        raise Exception(
            "WFCatalogCollector.getFilesFromDirectory: unknown directory structure."
        )

    return collectedFiles
