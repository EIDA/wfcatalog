import os
from multiprocessing import Pool
from WFCatalogCollector import WFCatalogCollector

import datetime

"""
Example multithreading script for WFCatalogCollector.py

Author: Mathijs Koymans, KNMI 2017
"""

NUMBER_OF_PROCESSES = 4

MetadataCollector = WFCatalogCollector("./logs/multithreader-master.log")


def WFCatalogWork(filename):

    try:

        MetadataCollector.process({"file": filename, "csegs": True, "flags": True})

    # Pass on system exists
    except SystemExit:
        pass


if __name__ == "__main__":

    # Get files from yesterday
    files = MetadataCollector._collectFilesFromDate(
        datetime.datetime.now() - datetime.timedelta(days=1)
    )

    # Or files from a directory
    # files = [os.path.join(root, f) for root, dirs, files in os.walk("/data/storage/orfeus/SDS/2016/EC") for f in files if os.path.isfile(os.path.join(root, f))]

    # Create a pool and map the work across the pool
    pool = Pool(processes=NUMBER_OF_PROCESSES)
    pool.map(WFCatalogWork, files)
    pool.close()
    pool.join()
