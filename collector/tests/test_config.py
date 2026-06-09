#!/usr/bin/env python3

from wfcatalog_collector.WFCatalogCollector import load_configuration


def test_config_load():
    config = load_configuration()
    assert not config["MONGO"]["ENABLED"]
