#!/usr/bin/env python3

from wfcatalog_collector.WFCatalogCollector import load_configuration
from wfcatalog_collector.WFCatalogCollector import WFCatalogCollector


def test_config_load():
    config = load_configuration()
    assert not config["MONGO"]["ENABLED"]


def test_show_config():
    wfcol = WFCatalogCollector()
    wfcol.showConfig()
