---
author: Nikos Sokos
created: 2026-11-02
service: wfcatalog
tags:
  - operator
---

# Configuration

It is important to edit the `configuration.json` properly before starting the
service. A template is provided as `configuration.json.sample` in the `service`
directory. Pay particular attention to the following options:

| Option | Description |
| --- | --- |
| `NAME` | Service name |
| `ARCHIVE` | Name of archive running the service |
| `HOST` | host where the service will be available |
| `PORT` | port where the service will be available |
| `MONGO.HOST` | host:port/database of the collections used by the service |

All options in `configuration.json.sample`, with their sample values:

| Option | Sample value |
| --- | --- |
| `NAME` | `ODC-WFCATALOG` |
| `ARCHIVE` | `ORFEUS ODC/KNMI` |
| `AGENT` | `ObsPy mSEED-QC` |
| `DOCUMENTATION_URI` | `ENTER_URI_HERE` |
| `BASE_URL` | `/eidaws/wfcatalog/1/` |
| `HOST` | `127.0.0.1` |
| `PORT` | `3000` |
| `LOGPATH` | `./logs/` |
| `MAXIMUM_POST_BYTES` | `1e4` |
| `MAXIMUM_GET_BYTES` | `1e4` |
| `MAXIMUM_SEGMENTS` | `50` |
| `WFCATALOG_SCHEMA_VERSION` | `1.0.0` |
| `RESPAWN` | `true` |
| `WORKER` | `0` |
| `MAXIMUM_CORES` | `4` |
| `MAXIMUM_BYTES_RETURNED` | `10e6` |
| `FILTER.ENABLED` | `false` |
| `FILTER.STREAMS` | `[]` |
| `ELASTICSEARCH.ENABLED` | `false` |
| `ELASTICSEARCH.HOST` | `127.0.0.1` |
| `ELASTICSEARCH.PORT` | `9200` |
| `ELASTICSEARCH.INDEX` | `wfcatalog` |
| `MONGO.AUTO_RECONNECT` | `true` |
| `MONGO.POOL_SIZE` | `10` |
| `MONGO.AUTHENTICATE` | `true` |
| `MONGO.HOST` | `127.0.0.1:27017` |
| `MONGO.DBNAME` | `wfrepo` |
| `MONGO.USER`, `MONGO.PASS` | empty |
| `MONGO.COLLECTION` | `daily_streams` |
| `MONGO.C_COLLECTION` | `c_segments` |
| `CLOSED` | `false` |
| `VERSION` | `1.0.3` |
