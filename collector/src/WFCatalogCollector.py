"""
WFCatalog Collector and Synchronization

Authors:
  @ Luca Trani (trani@knmi.nl) 2014
  @ Mathijs Koymans (koymans@knmi.nl) 2016


[CONFIG]
  Option description from config.json

  ARCHIVE: Archive name
  PUBLISHER: Quality metric published
  STRUCTURE: structure (ODC or SDS or SDSbynet). SDS is default and used by all nodes except the ODC. Used to find files.
  MONGO:
    ENABLED: (true | false) spits metrics to stdout (false) or database (true)
    DB_HOST: Host of Mongo database.
    DB_NAME: Name of database.
    ALLOW_DOUBLE: (true | false) if true, can insert multiple documents withe same file ID (unique Net, Sta, Cha, Loc, Day)
  ARCHIVE_ROOT: Root of the archive (e.g. "/path/to/archive/SDS/"). The following subdirectories are the archived years.
  DEFAULT_LOG_FILE: Path to log for writing.
  FILTERS:
    WHITE: Array of strings used for fnmatch (default ["*"] for everything)
    BLACK: Array of strings used for fnmatch (has precedent over white list)

[USAGE]
  The provided class collects new and synchronizes waveform metadata and
  can be called through the command line or by importing the WFCatalogCollector class

  -------------------------------------------------------------------

  Through an import:

  options are identical to the flags described below and
  passed as {'key': value} pairs in a dictionary. E.g.:

    > from WFCatalogCollector.py import WFCatalogCollector
    > mmc = WFCatalogCollector(logfile)
    > mmc.process({'dir': '/PATH/TO/FILES', 'csegs': True, 'flags': True})

  Through the CMD line:

    > python WFCatalogCollector.py --dir {/PATH/TO/FILES} --csegs --flags --logfile {logfile}

  Giving the --update flag does a checksum change detection on
  all input files. The documents in the database that are dependent
  on the changed files are removed, reprocessed, and inserted. Updating
  does NOT insert any new files in the directory.

  An update can be forced by giving --update which skips the checksum change'exampleson and reprocesses all files.
  Giving --past {day, yesterday, week, fortnight, month} will reprocess the files in
  the specified window.


[FLAGS]

  ### Boolean flags
  [--update] start synchronization on input files with changes
  [--force] forces synchronization on all input files
  [--csegs] include continuous segments
  [--flags] include miniseed header percentages, timing correction, and timing quality
  [--hourly] include hourly granules

  [--config] show Collector configuration
  [--version] show Collector version

  ### File input options
  [--dir $DIR] all files in this directory are processed
  [--file $FILE] process a specific file
  [--list $ARRAY] Array of files to be processed
  [--past $ENUM] files in date range matching this criteria will be processed {today, yesterday, week, fortnight, month}

  ### Other flags
  [--logfile] specify a custom logfile
  [--stdout]  outpurs everything to stdout
"""

import os
import json
import logging
import argparse
import datetime
import hashlib
import sys
import fnmatch
import glob
import re
import importlib.metadata
from logging.handlers import TimedRotatingFileHandler

from src.config import CONFIG
from src.db import MongoDatabase
from src import archive
from src import metrics
from src import mapping


