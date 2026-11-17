#!/usr/bin/env python3

import os
import tempfile
import pytest
from src.config import load_configuration
from src.WFCatalogCollector import WFCatalogCollector


def test_config_load():
    config = load_configuration()
    assert not config["MONGO"]["ENABLED"]


def test_show_config():
    wfcol = WFCatalogCollector()
    wfcol.showConfig()


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
        with pytest.raises(Exception):
            load_configuration()


def test_config_load_with_file_not_found():
    with tempfile.TemporaryDirectory() as confdir:
        os.environ["WFCAT_CONF_DIR"] = confdir
        config = load_configuration()
        assert config["ARCHIVE"] == "EIDA"


def test_publisher_from_environment(monkeypatch):
    with tempfile.TemporaryDirectory() as confdir:
        monkeypatch.setenv("WFCAT_CONF_DIR", confdir)  # no config.json: env vars are used
        monkeypatch.setenv("WFCAT_PUBLISHER", "TEST-NODE")
        config = load_configuration()
        assert config["PUBLISHER"] == "TEST-NODE"
