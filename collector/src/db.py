"""
WFCatalog Collector database access.

Thin wrapper around pymongo. pymongo is only imported when the database is
enabled in the configuration, so nodes that print to stdout do not need it.
"""

import os

from src.config import CONFIG

if CONFIG["MONGO"]["ENABLED"]:
    from pymongo import MongoClient


class MongoDatabase:
    """
    MongoDatabase
    > Main class for interaction with MongoDB
    """

    def __init__(self):
        """
        MongoDatabase.__init__
        > sets the configured host
        """
        self.host = CONFIG["MONGO"]["DB_HOST"]
        self._connected = False

    def _connect(self):
        """
        MongoDatabase._connect
        > Sets up connection to the MongoDB
        """

        if self._connected:
            return

        # Document DB deployments need a different set of arguments
        db_kwargs = {
            "username": CONFIG["MONGO"]["DB_USER"],
            "password": CONFIG["MONGO"]["DB_PASS"]
        }
        if CONFIG["MONGO"].get("ENGINE", "mongodb") == "docdb":
            db_kwargs |= {
                "tls": True,
                "tlsCAFile": "global-bundle.pem",
                "replicaSet": "rs0",
                "readPreference": "secondaryPreferred",
                "retryWrites": False
            }
        else:  # Just default to mongodb
            db_kwargs |= {"authSource": CONFIG["MONGO"]["DB_NAME"]}

        self.db = MongoClient(
            CONFIG["MONGO"]["DB_HOST"],
            CONFIG["MONGO"]["DB_PORT"],
            **db_kwargs
        ).get_database(CONFIG["MONGO"]["DB_NAME"])

        self._connected = True

    def getFileDataObject(self, file):
        """
        MongoDatabase.getFileDataObject
        """
        return self.db.wf_do.find({"fileId": os.path.basename(file)})

    def _storeFileDataObject(self, obj):
        """
        MongoDatabase._storeFileDataObject
        stored data object to wf_do collection
        """
        return self.db.wf_do.insert_one(obj)

    def _storeGranule(self, stream, granule):
        """
        MongoDatabase._storeGranule
        > stores daily and hourly granules to collections
        """

        if granule == "daily":
            return self.db.daily_streams.insert_one(stream)
        elif granule == "hourly":
            return self.db.hourly_streams.insert_one(stream)

    def removeDocumentsById(self, id):
        """
        MongoDatabase.removeDocumentsById
        > removes documents all related to ObjectId
        """
        # We could also use delete_one here
        self.db.daily_streams.delete_many({"_id": id})
        self.db.hourly_streams.delete_many({"streamId": id})
        self.db.c_segments.delete_many({"streamId": id})

    def storeContinuousSegment(self, segment):
        """
        MongoDatabase.storeContinuousSegment
        > Saves a continuous segment to collection
        """
        self.db.c_segments.insert_one(segment)

    def getDailyFilesById(self, file):
        """
        MongoDatabase.getDailyFilesById
        returns all documents that include this file in the metadata calculation
        """
        return self.db.daily_streams.find(
            {"files.name": os.path.basename(file)}, {"files": 1, "fileId": 1, "_id": 1}
        )

    def getDocumentByFilename(self, file):
        """
        MongoDatabase.getDocumentByFilename
        balbal
        """
        return self.db.daily_streams.find({"fileId": os.path.basename(file)})

    def countDocumentsByFilename(self, file):
        return self.db.daily_streams.count_documents({"fileId": os.path.basename(file)})

