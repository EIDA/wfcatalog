"""
WFCatalog Collector and Synchronization

Authors:
  @ Luca Trani (trani@knmi.nl) 2014
  @ Mathijs Koymans (koymans@knmi.nl) 2016


[CONFIG]
  Option description from config.json

  VERSION: Running version of the WFCatalog Collector
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
from __future__ import print_function

import os
import json
import logging
import argparse
import datetime
import hashlib
import warnings
import sys
import fnmatch
import signal
import glob

def handler(signum, frame):
  raise Exception("Metric calculation has timed out")

from logging.handlers import TimedRotatingFileHandler

# ObsPy mSEED-QC is required
try:
  from obspy.signal.quality_control import MSEEDMetadata
except ImportError as ex:
  raise ImportError('Failure to load MSEEDMetadata; ObsPy mSEED-QC is required.')

# Load configuration from JSON
cfg_dir = os.path.dirname(os.path.realpath(__file__))
with open(os.path.join(cfg_dir, 'config.json'), "r") as cfg:
  CONFIG = json.load(cfg)

if CONFIG['MONGO']['ENABLED']:
  from pymongo import MongoClient

if CONFIG['STRUCTURE'] == 'SDSbynet':
  #SDSbynet structure starts with an extended network code.
  # so we need to add the ability to extend a network code
  from fdsnnetextender import FdsnNetExtender
  fne = FdsnNetExtender()

class WFCatalogCollector():
  """
  WFCatalogCollector class for ingesting waveform metadata
  """

  def __init__(self, logfile=None):
    """
    WFCatalogCollector.__init__
    > initialize the class, set up logger and database connection
    """
    self.mongo = MongoDatabase()
    self._setupLogger(logfile)


  def _setOptions(self, user_options):
    """
    WFCatalogCollector._setOptions
    > returns default options for the Collector
    > and replaces with user options given
    > through JSON dictionary
    """

    # Standard options
    default_options = {
      'range': 1,
      'file': None,
      'dir': None,
      'glob': None,
      'list': None,
      'past': None,
      'date': None,
      'csegs': False,
      'flags': False,
      'hourly': False,
      'delete': False,
      'update': False,
      'force': False,
      'config': False,
      'version': False,
    }

    # Loop over user options and replace any default options
    for key in user_options:
      default_options[key] = user_options[key]

    self.args = default_options

    # Check if there is a single input method
    nInput = 6 - [self.args['date'], self.args['file'], self.args['dir'], self.args['list'], self.args['past'], self.args['glob']].count(None)
    if nInput == 0:
      raise Exception("No input was given");
    if nInput > 1:
      raise Exception("Multiple file inputs were given; aborting")

    if not CONFIG['MONGO']['ENABLED'] and self.args['update']:
      raise Exception("Cannot update files when database connection is disabled")

    # Show configuration and exit
    if self.args['config']:
      self.showConfig(); sys.exit(0)
    if self.args['version']:
      self.showVersion(); sys.exit(0)

    self._printArguments()
    self._setGranularity()


  def showVersion(self):
    """
    WFCatalog.showVersion
    > shows current Collector version
    """
    print(CONFIG["VERSION"])
 

  def process(self, options):
    """
    WFCatalogCollector.process
    > processes data with options
    """

    self.timeInitialized = datetime.datetime.now()

    # Attempt connection to the database
    if not self.mongo._connected:
      if CONFIG['MONGO']['ENABLED']:
        try:
          self.mongo._connect()
          self.log.info("Connection to the database has been established")
        except Exception as ex:
          self.log.critical("Could not establish connection to the database"); sys.exit(0)
      else:
        self.log.info("Connection to the database is disabled");

    self._setOptions(options)

    # 1. Get files for processing,
    # 2. filter them,
    # 3. process them
    self._getFiles()
    self._filterFiles()

    # Delete or process files
    if self.args['delete']:
      self._deleteFiles()
    else:
      self._processFiles()

    self.log.info("WFCollector synchronization completed in %s." % (datetime.datetime.now() - self.timeInitialized))
      

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
        if self._getFullPath(documents["fileId"]) not in self.files:
          self.log.info("Stage dependent file for update %s" % documents["fileId"])
          update_files.append(self._getFullPath(documents["fileId"]))

      # Remove the document
      for document in self.mongo.getDocumentByFilename(file):
           
        try:
          mongo_id = document['_id']
          self.mongo.removeDocumentsById(mongo_id)
          self.log.info("Succesfully removed document related to id %s." % mongo_id)
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

      self.log.info("Completed processing file in %s" % (datetime.datetime.now() - fileStart))


  def _passFilter(self, filename):
    """
    WFCatalogCollector._passFilter
    > Checks if filename matches a white/black list
    > the blacklist had precedence over the whitelist
    """

    for white_filter in CONFIG['FILTERS']['WHITE']:
      # Match in the whitelist
      if fnmatch.fnmatch(filename, white_filter):
        # Check if overruled by blacklist
        for black_filter in CONFIG['FILTERS']['BLACK']:
          # Overruled, file is blacklisted
          if fnmatch.fnmatch(filename, black_filter):
            return False

        # Not overruled, file is whitelisted
        return True

    # Default to false, not white listed so ignore
    return False


  def _setupLogger(self, logfile):
    """
    WFCatalogCollector._setupLogger
    > logging setup for the WFCatalog Collector
    """

    # Set up WFCatalogger
    self.log = logging.getLogger('WFCatalog Collector')
    self.log.setLevel(logging.INFO)

    if self.args['stdout']:
      # Log everything to standard output
      handler = logging.StreamHandler(sys.stdout)
      handler.setLevel(logging.INFO)
      formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
      handler.setFormatter(formatter)
      self.log.addHandler(handler)

    else:
      log_file = logfile or CONFIG['DEFAULT_LOG_FILE']
      self.file_handler = TimedRotatingFileHandler(log_file, when="midnight")
      self.file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
      self.log.addHandler(self.file_handler)


  def _printArguments(self):
    """
    WFCatalogCollector._printArguments
    > neatly prints some of the init settings
    """

    if self.args['force'] and not self.args['update']:
      raise Exception("Only catalog updates can be forced. Give --update --force")

    self.log.info("Begin collection of new waveform metadata.")

    if self.args['update']:
      self.log.info("Begin updating of waveform documents in database")

    if self.args['force']:
      self.log.info("Update is being forced")

   

  def _getWindow(self):
    """
    WFCatalogCollector._getWindow
    > returns window for given --past option
    """
    # Set the day tuple window for reprocessing [inclusive, exclusive)
    if self.args['past'] == 'day':
      window = (0, 1)
    elif self.args['past'] == 'yesterday':
      window = (1, 2)
    elif self.args['past'] == 'week':
      window = (1, 8)
    elif self.args['past'] == 'fortnight':
      window = (1, 15)
    elif self.args['past'] == 'month':
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
      pastFiles += self._collectFilesFromDate(now - datetime.timedelta(days=day))

    return pastFiles


  def _collectFilesFromDate(self, date):
    """
    WFCatalogCollector._collectFilesFromDate
    > collects the files for a given year and day
    """

    # Get the year & day of year
    jday = date.strftime("%j")
    year = date.strftime("%Y")

    # ODC directory structure makes it simple to loop over years and days
    if CONFIG['STRUCTURE'] == 'ODC':
      directory = os.path.join(CONFIG['ARCHIVE_ROOT'], year, jday)
      collectedFiles = [os.path.join(directory, f) for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]

    # SDS structure is slightly more complex, loop over all directories
    # in a year and extract files ending with a given jday
    elif CONFIG['STRUCTURE'] == 'SDS':
      collectedFiles = []
      directory = os.path.join(CONFIG['ARCHIVE_ROOT'], year)
      for subdir, dirs, files in os.walk(directory, followlinks=True):
        for file in files:
          if file.endswith(jday) and os.path.isfile(os.path.join(subdir, file)):
            collectedFiles.append(os.path.join(subdir, file))

    # SDSbynet structure is slightly more complex, loop over all network directories
    # in a year and extract files ending with a given jday
    elif CONFIG['STRUCTURE'] == 'SDSbynet':
      collectedFiles = []
      # First, loop over all networks
      for netdir in next(os.walk(CONFIG['ARCHIVE_ROOT']))[1]:
          # Then find all files
          for subdir, dirs, files in os.walk(os.path.join(CONFIG['ARCHIVE_ROOT'], netdir, year), followlinks=True):
            for file in files:
              if file.endswith(jday) and os.path.isfile(os.path.join(subdir, file)):
                collectedFiles.append(os.path.join(subdir, file))
    
    else:
      raise Exception("WFCatalogCollector.getFilesFromDirectory: unknown directory structure.")

    return collectedFiles


  def _getFiles(self):
    """
    WFCatalogCollector._getFiles
    reads all files from a given input directory
    """

    self.file_counter = 0

    # Past was given, collect files from the past
    if self.args['past']:
      self.files = self._getPastFiles()
      self.log.info("Collected %d file(s) from the past %s" % (len(self.files), self.args['past']))

    # List was given
    elif self.args['list']:
      self.files = [f for f in json.loads(self.args['list']) if os.path.isfile(f)]
      self.log.info("Collected %d file(s) from list" % len(self.files))

    # Raise if an invalid input directory is given
    elif self.args['dir']:
      if not os.path.isdir(self.args['dir']):
        raise Exception("Input is not a valid directory on the file system.")

      # Collect all the files (recursively) from a directory and add them
      self.files = [os.path.join(root, f) for root, dirs, files in os.walk(self.args['dir']) for f in files if os.path.isfile(os.path.join(root, f))]
      self.log.info("Collected %d file(s) from directory %s" % (len(self.files), self.args['dir']))

    # If globbing match all files
    elif self.args['glob']:
      self.files = glob.glob(self.args['glob'])
      self.files = [f for f in self.files if os.path.isfile(f)]

    # Single file as input
    elif self.args['file']:
      if not os.path.isfile(self.args['file']):
        raise Exception("Argument --file requires a valid file.")

      self.files = [self.args['file']]
      self.log.info("Collected file %s" % (self.args['file']))

    # Specific date as input (with optional range)
    elif self.args['date']:
      self.files = []
      specific_date = datetime.datetime.strptime(self.args['date'], "%Y-%m-%d")
      n_days = int(self.args['range'])
      # Include a given range (default to 1)
      for day in range(abs(n_days)):
        if n_days > 0:
          self.files += self._collectFilesFromDate(specific_date + datetime.timedelta(days=day))
        else:
          self.files += self._collectFilesFromDate(specific_date - datetime.timedelta(days=day))
      self.log.info("Collected %d file(s) from date %s +%d days" % (len(self.files), self.args['date'], n_days))

    # Raise on no input
    else:
      raise Exception("Input is empty. Use --dir, --file, or --list to specify a directory, file, or list of files to process.")


  def _validateFilters(self):
    """
    WFCatalogCollector._validateFilters
    > sanity checks the filters in the config.json
    """
    if len(CONFIG['FILTERS']['WHITE']) == 0:
      raise Exception('The whitelist is empty. If you wish to include all files add "*"')


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
    if self.args['delete']:
      return

    # Get the new files from the directory that are not in the database
    new_files = [file for file in self.files if self._isNewDocument(file)]
    self.log.info("Discovered %d new file(s) for processing" % (len(new_files)))

    # If we are updating, remove old documents and add changed document to the process list
    if self.args['update']:
      changed_files = self._getChangedFiles()
      if self.args['force']:
        self.log.info("Forcing update of %d file(s) in database" % (len(changed_files))) 
      else:
        self.log.info("Discovered %d file(s) with changed checksum in database" % (len(changed_files)))
    else:
      changed_files = []

    # Files to process is new + changed (when updating)
    self.files = set(new_files + changed_files)
    self.log.info("Begin processing of %d file(s)" % (len(self.files)))

    self.totalFiles = len(self.files)

    if self.totalFiles == 0:
      self.log.info("No files for processing: doing nothing."); sys.exit(0)


  def _getChangedFiles(self):
    """
    WFCatalogCollector._getChangedFiles
    > compares checksums in database against files in a directory
    """

    changedFiles = []

    if self.args['force']:
      self.log.info("Updating: forcing checksum change for database documents")
    else:
      self.log.info("Updating: start change detection through checksums of database documents")

    # Go over all the files in the input
    for file in self.files:
    
      # Get the documents that depend on this file
      # under document.files
      for document in self.mongo.getDailyFilesById(file): 

        # The document update is forced
        # We must update every document that depends on the file
        if self.args['force']:
          self.log.info("Forcing update on %s" % document["fileId"])
          changedFiles.append(document["fileId"])
          continue

        # Loop over all the used files
        for used_files in document['files']:

          # If not forcing, just check the MD5 hash of the
          # actual passed file, and the MD5 hash in the database
          if used_files["name"] != os.path.basename(file):
            continue

          self.log.info("Comparing MD5checksums for %s" % used_files['name'])
          
          fullPath = self._getFullPath(os.path.basename(file))
          MD5Hash = self._getMD5Hash(fullPath)

          # Compare the checksum
          if MD5Hash != used_files['chksm']:

            self.log.info("Detected MD5checksum change for %s" % used_files['name'])
            self.log.info("Adding file %s for updating" % document["fileId"])
            changedFiles.append(document["fileId"])
    
    return list(set([self._getFullPath(filename) for filename in changedFiles]))
     
      
  def _getFullPath(self, file):
    """
    WFCatalogCollector._getFullPath
    > returns full path based on the archive root directory
    > for file basename and directory stucture (config)
    """

    return self._getFileDirectory(self._getStatsObject(file))


  def _isNewDocument(self, file):
    """
    WFCatalogCollector._isNewDocument
    > check if daily stream with given filename
    > does not exist in the database. If double is allowed
    > this check is skipped.
    """

    if not CONFIG['MONGO']['ENABLED']:
      return True
    elif CONFIG['MONGO']['ALLOW_DOUBLE']:
      return True
    else:
      return self.mongo.getDocumentByFilename(file).count() == 0
      


  def _callObsPyMetadata(self, files, start, end, granule):
    """
    WFCatalogCollector._callObsPyMetadata
    wrapper function to call obspy.signal.MSEEDMetdata
    """

    # Throw an exception after the timeout (UNIX only)
    signal.signal(signal.SIGALRM, handler)
    signal.alarm(CONFIG['PROCESSING_TIMEOUT'])

    try:
      # Catch mSEED reading warnings
      with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')

        # Skip continuous segments for hourly granules
        if granule == 'daily':
          metadata = MSEEDMetadata(files, starttime=start, endtime=end, add_flags=self.args['flags'], add_c_segments=self.args['csegs'])
        elif granule == 'hourly':
          metadata = MSEEDMetadata(files, starttime=start, endtime=end, add_flags=self.args['flags'], add_c_segments=False)

        metadata.meta.update({'warnings': len(w) > 0})

    finally:
      # Disable alarm
      signal.alarm(0)

    return metadata.meta


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
      granule = fas['segments']['daily']
      daily_meta = self._callObsPyMetadata(fas['files'], granule['start'], granule['end'], 'daily')
      daily_meta.update({'fileId': os.path.basename(file)})
    except Exception as ex:
      self.log.error("Could not get daily metadata for %s" % os.path.basename(file)) 
      self.log.error(ex) 
      return

    # Get the hourly granulated waveform metadata
    hourly_meta_array = []
    for granule in fas['segments']['hourly']:
      try:
        hourly_meta = self._callObsPyMetadata(fas['files'], granule['start'], granule['end'], 'hourly')
        hourly_meta.update({'fileId': os.path.basename(file)})
        hourly_meta_array.append(hourly_meta)
      except Exception as ex:
        if(str(ex) != "No data within the temporal constraints."):
          self.log.error("Could not get hourly metadata for %s" % os.path.basename(file)) 
          self.log.error(ex) 

    # Store the documents
    self._storeOutput({
      'daily': daily_meta,
      'hourly': hourly_meta_array
    })


  def _storeOutput(self, documents):
    """
    WFCatalog._storeOutput
    > stores documents to MongoDB though 
    > the MongoDatabase() class
    """

    # If a database is not connected throw to stdout
    if not CONFIG['MONGO']['ENABLED']:
      print({
        'daily': documents['daily'],
        'hourly': documents['hourly']
      })
      self.log.info("Succesfully printed metrics to stdout")
      return

    # When updating, make sure we remove the previous document
    if self.args['update'] or self.args['delete']:
      try:
        for document in self.mongo.getDocumentByFilename(documents['daily']['fileId']):
          mongo_id = document['_id']
          self.mongo.removeDocumentsById(mongo_id)
          self.log.info("Succesfully removed document related to id %s." % mongo_id)
      except Exception as ex:
        self.log.error("Could not remove documents with id %s." % mongo_id)
        self.log.exception(ex)
        return

    # Final check and quit if the document with this fileId
    # is already in the database
    if not self._isNewDocument(documents['daily']['fileId']):
      self.log.error("Stop: document with this id is already in the database: %s" % documents['daily']['fileId'])
      return

    # Store the daily output and get the parentID
    try:
      qc_metadata_daily = self._getDatabaseKeyMap(documents['daily'], None)
      id = self.mongo._storeGranule(qc_metadata_daily, 'daily')
      self.log.info("Succesfully stored daily granule %s" % id)
    except Exception as ex:
      self.log.error("Could not store daily granule document to database")
      self.log.exception(ex)
      return

    # Store the hourly output
    if self.args['hourly']:
      for i, granule in enumerate(documents['hourly']):
        try:
          qc_metadata = self._getDatabaseKeyMap(granule, id)
          self.mongo._storeGranule(qc_metadata, 'hourly')
          self.log.info("[%d/%d] Succesfully stored hourly granule" % (i + 1, len(documents['hourly'])))
        except Exception as ex:
          self.log.error("Could not store hourly granule document to database")
          self.log.exception(ex)

    # Store continuous segments if the metadata is not continuous
    if self.args['csegs'] and not qc_metadata_daily['cont']:
      for segment in documents['daily']['c_segments']:
        try:
          qc_metadata = self._getDatabaseKeyMapContinuous(segment, id)
          self.mongo.storeContinuousSegment(qc_metadata)
        except Exception as ex:
          self.log.exception("Could not store continuous segment to database")
      self.log.info("Succesfully stored %d continuous segment(s) to database" % len(documents['daily']['c_segments']))


  def _getDatabaseKeyMapContinuous(self, trace, id):
    """
    WFCatalogCollector._getDatabaseKeyMapContinuous
    > Document parser for continuous segments
    """

    # Source object for a continuous segment
    source = {
      'streamId': id,
      'smin': int(trace['sample_min']),
      'smax': int(trace['sample_max']),
      'smean': float(trace['sample_mean']),
      'smedian': float(trace['sample_median']),
      'stdev': float(trace['sample_stdev']),
      'rms': float(trace['sample_rms']),
      'supper': float(trace['sample_upper_quartile']),
      'slower': float(trace['sample_lower_quartile']),
      'nsam': int(trace['num_samples']),
      'srate': float(trace['sample_rate']),
      'ts': trace['start_time'].datetime,
      'te': trace['end_time'].datetime,
      'slen': float(trace['segment_length'])
    }

    return source


  def _getDatabaseKeyMap(self, trace, id):
    """
    WFCatalogCollector._getDatabaseKeyMap
    > document parser for daily and hourly granules
    """

    nSegments = len(trace.get('c_segments') or [])

    # Source document for granules
    source = {
      'created': datetime.datetime.now(),
      'collector': CONFIG['VERSION'],
      'warnings': trace['warnings'],
      'status': 'open',
      'format': 'mSEED',
      'fileId': trace['fileId'],
      'type': 'seismic',
      'nseg': nSegments,
      'cont': trace['num_gaps'] == 0,
      'net': trace['network'],
      'sta': trace['station'],
      'cha': trace['channel'],
      'loc': trace['location'],
      'qlt': trace['quality'],
      'ts': trace['start_time'].datetime,
      'te': trace['end_time'].datetime,
      'enc': trace['encoding'],
      'srate': trace['sample_rate'],
      'rlen': trace['record_length'], 
      'nrec': int(trace['num_records']) if trace['num_records'] is not None else None,
      'nsam': int(trace['num_samples']),
      'smin': int(trace['sample_min']),
      'smax': int(trace['sample_max']),
      'smean': float(trace['sample_mean']),
      'smedian': float(trace['sample_median']),
      'supper': float(trace['sample_upper_quartile']),
      'slower': float(trace['sample_lower_quartile']),
      'rms': float(trace['sample_rms']),
      'stdev': float(trace['sample_stdev']), 
      'ngaps': int(trace['num_gaps']),
      'glen': float(trace['sum_gaps']),
      'nover': int(trace['num_overlaps']),
      'olen': float(trace['sum_overlaps']),
      'gmax': float(trace['max_gap']) if trace['max_gap'] is not None else None,
      'omax': float(trace['max_overlap']) if trace['max_overlap'] is not None else None,
      'avail': float(trace['percent_availability']),
      'sgap': trace['start_gap'] is not None,
      'egap': trace['end_gap'] is not None
    }

    # Add parent streamId if it is given, this links
    # the daily stream to hourly granules
    if id is not None:
      source.update({'streamId': id})

    # Add the miniseed header percentages and timing quality
    if self.args['flags']:
      source.update(self._getTimingQuality(trace))
      source.update(self._getFlags(trace))

    # Add file list and checksums
    source.update(self._getFileChecksums(trace['files']))

    return source


  def _getFileChecksums(self, files):
    """
    WFCatalogCollector._getFileChecksums
    returns files and checksums from the trace
    """

    if CONFIG['ENABLE_DUBLIN_CORE']:
      return {'files': [{'do': self._getFileDataObject(f), 'name': os.path.basename(f), 'chksm': self._getMD5Hash(f)} for f in files]}
    else:
      return {'files': [{'name': os.path.basename(f), 'chksm': self._getMD5Hash(f)} for f in files]}


  def _getFileDataObject(self, file):
    """
    WFCatalogCollector._getFileDataObject
    Get the id of the data object or store a new one
    """

    # If the extension exists in the table
    for document in self.mongo.getFileDataObject(file):
      return document['_id']

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
      'fileId': os.path.basename(file),
      'dc:identifier': 'actionable pid',
      'dc:title': 'title',
      'dc:subject': 'mSEED, waveform, quality',
      'dc:creator': CONFIG['ARCHIVE'],
      'dc:contributor': 'network operator',
      'dc:publisher': CONFIG['ARCHIVE'],
      'dc:type': 'seismic waveform',
      'dc:format': 'MSEED',
      'dc:date': datetime.datetime.now(),
      'dc:coverage': 'cov_id',
      'dcterms:available': 'available from now',
      'dcterms:dateAccepted': datetime.datetime.now(),
      'dc:rights': 'open access',
      'dcterms:isPartOf': 'wfmetadata_id'
    }

    return document


  def _getTimingQuality(self, trace):
    """
    WFCatalogCollector._getTimingQuality
    writes timing quality parameters and correction to source document
    """

    trace = trace['miniseed_header_percentages']

    # Add the timing correction
    source = {'tcorr': float(trace['timing_correction'])}

    # Check if the minimum is None, so is the rest
    # otherwise convert to floats
    if trace['timing_quality_min'] is None:

      source.update({
        'tqmin': None,
        'tqmax': None,
        'tqmean': None,
        'tqmedian': None,
        'tqupper': None,
        'tqlower': None
      })

    else:

      source.update({
        'tqmin': float(trace['timing_quality_min']),
        'tqmax': float(trace['timing_quality_max']),
        'tqmean': float(trace['timing_quality_mean']),
        'tqmedian': float(trace['timing_quality_median']),
        'tqupper': float(trace['timing_quality_upper_quartile']),
        'tqlower': float(trace['timing_quality_lower_quartile'])
      })

    return source


  def _getFlags(self, trace):
    """
    WFCatalogCollector._getFlags
    writes mSEED header flag percentages to source document
    """    

    header = trace['miniseed_header_percentages']

    source = {
      'io_flags': self._getFlagKeys(header, 'io_and_clock_flags'),
      'dq_flags': self._getFlagKeys(header, 'data_quality_flags'),
      'ac_flags': self._getFlagKeys(header, 'activity_flags')
    } 

    return source


  def _getFlagKeys(self, trace, flag_type):
    """
    mSEEDMetadataCollector._getFlagKeys
    returns MongoDB document structure for miniseed header percentages
    """

    trace = trace[flag_type]

    if flag_type == 'activity_flags':

      source = {
        'cas': trace['calibration_signal'],
        'tca': trace['time_correction_applied'],
        'evb': trace['event_begin'],
        'eve': trace['event_end'],
        'eip': trace['event_in_progress'],
        'pol': trace['positive_leap'],
        'nel': trace['negative_leap']
      }  

    elif flag_type == 'data_quality_flags':

      source = {
        'asa': trace['amplifier_saturation'],
        'dic': trace['digitizer_clipping'],
        'spi': trace['spikes'],
        'gli': trace['glitches'],
        'mpd': trace['missing_padded_data'],
        'tse': trace['telemetry_sync_error'],
        'dfc': trace['digital_filter_charging'],
        'stt': trace['suspect_time_tag']
      }

    elif flag_type == 'io_and_clock_flags':

      source = {
        'svo': trace['station_volume'],
        'lrr': trace['long_record_read'],
        'srr': trace['short_record_read'],
        'sts': trace['start_time_series'],
        'ets': trace['end_time_series'],
        'clo': trace['clock_locked']
      }

    else:
      raise Exception("Unknown flag type in mSEEDMetadataCollector._getFlagKeys")

    # Make sure the flags are floats
    for flag in source:
      source[flag] = float(source[flag])

    return source


  def _getMD5Hash(self, f):
    """
    WFCatalogCollector._getMD5Hash
    > Method to generate md5 hashes used 
    > for the checksum field
    """
    try:
      BLOCKSIZE = 65536
      hasher = hashlib.md5()
      with open(f, 'rb') as afile:
        buf = afile.read(BLOCKSIZE)
        while len(buf) > 0:
          hasher.update(buf)
          buf = afile.read(BLOCKSIZE)
    except Exception as ex:
      self.log.error(ex)
      return None

    return hasher.hexdigest()


  def _getStatsObject(self, file):
    """
    WFCatalogCollector._getStatsObject
    returns object with stream metadata depending on archive struture
    """
    
    statsArray = file.split(".")

    if CONFIG['STRUCTURE'] == 'ODC':

      stats_object = {
        'jday': statsArray.pop(),
        'year': statsArray.pop(),
        'network': statsArray.pop(),
        'channel': statsArray.pop(),
        'station': statsArray.pop()
      }

    elif CONFIG['STRUCTURE'] == 'SDS' or CONFIG['STRUCTURE'] == 'SDSbynet':

      stats_object = {
        'jday': statsArray.pop(),
        'year': statsArray.pop(),
        'dtype': statsArray.pop(),
        'channel': statsArray.pop(),
        'location': statsArray.pop(),
        'station': statsArray.pop(),
        'network': statsArray.pop()
      }

    else:
      raise Exception("Unknown directory structure in mSEEDMetadataCollector._getStatsObject")

    return stats_object
       

  def _getFilename(self, stats):
    """
    WFCatalogCollector._getFilename
    Returns filename based on structure ODC/SDS
    """

    if CONFIG['STRUCTURE'] == 'ODC':
      filename = ".".join([stats['station'], stats['channel'], stats['network'], stats['year'], stats['jday']]) 

    elif CONFIG['STRUCTURE'] == 'SDS' or CONFIG['STRUCTURE'] == 'SDSbynet':
      filename = ".".join([stats['network'], stats['station'], stats['location'], stats['channel'], stats['dtype'], stats['year'], stats['jday']])

    else:
      raise Exception("Unknown directory structure in mSEEDMetadataCollector._getFilename")

    return filename


  def _getFileDirectory(self, stats):
    """
    WFCatalogCollector._getFileDirectory
    > Returns the directory for a stream at a given date
    """

    if CONFIG['STRUCTURE'] == 'ODC':
      filepath = os.path.join(stats['year'], stats['jday'], self._getFilename(stats))

    elif CONFIG['STRUCTURE'] == 'SDS':
      filepath = os.path.join(stats['year'], stats['network'], stats['station'], stats['channel'] + "." + stats['dtype'], self._getFilename(stats))

    # SDSbynet starts with the extended networkcode
    elif CONFIG['STRUCTURE'] == 'SDSbynet':
      try:
        extnet = fne.extend(stats['network'], stats['year'])
      except Error as e:
        logging.error("Unable to extend network code")
        logging.error(e)
        raise e
      filepath = os.path.join(stats['year'], stats['network'], stats['station'], stats['channel'] + "." + stats['dtype'], self._getFilename(stats))

    else:
      raise Exception("Unknown directory structure in CONFIG (expected ODC or SDS or SDSbynet)")

    return os.path.join(CONFIG['ARCHIVE_ROOT'], filepath)


  def _setGranularity(self):
    """
    WFCatalogCollector._setGranularity
    > Set the granularity
    """

    # For daily granularity take steps of 24h
    self.gran = 1 if self.args['hourly'] else 24
 

  def _getNextFile(self, file, direction):
    """
    WFCatalogCollector._getNextFile
    > gets previous or next dayfile depending on direction (-1, +1)
    """

    stats = self._getStatsObject(os.path.basename(file))
    current_date = datetime.datetime.strptime(stats['year'] + " " + stats['jday'], '%Y %j')
    new_date = current_date + datetime.timedelta(days=direction)

    stats['year'] = new_date.strftime('%Y')
    stats['jday'] = new_date.strftime('%j')

    return self._getFileDirectory(stats)


  def _getDateFromFile(self, file):
    """
    WFCatalogCollector._getDateFromFile
    > returns datetime object of the day a file based on jday/year
    """

    stats = self._getStatsObject(os.path.basename(file))
    return datetime.datetime.strptime(stats['year'] + " " + stats['jday'], '%Y %j')


  def _getFileSegments(self, file):
    """
    WFCatalogCollector._getFileSegments
    > returns the start & end time of segments to a given granularity
    > segment for a full day is returned automatically, hourly is optional
    """

    # Get the daily segment
    start_time = self._getDateFromFile(file)
    end_time = start_time + datetime.timedelta(days=1)

    daily = {'start': start_time, 'end': end_time}

    # Extend with requested hourly granularity
    # Taking 1h steps
    hourly = []
    if self.args['hourly']:

      while start_time < end_time:

        segment_end = start_time + datetime.timedelta(hours=self.gran)
        hourly.append({'start': start_time, 'end': segment_end})
        start_time = segment_end

    return {'daily': daily, 'hourly': hourly}


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
    previous_file = self._getNextFile(file, -1)
    if os.path.isfile(previous_file):
      day_files.append(previous_file)

    # Add todays file
    day_files.append(file)

    # Get tomorrows file
    next_file = self._getNextFile(file, 1)
    if os.path.isfile(next_file):
      day_files.append(next_file)

    self.log.info("[%d/%d] File %s prepared with %s" % (self.file_counter, self.totalFiles, os.path.basename(file), [os.path.basename(f) for f in day_files]))

    return {'files': day_files, 'segments': self._getFileSegments(file)}


class MongoDatabase():
  """
  MongoDatabase
  > Main class for interaction with MongoDB
  """

  def __init__(self):
    """
    MongoDatabase.__init__
    > sets the configured host
    """
    self.host = CONFIG['MONGO']['DB_HOST']
    self._connected = False


  def _connect(self):
    """
    MongoDatabase._connect
    > Sets up connection to the MongoDB
    """

    if self._connected:
      return

    self.client = MongoClient(self.host)
    self.db = self.client[CONFIG['MONGO']['DB_NAME']]

    if CONFIG['MONGO']['AUTHENTICATE']:
      self.db.authenticate(CONFIG['MONGO']['USER'], CONFIG['MONGO']['PASS'])

    self._connected = True

  def getFileDataObject(self, file):
    """
    MongoDatabase.getFileDataObject
    """
    return self.db.wf_do.find({'fileId': os.path.basename(file)})

  def _storeFileDataObject(self, obj):
    """
    MongoDatabase._storeFileDataObject
    stored data object to wf_do collection
    """  
    return self.db.wf_do.save(obj)

  def _storeGranule(self, stream, granule):
    """
    MongoDatabase._storeGranule
    > stores daily and hourly granules to collections
    """

    if granule == 'daily':
      return self.db.daily_streams.save(stream)
    elif granule == 'hourly':
      return self.db.hourly_streams.save(stream)


  def removeDocumentsById(self, id):
    """
    MongoDatabase.removeDocumentsById
    > removes documents all related to ObjectId
    """
    self.db.daily_streams.remove({'_id': id})
    self.db.hourly_streams.remove({'streamId': id})
    self.db.c_segments.remove({'streamId': id})


  def storeContinuousSegment(self, segment):
    """
    MongoDatabase.storeContinuousSegment
    > Saves a continuous segment to collection
    """
    self.db.c_segments.save(segment)


  def getDailyFilesById(self, file):
    """
    MongoDatabase.getDailyFilesById
    returns all documents that include this file in the metadata calculation
    """
    return self.db.daily_streams.find({'files.name': os.path.basename(file)}, {'files': 1, 'fileId': 1, '_id': 1})


  def getDocumentByFilename(self, file):
    """
    MongoDatabase.getDocumentByFilename
    balbal
    """
    return self.db.daily_streams.find({'fileId': os.path.basename(file)})


if __name__ == '__main__':

  # Parse cmd line arguments
  parser = argparse.ArgumentParser(description='Processes mSEED files and ingests waveform metadata to a Mongo repository.')

  # Input file options
  parser.add_argument('--dir', help='directory containing the files to process')
  parser.add_argument('--file', help='specific file to be processed')
  parser.add_argument('--glob', help='glob expression for files to be processed')
  parser.add_argument('--list', help='specific list of files to be processed ["file1", "file2"]')
  parser.add_argument('--past', help='process files in a specific range in the past', choices=['day', 'yesterday', 'week', 'fortnight', 'month'], default=None)
  parser.add_argument('--date', help='process files for a specific date', default=None)
  parser.add_argument('--range', help='number of days after a specific date', default=1)

  # Options to show config/versioning
  parser.add_argument('--config', help='view configuration options', action='store_true')
  parser.add_argument('--version', action='version', version=CONFIG['VERSION'])

  # Add flags and continuous segments
  parser.add_argument('--flags', help='include mSEED header flags in result', action='store_true')
  parser.add_argument('--csegs', help='include continuous segments in result', action='store_true')
  parser.add_argument('--hourly', help='include hourly granules in result', action='store_true')

  # Set custom logfile
  parser.add_argument('--logfile', help='set custom logfile')
  parser.add_argument('--stdout',  help='outputs all logs to stdout')

  # Options to update documents existing in the database, normally
  # files that are already processed are skipped
  # Updates can be forced (without checksum check)
  parser.add_argument('--update', help='update existing documents in the database', action='store_true')
  parser.add_argument('--force', help='force file updates', action='store_true')
  parser.add_argument('--delete', help='delete files from database', action='store_true')

  # Get parsed arguments as a JSON dict to match
  # compatibility with an imported class
  args = vars(parser.parse_args())

  WFCollector = WFCatalogCollector(args['logfile'])

  WFCollector.process(args)
