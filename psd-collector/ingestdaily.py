"""

  Binned PSD (Power Spectral Densities) Extraction
  
  Compression to special format and saved to MongoDB
  
  DESCRIPTION OF PSD FORMAT:
  
  The PSDs are given as a binary string of unsigned 8-bit integers
  The first byte of the string indicates the offset of the first period
  starting from 0.001 and increasing by 1/8th of an octave per index
  Following bytes are absolute values normalized to -50

  Requires a modification in ObsPy
  
  Copyright 2017, Mathijs Koymans, ORFEUS Data Center, KNMI, De Bilt
  
  Licensed under GPL-3.0 - All Rights Reserved

"""

import os
import sys
import math
import json
import logging
import warnings

from struct import pack
from bson.binary import Binary
from obspy import read_inventory, Stream, UTCDateTime, read
from obspy.signal import PPSD

from requests.exceptions import HTTPError
from datetime import datetime, timedelta
from logging import FileHandler

# Custom FileStream class
from filestream import FileStream

with open("/data/seismo/wfcatalog/psd-collector/config.json") as configurationFile:
    CONFIG = json.load(configurationFile)


class PSDExtractor:

    """
    Public Class PPSDExtractor
    Wrapper for extratcing PSD values from seismic traces
    """

    # Lower and upper limit for frequencies [0.01, 1000]
    # necessary to standardize freq/period bins

    def __init__(self, log):

        self.log = log

        # Cache for inventories
        self.INVENTORY_CACHE = {}

        self.PERIOD_TUPLE = (CONFIG["PERIOD_LOWER_LIMIT"], CONFIG["PERIOD_UPPER_LIMIT"])

    def _setupLogger(self, logfile):

        # Set up WFCatalogger
        self.log = logging.getLogger("PSDThread")

        log_file = logfile or CONFIG["DEFAULT_LOG_FILE"]

        self.log.setLevel("INFO")
        self.file_handler = FileHandler(log_file)
        self.file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        self.log.addHandler(self.file_handler)

    def Process(self, filename):

        """
        Public Function Process
        Calculates PSD values for given file
        """

        initialized = datetime.now()

        filestream = FileStream(filename)

        # Skip infrasound channels
        if filestream.cha.endswith("DF"):
            raise Exception("File %s is an infrasound channel." % filename)

        # Get the response information
        inventory = self.GetInventory(filestream)

        self.log.info("Succesfully requested inventory for %s." % filename)

        # Create an empty ObsPy stream and fill it
        ObspyStream = Stream()

        self.log.info("Collected neighbouring files %s." % filestream.neighbours)

        # Collect data from the archive
        for filepath in filestream.neighbours:

            st = read(
                filepath,
                starttime=filestream.start,
                endtime=filestream.next.end,
                nearest_sample=False,
                format="MSEED",
            )

            # Concatenate all traces
            for tr in st:
                if tr.stats.npts != 0:
                    ObspyStream.extend([tr])

        # No data was read
        if not ObspyStream:
            raise Exception("No data within temporal constraints for %s." % filename)

        # Attempt to merge all streams with a fill value of 0
        ObspyStream.merge(0, fill_value=0)

        # Single trace
        if len(ObspyStream) > 1:
            raise Exception("More than a single stream detected in %s." % filename)

        trace = ObspyStream[0]

        # Trim the stream and pad values with 0
        # Include start and exclusive end
        ObspyStream.trim(
            starttime=filestream.start,
            endtime=filestream.psdEnd,
            pad=True,
            fill_value=0,
            nearest_sample=False,
        )

        warn = False

        # Attempt to extract PSD values
        with warnings.catch_warnings(record=True) as w:

            warnings.simplefilter("always")

            ppsd = PPSD(trace.stats, inventory, period_limits=self.PERIOD_TUPLE)

            ppsd.add(ObspyStream)

            warn = len(w) > 0

        self.log.info(
            "Succesfully calculated %i power spectral densities for %s."
            % (len(ppsd._binned_psds), filename)
        )

        results = []

        # Go over all returned segment and time steps
        for segment, time in zip(ppsd._binned_psds, self._Times(filestream.start)):

            # Concatenate offset with PSD values
            # Attempt to create a byte string
            try:
                psd_array = self._GetOffset(segment, ppsd.valid)
                byteAmplitudes = self._AsByteArray(psd_array)
            except Exception as ex:
                self.log.error("Could not compress spectra for %s" % filename)
                continue

            results.append(
                {
                    "net": filestream.net,
                    "fileId": filestream.filename,
                    "sta": filestream.sta,
                    "loc": filestream.loc,
                    "cha": filestream.cha,
                    "warnings": warn,
                    "ts": UTCDateTime(time).datetime,
                    "te": (UTCDateTime(time) + timedelta(minutes=60)).datetime,
                    "binary": byteAmplitudes,
                }
            )

        return {
            "spectra": results,
            "filename": filename,
            "time": (datetime.now() - initialized),
        }

    def _Times(self, start):

        """
        Returns 48 times starting at the start of the filestream
        with 30 minute increments
        """

        return [start + timedelta(minutes=(30 * x)) for x in range(48)]

    def _AsByteArray(self, array):

        """
        Private Function _AsByteArray
        Packs list of values 0 <= i <= 255 to byte array
        to be stored in MongoDB as an opaque binary string
        """

        return Binary("".join([pack("B", b) for b in array]))

    def _Reduce(self, x):

        """
        Private Function _Reduce
        Reduce the amplitude and truncate to integer

        Seismological data goes from 0 to -255
        Infrasound data goes from 100 to -155
        """

        x = int(x)

        if -255 <= x and x <= 0:
            return int(x + 255)
        else:
            return 255

    def _GetOffset(self, segment, mask):

        """
        Private Function _GetOffset
        Detects the first frequency and uses this offset
        """

        # Determine the first occurrence of True
        # from the Boolean mask, this will be the offset
        counter = 0
        for boolean in mask:
            if not boolean:
                counter += 1
            else:
                return [counter - 1] + [self._Reduce(x) for x in segment]

    def GetInventory(self, filestream):

        """
        Public Property Inventory
        Returns the stream inventory from cache or FDSN webservice
        """

        # Check if the inventory is cached
        if filestream.id not in self.INVENTORY_CACHE:

            # Attempt to get the inventory from the FDSN webservice
            inventory = read_inventory(filestream.FDSNXMLQuery)

            # Set the cache
            self.INVENTORY_CACHE[filestream.id] = inventory

        return self.INVENTORY_CACHE[filestream.id]
