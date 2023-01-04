"""

Filestream class for handling SDS type files

Author: Mathijs Koymans, 2017
Copyright: ORFEUS Data Center, 2017

"""

import os
import json

from obspy import UTCDateTime
from datetime import datetime, timedelta

with open("/data/seismo/wfcatalog/psd-collector/config.json") as configurationFile:
    CONFIG = json.load(configurationFile)


class FileStream:

    """
    Public Class FileStream
    Class for handling files in SDS archive
    """

    def __init__(self, filename):

        """
        Create a filestream from a given filename
        """

        self.filename = filename

        # Extract stream identification
        (
            self.net,
            self.sta,
            self.loc,
            self.cha,
            self.quality,
            self.year,
            self.day,
        ) = filename.split(".")

    # Returns filepath for a given file
    @property
    def filepath(self):
        return os.path.join(self.directory, self.filename)

    # Returns the stream identifier
    @property
    def id(self):
        return ".".join([self.net, self.sta, self.loc, self.cha])

    # Returns the file directory based on SDS structure
    @property
    def directory(self):
        return os.path.join(
            CONFIG["ARCHIVE_ROOT"], self.year, self.net, self.sta, self.channelDirectory
        )

    # Returns channel directory
    @property
    def channelDirectory(self):
        return self.cha + "." + self.quality

    # Returns next file in stream
    @property
    def next(self):
        return self._getAdjacentFile(1)

    # Returns previous file in stream
    @property
    def previous(self):
        return self._getAdjacentFile(-1)

    @property
    def psdEnd(self):
        return self.end + timedelta(minutes=30)

    # Returns start time of file
    @property
    def start(self):
        return UTCDateTime(datetime.strptime(self.year + " " + self.day, "%Y %j"))

    # Returns end time of file
    @property
    def end(self):
        return UTCDateTime(self.start + timedelta(days=1))

    # Returns the file path of file
    @property
    def filepath(self):
        return os.path.join(CONFIG["ARCHIVE_ROOT"], self.directory, self.filename)

    # Returns list of files neighbouring a file
    @property
    def neighbours(self):
        return [
            f
            for f in [self.previous.filepath, self.filepath, self.next.filepath]
            if os.path.isfile(f)
        ]

    # Returns FDSNXML URL for resposnse request
    @property
    def FDSNXMLQuery(self):

        # If the location code is empty we are required to submit "--"
        # to the FDSN webservices
        return "".join(
            [
                CONFIG["FDSN_STATION_ADDRESS"],
                "?net=",
                self.net,
                "&sta=",
                self.sta,
                "&loc=",
                "--" if self.loc == "" else self.loc,
                "&cha=",
                self.cha,
                "&level=response",
            ]
        )

    def _getAdjacentFile(self, direction):

        """
        Private Function _getAdjacentFile
        Returns adjacent filestream based on direction
        """

        newDate = self.start + timedelta(days=direction)

        # The year and day may change
        newYear = newDate.strftime("%Y")
        newDay = newDate.strftime("%j")

        newFilename = ".".join(
            [self.net, self.sta, self.loc, self.cha, self.quality, newYear, newDay]
        )

        return FileStream(newFilename)
