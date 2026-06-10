#!/usr/bin/env python3

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