class WFCatalogCollector:
    """
    WFCatalogCollector class for ingesting waveform metadata
    """

    def __init__(self, logfile=None, to_stdout=False):
        """
        WFCatalogCollector.__init__
        > initialize the class, set up logger and database connection
        """
        self.mongo = MongoDatabase()
        self._setupLogger(logfile, to_stdout)
        # Show configuration and exit

    def _setOptions(self, user_options):
        """
        WFCatalogCollector._setOptions
        > returns default options for the Collector
        > and replaces with user options given
        > through JSON dictionary
        """

        # Standard options
        default_options = {
            "range": 1,
            "file": None,
            "dir": None,
            "glob": None,
            "list": None,
            "past": None,
            "date": None,
            "csegs": False,
            "flags": False,
            "hourly": False,
            "delete": False,
            "update": False,
            "force": False,
            "config": False,
        }

        # Loop over user options and replace any default options
        for key in user_options:
            default_options[key] = user_options[key]

        self.args = default_options

        # Check if there is a single input method
        nInput = 6 - [
            self.args["date"],
            self.args["file"],
            self.args["dir"],
            self.args["list"],
            self.args["past"],
            self.args["glob"],
        ].count(None)
        if nInput == 0:
            raise Exception("No input was given")
        if nInput > 1:
            raise Exception("Multiple file inputs were given; aborting")

        if not CONFIG["MONGO"]["ENABLED"] and self.args["update"]:
            raise Exception("Cannot update files when database connection is disabled")

        self._printArguments()
        self._setGranularity()

    def process(self, options):
        """
        WFCatalogCollector.process
        > processes data with options
        """

        # This could be done elswhere but this is the most simple way for now
        if "config" in options and options["config"]:
            self.showConfig()
            sys.exit(0)

        self.timeInitialized = datetime.datetime.now()

        # Attempt connection to the database
        if not self.mongo._connected:
            if CONFIG["MONGO"]["ENABLED"]:
                try:
                    self.mongo._connect()
                    self.log.info("Connection to the database has been established")
                except Exception as ex:
                    self.log.critical("Could not establish connection to the database")
                    sys.exit(0)
            else:
                self.log.info("Connection to the database is disabled")

        self._setOptions(options)

        # 1. Get files for processing,
        # 2. filter them,
        # 3. process them
        self._getFiles()
        self._filterFiles()

        # Delete or process files
        if self.args["delete"]:
            self._deleteFiles()
        else:
            self._processFiles()

        self.log.info(
            "WFCollector synchronization completed in %s."
            % (datetime.datetime.now() - self.timeInitialized)
        )

    def _deleteFiles(self):
        """
        WFCatalogCollector._deleteFiles
        Removes files from database
        """

        update_files = []

        for file in self.files:
            # Set update for dependents on the file to be deleted
            for documents in self.mongo.getDailyFilesById(file):
                # Make sure to not update self or any file included in deletion
                if archive.getFullPath(documents["fileId"]) not in self.files:
                    self.log.info(
                        "Stage dependent file for update %s" % documents["fileId"]
                    )
                    update_files.append(archive.getFullPath(documents["fileId"]))

            # Remove the document
            for document in self.mongo.getDocumentByFilename(file):
                try:
                    mongo_id = document["_id"]
                    self.mongo.removeDocumentsById(mongo_id)
                    self.log.info(
                        "Succesfully removed document related to id %s." % mongo_id
                    )
                except Exception as ex:
                    self.log.error("Could not remove documents with id %s." % mongo_id)
                    self.log.exception(ex)

        # Set some variables and process the files to be updated
        self.files = update_files
        self.totalFiles = len(self.files)
        self._processFiles()

    def _processFiles(self):
        """
        WFCatalogCollector._processFiles
        > Loop over all files added to the class
        """

        for file in self.files:
            fileStart = datetime.datetime.now()

            self.log.info("Starting processing file %s", file)

            try:
                self._collectMetadata(file)
            except Exception as ex:
                self.log.error("Could not compute metadata")
                self.log.error(ex)
                continue

            self.log.info(
                "Completed processing file in %s"
                % (datetime.datetime.now() - fileStart)
            )

    def _passFilter(self, filename):
        """
        WFCatalogCollector._passFilter
        > Checks if filename matches a white/black list
        > the blacklist had precedence over the whitelist
        """

        for white_filter in CONFIG["FILTERS"]["WHITE"]:
            # Match in the whitelist
            if fnmatch.fnmatch(filename, white_filter):
                # Check if overruled by blacklist
                for black_filter in CONFIG["FILTERS"]["BLACK"]:
                    # Overruled, file is blacklisted
                    if fnmatch.fnmatch(filename, black_filter):
                        return False

                # Not overruled, file is whitelisted
                return True

        # Default to false, not white listed so ignore
        return False

    def _setupLogger(self, logfile, to_stdout):
        """
        WFCatalogCollector._setupLogger
        > logging setup for the WFCatalog Collector
        """

        # Set up WFCatalogger

        if CONFIG["DEFAULT_LOG_FILE"] is not None:
            self.log = logging.getLogger("WFCatalog Collector")
            log_file = logfile or CONFIG["DEFAULT_LOG_FILE"]
            self.file_handler = TimedRotatingFileHandler(log_file, when="midnight")
            self.file_handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
            self.log.addHandler(self.file_handler)
        else:
            logging.basicConfig(
                level=logging.INFO,
                stream=sys.stdout,
                format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            )
            self.log = logging.getLogger("WFCatalog Collector")

    def _printArguments(self):
        """
        WFCatalogCollector._printArguments
        > neatly prints some of the init settings
        """

        if self.args["force"] and not self.args["update"]:
            raise Exception("Only catalog updates can be forced. Give --update --force")

        self.log.info("Begin collection of new waveform metadata.")

        if self.args["update"]:
            self.log.info("Begin updating of waveform documents in database")

        if self.args["force"]:
            self.log.info("Update is being forced")

    def _getWindow(self):
        """
        WFCatalogCollector._getWindow
        > returns window for given --past option
        """
        # Set the day tuple window for reprocessing [inclusive, exclusive)
        if self.args["past"] == "day":
            window = (0, 1)
        elif self.args["past"] == "yesterday":
            window = (1, 2)
        elif self.args["past"] == "week":
            window = (1, 8)
        elif self.args["past"] == "fortnight":
            window = (1, 15)
        elif self.args["past"] == "month":
            window = (1, 32)

        return window[0], window[1]

    def _getPastFiles(self):
        """
        WFCatalogCollector._getPastFiles
        > returns files from today, yesterday, last week,
        > last two weeks, or last month
        """

        now = datetime.datetime.now()
        start, end = self._getWindow()

        # Loop over the window and collect files
        pastFiles = []
        for day in range(start, end):
            pastFiles += archive.collectFilesFromDate(now - datetime.timedelta(days=day))

        return pastFiles

    def _getFiles(self):
        """
        WFCatalogCollector._getFiles
        reads all files from a given input directory
        """

        self.file_counter = 0

        # Past was given, collect files from the past
        if self.args["past"]:
            self.files = self._getPastFiles()
            self.log.info(
                "Collected %d file(s) from the past %s"
                % (len(self.files), self.args["past"])
            )

        # List was given
        elif self.args["list"]:
            self.files = json.loads(self.args["list"])
            # When deleting, the files may already be gone from the archive
            if not self.args["delete"]:
                self.files = [f for f in self.files if os.path.isfile(f)]
            self.log.info("Collected %d file(s) from list" % len(self.files))

        # Raise if an invalid input directory is given
        elif self.args["dir"]:
            if not os.path.isdir(self.args["dir"]):
                raise Exception("Input is not a valid directory on the file system.")

            # Collect all the files (recursively) from a directory and add them
            self.files = [
                os.path.join(root, f)
                for root, dirs, files in os.walk(self.args["dir"])
                for f in files
                if os.path.isfile(os.path.join(root, f))
            ]
            self.log.info(
                "Collected %d file(s) from directory %s"
                % (len(self.files), self.args["dir"])
            )

        # If globbing match all files
        elif self.args["glob"]:
            self.files = glob.glob(self.args["glob"])
            self.files = [f for f in self.files if os.path.isfile(f)]

        # Single file as input
        elif self.args["file"]:
            # When deleting, the file may already be gone from the archive
            if not self.args["delete"] and not os.path.isfile(self.args["file"]):
                raise Exception("Argument --file requires a valid file.")

            self.files = [self.args["file"]]
            self.log.info("Collected file %s" % (self.args["file"]))

        # Specific date as input (with optional range)
        elif self.args["date"]:
            self.files = []
            # Date type 2019-01-01
            if re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", self.args["date"]):
                specific_date = datetime.datetime.strptime(
                    self.args["date"], "%Y-%m-%d"
                )
            # Date type 2019-001
            elif re.match(r"^[0-9]{4}-[0-9]{3}$", self.args["date"]):
                specific_date = datetime.datetime.strptime(self.args["date"], "%Y-%j")
            else:
                raise ValueError("Invalid date specification: %s" % self.args["date"])
            n_days = int(self.args["range"])
            # Include a given range (default to 1)
            for day in range(abs(n_days)):
                if n_days > 0:
                    self.files += archive.collectFilesFromDate(
                        specific_date + datetime.timedelta(days=day)
                    )
                else:
                    self.files += archive.collectFilesFromDate(
                        specific_date - datetime.timedelta(days=day)
                    )
            self.log.info(
                "Collected %d file(s) from date %s +%d days"
                % (len(self.files), self.args["date"], n_days)
            )

        # Raise on no input
        else:
            raise Exception(
                "Input is empty. Use --dir, --file, or --list to specify a directory, file, or list of files to process."
            )

    def _validateFilters(self):
        """
        WFCatalogCollector._validateFilters
        > sanity checks the filters in the config.json
        """
        if len(CONFIG["FILTERS"]["WHITE"]) == 0:
            raise Exception(
                'The whitelist is empty. If you wish to include all files add "*"'
            )

    def _filterFiles(self):
        """
        WFCatalogCollector._filterFiles
        > Check if we wish to update the documents
        > If not updating, documents that already exist in the database are skipped
        > Documents are identified by filename
        """
        # Validate the white and black list
        self._validateFilters()

        self.files = [f for f in self.files if self._passFilter(os.path.basename(f))]

        # Return immediately if deleting
        if self.args["delete"]:
            return

        # Get the new files from the directory that are not in the database
        new_files = [file for file in self.files if self._isNewDocument(file)]
        self.log.info("Discovered %d new file(s) for processing" % (len(new_files)))

        # If we are updating, remove old documents and add changed document to the process list
        if self.args["update"]:
            changed_files = self._getChangedFiles()
            if self.args["force"]:
                self.log.info(
                    "Forcing update of %d file(s) in database" % (len(changed_files))
                )
            else:
                self.log.info(
                    "Discovered %d file(s) with changed checksum in database"
                    % (len(changed_files))
                )
        else:
            changed_files = []

        # Files to process is new + changed (when updating)
        self.files = set(new_files + changed_files)
        self.log.info("Begin processing of %d file(s)" % (len(self.files)))

        self.totalFiles = len(self.files)

        if self.totalFiles == 0:
            self.log.info("No files for processing: doing nothing.")
            sys.exit(0)

    def _getChangedFiles(self):
        """
        WFCatalogCollector._getChangedFiles
        > compares checksums in database against files in a directory
        """

        changedFiles = []

        if self.args["force"]:
            self.log.info("Updating: forcing checksum change for database documents")
        else:
            self.log.info(
                "Updating: start change detection through checksums of database documents"
            )

        # Go over all the files in the input
        for file in self.files:
            # Get the documents that depend on this file
            # under document.files
            for document in self.mongo.getDailyFilesById(file):
                # The document update is forced
                # We must update every document that depends on the file
                if self.args["force"]:
                    self.log.info("Forcing update on %s" % document["fileId"])
                    changedFiles.append(document["fileId"])
                    continue

                # Loop over all the used files
                for used_files in document["files"]:
                    # If not forcing, just check the MD5 hash of the
                    # actual passed file, and the MD5 hash in the database
                    if used_files["name"] != os.path.basename(file):
                        continue

                    self.log.info("Comparing MD5checksums for %s" % used_files["name"])

                    fullPath = archive.getFullPath(os.path.basename(file))
                    MD5Hash = self._getMD5Hash(fullPath)

                    # Compare the checksum
                    if MD5Hash != used_files["chksm"]:
                        self.log.info(
                            "Detected MD5checksum change for %s" % used_files["name"]
                        )
                        self.log.info(
                            "Adding file %s for updating" % document["fileId"]
                        )
                        changedFiles.append(document["fileId"])

        return list(set([archive.getFullPath(filename) for filename in changedFiles]))

    def _isNewDocument(self, file):
        """
        WFCatalogCollector._isNewDocument
        > check if daily stream with given filename
        > does not exist in the database. If double is allowed
        > this check is skipped.
        """

        if not CONFIG["MONGO"]["ENABLED"]:
            return True
        elif CONFIG["MONGO"]["ALLOW_DOUBLE"]:
            return True
        else:
            return self.mongo.countDocumentsByFilename(file) == 0

    def _collectMetadata(self, file):
        """
        WFCatalogCollector._collectMetadata
        > collects the metadata from the ObsPy mseedMetadata class
        """
        self.file_counter += 1

        if not os.path.isfile(file):
            self.log.info("File no longer exists in archive %s" % file)
            return

        # Get the neighbouring files and windows for a given file
        try:
            fas = self._collectFilesAndSegments(file)
        except Exception as ex:
            self.log.error("Could not get neighbouring files")
            self.log.error(ex)
            return

        # Get the daily granulated waveform metadata
        try:
            granule = fas["segments"]["daily"]
            daily_meta = metrics.computeMetadata(
                fas["files"], granule["start"], granule["end"], "daily",
                self.args["flags"], self.args["csegs"],
            )
            daily_meta.update({"fileId": os.path.basename(file)})
        except Exception as ex:
            self.log.error(
                "Could not get daily metadata for %s" % os.path.basename(file)
            )
            self.log.error(ex)
            return

        # Get the hourly granulated waveform metadata
        hourly_meta_array = []
        for granule in fas["segments"]["hourly"]:
            try:
                hourly_meta = metrics.computeMetadata(
                    fas["files"], granule["start"], granule["end"], "hourly",
                    self.args["flags"], self.args["csegs"],
                )
                hourly_meta.update({"fileId": os.path.basename(file)})
                hourly_meta_array.append(hourly_meta)
            except Exception as ex:
                if str(ex) != "No data within the temporal constraints.":
                    self.log.error(
                        "Could not get hourly metadata for %s" % os.path.basename(file)
                    )
                    self.log.error(ex)

        # Store the documents
        self._storeOutput({"daily": daily_meta, "hourly": hourly_meta_array})

    def _storeOutput(self, documents):
        """
        WFCatalog._storeOutput
        > stores documents to MongoDB though
        > the MongoDatabase() class
        """

        # If a database is not connected throw to stdout
        if not CONFIG["MONGO"]["ENABLED"]:
            print({"daily": documents["daily"], "hourly": documents["hourly"]})
            self.log.info("Succesfully printed metrics to stdout")
            return

        # When updating, make sure we remove the previous document
        if self.args["update"] or self.args["delete"]:
            try:
                for document in self.mongo.getDocumentByFilename(
                    documents["daily"]["fileId"]
                ):
                    mongo_id = document["_id"]
                    self.mongo.removeDocumentsById(mongo_id)
                    self.log.info(
                        "Succesfully removed document related to id %s." % mongo_id
                    )
            except Exception as ex:
                self.log.error("Could not remove documents with id %s." % mongo_id)
                self.log.exception(ex)
                return

        # Final check and quit if the document with this fileId
        # is already in the database
        if not self._isNewDocument(documents["daily"]["fileId"]):
            self.log.error(
                "Stop: document with this id is already in the database: %s"
                % documents["daily"]["fileId"]
            )
            return

        # Store the daily output and get the parentID
        try:
            qc_metadata_daily = mapping.getDatabaseKeyMap(
                documents["daily"], None, self.args["flags"]
            )
            qc_metadata_daily.update(self._getFileChecksums(documents["daily"]["files"]))
            id = self.mongo._storeGranule(qc_metadata_daily, "daily")
            self.log.info("Succesfully stored daily granule %s" % id.inserted_id)
        except Exception as ex:
            self.log.error("Could not store daily granule document to database")
            self.log.exception(ex)
            return

        # Store the hourly output
        if self.args["hourly"]:
            for i, granule in enumerate(documents["hourly"]):
                try:
                    qc_metadata = mapping.getDatabaseKeyMap(
                        granule, id.inserted_id, self.args["flags"]
                    )
                    qc_metadata.update(self._getFileChecksums(granule["files"]))
                    self.mongo._storeGranule(qc_metadata, "hourly")
                    self.log.info(
                        "[%d/%d] Succesfully stored hourly granule"
                        % (i + 1, len(documents["hourly"]))
                    )
                except Exception as ex:
                    self.log.error(
                        "Could not store hourly granule document to database"
                    )
                    self.log.exception(ex)

        # Store continuous segments if the metadata is not continuous
        if self.args["csegs"] and not qc_metadata_daily["cont"]:
            for segment in documents["daily"]["c_segments"]:
                try:
                    qc_metadata = mapping.getDatabaseKeyMapContinuous(
                        segment, id.inserted_id
                    )
                    self.mongo.storeContinuousSegment(qc_metadata)
                except Exception as ex:
                    self.log.exception("Could not store continuous segment to database")
            self.log.info(
                "Succesfully stored %d continuous segment(s) to database"
                % len(documents["daily"]["c_segments"])
            )

    def _getFileChecksums(self, files):
        """
        WFCatalogCollector._getFileChecksums
        returns files and checksums from the trace
        """

        if CONFIG["ENABLE_DUBLIN_CORE"]:
            return {
                "files": [
                    {
                        "do": self._getFileDataObject(f),
                        "name": os.path.basename(f),
                        "chksm": self._getMD5Hash(f),
                    }
                    for f in files
                ]
            }
        else:
            return {
                "files": [
                    {"name": os.path.basename(f), "chksm": self._getMD5Hash(f)}
                    for f in files
                ]
            }

    def _getFileDataObject(self, file):
        """
        WFCatalogCollector._getFileDataObject
        Get the id of the data object or store a new one
        """

        # If the extension exists in the table
        for document in self.mongo.getFileDataObject(file):
            return document["_id"]

        # Otherwise create it
        return self.mongo._storeFileDataObject(self._createDataObject(file))

    def _createDataObject(self, file):
        """
        WFCatalogCollector._createDataObject
        function to create additional/alternate metadata
        """

        # Create data object literal with additional metadata
        # !!! MODIFY !!!
        document = {
            "fileId": os.path.basename(file),
            "dc:identifier": "actionable pid",
            "dc:title": "title",
            "dc:subject": "mSEED, waveform, quality",
            "dc:creator": CONFIG["ARCHIVE"],
            "dc:contributor": "network operator",
            "dc:publisher": CONFIG["PUBLISHER"],
            "dc:type": "seismic waveform",
            "dc:format": "MSEED",
            "dc:date": datetime.datetime.now(),
            "dc:coverage": "cov_id",
            "dcterms:available": "available from now",
            "dcterms:dateAccepted": datetime.datetime.now(),
            "dc:rights": "open access",
            "dcterms:isPartOf": "wfmetadata_id",
        }

        return document

    def _getMD5Hash(self, f):
        """
        WFCatalogCollector._getMD5Hash
        > Method to generate md5 hashes used
        > for the checksum field
        """
        try:
            BLOCKSIZE = 65536
            hasher = hashlib.md5()
            with open(f, "rb") as afile:
                buf = afile.read(BLOCKSIZE)
                while len(buf) > 0:
                    hasher.update(buf)
                    buf = afile.read(BLOCKSIZE)
        except Exception as ex:
            self.log.error(ex)
            return None

        return hasher.hexdigest()

    def _setGranularity(self):
        """
        WFCatalogCollector._setGranularity
        > Set the granularity
        """

        # For daily granularity take steps of 24h
        self.gran = 1 if self.args["hourly"] else 24

    def _getFileSegments(self, file):
        """
        WFCatalogCollector._getFileSegments
        > returns the start & end time of segments to a given granularity
        > segment for a full day is returned automatically, hourly is optional
        """

        # Get the daily segment
        start_time = archive.getDateFromFile(file)
        end_time = start_time + datetime.timedelta(days=1)

        daily = {"start": start_time, "end": end_time}

        # Extend with requested hourly granularity
        # Taking 1h steps
        hourly = []
        if self.args["hourly"]:
            while start_time < end_time:
                segment_end = start_time + datetime.timedelta(hours=self.gran)
                hourly.append({"start": start_time, "end": segment_end})
                start_time = segment_end

        return {"daily": daily, "hourly": hourly}

    def showConfig(self):
        """
        WFCatalogCollector.showConfig
        > dumps script configuration to screen
        """

        print(json.dumps(CONFIG, indent=2))

    def _collectFilesAndSegments(self, file):
        """
        WFCatalogCollector._collectFilesAndSegments
        > collects neighbouring files and time windows for which metadata is calculated
        """

        day_files = []

        # Append three files to array in order [yesterday, today, tomorrow]
        # Get yesterdays file
        previous_file = archive.getNextFile(file, -1)
        if os.path.isfile(previous_file):
            day_files.append(previous_file)

        # Add todays file
        day_files.append(file)

        # Get tomorrows file
        next_file = archive.getNextFile(file, 1)
        if os.path.isfile(next_file):
            day_files.append(next_file)

        self.log.info(
            "[%d/%d] File %s prepared with %s"
            % (
                self.file_counter,
                self.totalFiles,
                os.path.basename(file),
                [os.path.basename(f) for f in day_files],
            )
        )

        return {"files": day_files, "segments": self._getFileSegments(file)}



