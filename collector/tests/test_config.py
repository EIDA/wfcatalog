#!/usr/bin/env python3

import os
import tempfile
import pytest
from src.WFCatalogCollector import load_configuration
from src.WFCatalogCollector import WFCatalogCollector


def test_config_load():
    config = load_configuration()
    assert not config["MONGO"]["ENABLED"]


def test_show_config():
    wfcol = WFCatalogCollector()
    wfcol.showConfig()


def test_show_version():
    wfcol = WFCatalogCollector()
    wfcol.showVersion()


def test_config_load_with_file():
    with tempfile.TemporaryDirectory() as confdir:
        os.environ["WFCAT_CONF_DIR"] = confdir
        with open(f"{confdir}/config.json", "w") as conf:
            conf.write("""{"ARCHIVE": "EIDA TEST NODE"}""")
        config = load_configuration()
        assert config["ARCHIVE"] == "EIDA TEST NODE"


def test_config_error():
    with tempfile.TemporaryDirectory() as confdir:
        os.environ["WFCAT_CONF_DIR"] = confdir
        with open(f"{confdir}/config.json", "w") as conf:
            conf.write("""{"ARCHIVE": "EIDA TEST NODE"},""")
        with pytest.raises(Exception) as e_info:
            load_configuration()


def test_config_load_with_file_not_found():
    with tempfile.TemporaryDirectory() as confdir:
        os.environ["WFCAT_CONF_DIR"] = confdir
        config = load_configuration()
        assert config["ARCHIVE"] == "EIDA"
