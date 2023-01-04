import signal
import time
import logging
import json
import sys
import os

from multiprocessing import Pool
from pymongo import MongoClient
from datetime import datetime, timedelta

from ingestdaily import PSDExtractor


def notexists(file):

    return file.startswith("NL")


def filesFromDir(direc):

    filesDir = []
    for root, dirs, files in os.walk(direc):
        for name in files:
            filesDir.append(name)

    return filesDir


def _collectFilesFromDate(date):

    """
    WFCatalogCollector._collectFilesFromDate
    > collects the files for a given year and day
    """

    # Get the year & day of year
    jday = date.strftime("%j")
    year = date.strftime("%Y")

    # SDS structure is slightly more complex, loop over all directories
    # in a year and extract files ending with a given jday
    collectedFiles = []
    directory = os.path.join(CONFIG["ARCHIVE_ROOT"], year)
    for subdir, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(jday) and os.path.isfile(os.path.join(subdir, file)):
                collectedFiles.append(file)

    return collectedFiles


class TimeoutException(Exception):
    pass


with open("./config.json") as configurationFile:
    CONFIG = json.load(configurationFile)


def handler(signum, frame):
    raise Exception("The PSD calculation has timed out.")


def getdb():
    return


# Open the database connection
client = MongoClient(
    CONFIG["MONGO"]["HOST"],
    CONFIG["MONGO"]["PORT"],
)

db = client[CONFIG["MONGO"]["DATABASE"]]


def PSDWork(filename):

    log.info("Start processing of file %s." % filename)

    # Write object to database
    if db.psd.find({"fileId": filename}).count() > 0:
        log.error("Spectra for %s are already in the database." % filename)
        return None

    signal.signal(signal.SIGALRM, handler)
    signal.alarm(CONFIG["PROCESSING_TIMEOUT"])

    try:
        return Extractor.Process(filename)
    except Exception as ex:
        log.error(ex)
        return None
    finally:
        signal.alarm(0)


# Open the logger
log = logging.getLogger("PSD-Collector")
log.setLevel("INFO")
file_handler = logging.FileHandler(CONFIG["DEFAULT_LOG_FILE"])
file_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)
log.addHandler(file_handler)

if CONFIG["MONGO"]["AUTHENTICATE"]:
    log.info("Database connection has been succesfully authenticated.")
    db.authenticate(CONFIG["MONGO"]["USER"], CONFIG["MONGO"]["PASS"])

Extractor = PSDExtractor(log)

log.info("Database connection has been succesfully established.")

pool = Pool(processes=CONFIG["NUMBER_OF_PROCESSES"])

yesterday = datetime.now() - timedelta(days=1)
# files = _collectFilesFromDate(yesterday)
files = filesFromDir("/data/shared-dta/rdsait/1055/after/")
files = filter(notexists, files)

for result in pool.imap_unordered(PSDWork, files, chunksize=5):

    # Save the result
    if result is not None:
        log.info(
            "Storing %i spectra for %s." % (len(result["spectra"]), result["filename"])
        )
        for document in result["spectra"]:
            db.psd.save(document)

        log.info("Finished processing %s in %s." % (result["filename"], result["time"]))

log.info("Master has finished!")

pool.close()
pool.join()
