"""
WFCatalog Collector configuration.

Loads settings once at import time, from $WFCAT_CONF_DIR/config.json if it
exists, otherwise from WFCAT_* environment variables. See load_configuration.
"""

import os
from pathlib import Path
import json
import logging
import sys
import importlib.metadata


def load_configuration():
    """
    Loads configuration parameters.
    First try from $WFCAT_CONF_DIR/config.json ($WFCAT_CONF_DIR defaults to current working directory)
    If file does not exist, use the following environment variables:
    - WFCAT_NODE_NAME : The name of the EIDA node. Will be set as the creator in wfcatalog database. Default is EIDA
    - WFCAT_PUBLISHER : The name of the EIDA node. Will be set as the publisher in wfcatalog database. Default is "Obspy {Version}"
    - WFCAT_ARCHIVE_STRUCT: Define how the archive is organised in it's directory hierarchy.
              Possible values are "SDS" or "SDSbynet" or "ODC"
              Default is "SDS" for "Seiscomp Data Structure"
    - WFCAT_ARCHIVE_ROOT: The root path of the data archive.
    - WFCAT_MONGO_ENABLED: Should the process connect to the mongodb backend ? (true or false), default false
    - WFCAT_MONGO_ENGINE: Engine running the DB backend (mongodb or docdb), default mongodb
    - WFCAT_MONGO_HOST: Hostname of the mongo server. Default 127.0.0.1
    - WFCAT_MONGO_PORT: Port of the mongs server. Default 27017
    - WFCAT_MONGO_DBNAME: Port of the mongs server. Default 27017
    - WFCAT_MONGO_USER: Username. Default "wfcatalog"
    - WFCAT_MONGO_PASS: Password. Default "wfcatalog"
    - WFCAT_MONGO_ALLOW_DUPLICATE: If true, can insert multiple documents with same file ID (unique Net, Sta, Cha, Loc, Day)
    - WFCAT_DEFAULT_LOG_FILE: Path to the log file. If not set, logs to stdout
    - WFCAT_PROCESSING_TIMEOUT: Number of seconds to timeout when analysing a file
    - WFCAT_DUBLIN_CORE_ENABLED: Add data object information in the catalog
    - WFCAT_FILTERS_WHITE: coma separated list of pattern to whitelist when harvesting files. Default '*'
    - WFCAT_FILTERS_BLACK: coma separated list of pattern to blacklist when harvesting files. Default ''
    """
    try:
        conf_dir = Path(os.getenv("WFCAT_CONF_DIR", os.getcwd()))
        conf_file = conf_dir / "config.json"

        if conf_file.exists():
            with conf_file.open() as cfg:
                logging.info("Using configuration from %s", conf_file)
                config = json.load(cfg)
        else:
            node_name = os.getenv("WFCAT_NODE_NAME", "EIDA")
            publisher = os.getenv(
                "WFCAT_PUBLISHER ", f"Obspy {importlib.metadata.version('obspy')}"
            )
            archive_struct = os.getenv("WFCAT_ARCHIVE_STRUCT", "SDS")
            archive_root = os.getenv("WFCAT_ARCHIVE_ROOT", "")
            mongo_enabled = os.getenv("WFCAT_MONGO_ENABLED", "false") == "true"
            mongo_engine = os.getenv("WFCAT_MONGO_ENGINE", "mongodb")
            mongo_host = os.getenv("WFCAT_MONGO_HOST", "localhost")
            mongo_port = int(os.getenv("WFCAT_MONGO_PORT", "27017"))
            mongo_dbname = os.getenv("WFCAT_MONGO_DBNAME", "wfcatalog")
            mongo_user = os.getenv("WFCAT_MONGO_USER", "wfcatalog")
            mongo_pass = os.getenv("WFCAT_MONGO_PASS", "wfcatalog")
            mongo_allow_duplicate = (
                os.getenv("WFCAT_MONGO_ALLOW_DUPLICATE", "false") == "true"
            )
            default_log_file = os.getenv("WFCAT_DEFAULT_LOG_FILE", None)
            processing_timeout = int(os.getenv("WFCAT_PROCESSING_TIMEOUT", "120"))
            dublin_core_enabled = (
                os.getenv("WFCAT_DUBLIN_CORE_ENABLED", "false") == "true"
            )
            filters_white = os.getenv("WFCAT_FILTERS_WHITE", "*").split(",")
            filters_black = os.getenv("WFCAT_FILTERS_BLACK", "").split(",")
            config = {
                "MONGO": {
                    "ENABLED": mongo_enabled,
                    "ENGINE": mongo_engine,
                    "DB_HOST": mongo_host,
                    "DB_PORT": mongo_port,
                    "DB_USER": mongo_user,
                    "DB_PASS": mongo_pass,
                    "DB_NAME": mongo_dbname,
                    "ALLOW_DOUBLE": mongo_allow_duplicate,
                },
                "ARCHIVE": node_name,
                "PUBLISHER": publisher,
                "STRUCTURE": archive_struct,
                "ARCHIVE_ROOT": archive_root,
                "DEFAULT_LOG_FILE": default_log_file,
                "PROCESSING_TIMEOUT": processing_timeout,
                "ENABLE_DUBLIN_CORE": dublin_core_enabled,
                "FILTERS": {"WHITE": filters_white, "BLACK": filters_black},
            }

    except json.decoder.JSONDecodeError as e:
        # I don't have any logger initialized yet
        print("ERROR: Configuration error: %s", e)
        raise e
    except Exception as e:
        raise e

    return config


try:
    CONFIG = load_configuration()
except Exception:
    sys.exit(1)
