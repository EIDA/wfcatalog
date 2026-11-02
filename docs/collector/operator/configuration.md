---
author: Nikos Sokos
created: 2026-11-02
service: wfcatalog
tags:
  - operator
---

# Configuration

Configuration can be set by two means.

## config.json file

It is important to edit the `config.json` properly before using the collector.
A template is provided as `config.json.sample` in the `collector` directory.
Pay particular attention to the following settings:

| Setting | Description |
| --- | --- |
| `ARCHIVE` | Archive name |
| `PUBLISHER` | Quality metric publisher |
| `STRUCTURE` | ODC or SDS or SDSbynet. SDS is default and used by all nodes except the ODC. Used to find files. |
| `MONGO.ENABLED` | `false` will print metrics to stdout and `true` will try to save metrics to MongoDB |
| `MONGO.ENGINE` | Engine running the DB backend (mongodb or docdb) |
| `MONGO.DB_HOST` | mongodb://host:port of the database |
| `MONGO.DB_PORT` | Port of the database |
| `MONGO.DB_NAME` | name of the database (recommended: `wfrepo`) |
| `MONGO.DB_USER`, `MONGO.DB_PASS` | Database credentials |
| `MONGO.ALLOW_DOUBLE` | allow double streams to be added to the database (recommended: `false`) |
| `ARCHIVE_ROOT` | root directory of the data archive that is used for metric calculation. The following subdirectories are the archived years. |
| `DEFAULT_LOG_FILE` | Path to log for writing |
| `PROCESSING_TIMEOUT` | Number of seconds to timeout when analysing a file |
| `ENABLE_DUBLIN_CORE` | Add data object information in the catalog |
| `FILTERS.WHITE` | Array of strings used for fnmatch (default `["*"]` for everything) |
| `FILTERS.BLACK` | Array of strings used for fnmatch (has precedent over white list) |

Archive structures:

- `ODC` has his own data structure
- `SDS` supposes that the data has the structure: `YYYY/NET/STA/CHAN.D/NET.STA.CHAN.D.YYYY.JJJ`
- `SDSbynet` supposes that the data has the structure: `NETXT/YYYY/STA/CHAN.D/NET.STA.CHAN.D.YYYY.JJJ`
  where NETXT is an extended network code.
  If the value is `SDSbynet`, then you need to install the fdsnextender python library `pip install fdsnnetextender`

## Alternatively, environment variables

If `config.json` can not be found in the `WFCAT_CONF_DIR` directory (default to current working directory), then the system loads from the following environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `WFCAT_NODE_NAME` | `EIDA` | The name of the EIDA node. Will be set as the creator in wfcatalog database. |
| `WFCAT_PUBLISHER` | `Obspy {Version}` | The name of the EIDA node. Will be set as the publisher in wfcatalog database. |
| `WFCAT_ARCHIVE_STRUCT` | `SDS` | Define how the archive is organised in its directory hierarchy. Possible values are `SDS` or `SDSbynet` or `ODC`. `SDS` stands for "Seiscomp Data Structure". |
| `WFCAT_ARCHIVE_ROOT` | | The root path of the data archive. |
| `WFCAT_MONGO_ENABLED` | `false` | Should the process connect to the mongodb backend? (`true` or `false`) |
| `WFCAT_MONGO_ENGINE` | `mongodb` | Engine running the DB backend (`mongodb` or `docdb`) |
| `WFCAT_MONGO_HOST` | `localhost` | Hostname of the mongo server. |
| `WFCAT_MONGO_PORT` | `27017` | Port of the mongo server. |
| `WFCAT_MONGO_DBNAME` | `wfcatalog` | Name of the database. |
| `WFCAT_MONGO_USER` | `wfcatalog` | Username. |
| `WFCAT_MONGO_PASS` | `wfcatalog` | Password. |
| `WFCAT_MONGO_ALLOW_DUPLICATE` | `false` | If true, can insert multiple documents with same file ID (unique Net, Sta, Cha, Loc, Day) |
| `WFCAT_DEFAULT_LOG_FILE` | | Path to the log file. If not set, logs to stdout |
| `WFCAT_PROCESSING_TIMEOUT` | `120` | Number of seconds to timeout when analysing a file |
| `WFCAT_DUBLIN_CORE_ENABLED` | `false` | Add data object information in the catalog |
| `WFCAT_FILTERS_WHITE` | `*` | comma separated list of pattern to whitelist when harvesting files. |
| `WFCAT_FILTERS_BLACK` | | comma separated list of pattern to blacklist when harvesting files. |