if __name__ == "__main__":
    # Parse cmd line arguments
    parser = argparse.ArgumentParser(
        description="Processes mSEED files and ingests waveform metadata to a Mongo repository."
    )

    # Input file options
    parser.add_argument("--dir", help="directory containing the files to process")
    parser.add_argument("--file", help="specific file to be processed")
    parser.add_argument("--glob", help="glob expression for files to be processed")
    parser.add_argument(
        "--list", help='specific list of files to be processed ["file1", "file2"]'
    )
    parser.add_argument(
        "--past",
        help="process files in a specific range in the past",
        choices=["day", "yesterday", "week", "fortnight", "month"],
        default=None,
    )
    parser.add_argument(
        "--date", help="process files for a specific date", default=None
    )
    parser.add_argument(
        "--range", help="number of days after a specific date", default=1
    )

    # Options to show config/versioning
    parser.add_argument(
        "--config",
        help="view configuration options",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=importlib.metadata.version("wfcatalog-collector"),
    )

    # Add flags and continuous segments
    parser.add_argument(
        "--flags", help="include mSEED header flags in result", action="store_true"
    )
    parser.add_argument(
        "--csegs", help="include continuous segments in result", action="store_true"
    )
    parser.add_argument(
        "--hourly", help="include hourly granules in result", action="store_true"
    )

    # Set custom logfile
    parser.add_argument("--logfile", help="set custom logfile")
    parser.add_argument(
        "--stdout",
        help="outputs all logs to stdout",
        default=False,
        action="store_true",
    )

    # Options to update documents existing in the database, normally
    # files that are already processed are skipped
    # Updates can be forced (without checksum check)
    parser.add_argument(
        "--update",
        help="update existing documents in the database",
        action="store_true",
    )
    parser.add_argument("--force", help="force file updates", action="store_true")
    parser.add_argument(
        "--delete", help="delete files from database", action="store_true"
    )

    # Get parsed arguments as a JSON dict to match
    # compatibility with an imported class
    args = vars(parser.parse_args())

    WFCollector = WFCatalogCollector(args["logfile"], to_stdout=args["stdout"])

    WFCollector.process(args)
