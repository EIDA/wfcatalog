# EIDA-NG WFCatalog Collector

Python script for ingestion waveform metadata to MongoDB.

## Collector Requirements

- Python3.11+
- MongoDB collections (`daily_streams`, `c_segments`)

It is important to create two MongoDB collections and apply an index on the
daily streams fileId field before starting the procedure.

```bash
db.daily_streams.createIndex({'fileId': 1})
db.c_segments.createIndex({'fileId': 1})
```

## Installation
### Downloading the source code

The source code of the WFCatalog Service can be downloaded through
git: `git clone https://github.com/EIDA/EIDA.git` and is located in
the `wfcatalog/collector` subdirectory that will be our working directory
during setup.

### Alternatively as a container

    podman run ghcr.io/eida/wfcatalog-collector:latest

## Configuring the collector

Configuration can be set by two means:

### config.json file

It is important to edit the `config.json` properly before using the collector.
Pay particular attention to the following settings:

- `MONGO.ENABLED` - `false` will print metrics to stdout and `true` will try to save metrics to MOngoDB
- `MONGO.DB_HOST` - mongodb://host:port of the database
- `MONGO.DB_NAME` - name of the database (recommended: `wfrepo`)
- `MONGO.ALLOW_DOUBLE` - allow double streams to be added to the database (recommended: `false`)
- `ARCHIVE_ROOT` - root directory of the data archive that is used for metric calculation
- `STRUCTURE` - ODC or SDS or SDSbynet.
  - `ODC` has his own data structure
  - `SDS` supposes that the data has the structure : `YYYY/NET/STA/CHAN.D/NET.STA.CHAN.D.YYYY.JJJ`
  - `SDSbynet` supposes that the data has the structure : `NETXT/YYYY/STA/CHAN.D/NET.STA.CHAN.D.YYYY.JJJ`
    where NETXT is an extended network code.
  - If the value is `SDSbynet`, then you need to install the fdsnextender python library `pip install fdsnnetextender`
  
### Alternatively, environment variables

If `config.json` can not be found in the `WFCAT_CONF_DIR` directory (default to current working directory), then the systems loads from the following environment variables:

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


## Running the collector

### With uv (recommanded)

[https://docs.astral.sh/uv/getting-started/installation/](Get uv)

``` bash
uv run src/WFCatalogCollector.py
```

### virtual env + pip
```bash
# Create the virtual environment and install dependencies
cd ./collector/
python3 -m venv .env
source ./env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

The collector can be run with `MONGO.ENABLED` set to `false` to test the script installation
without saving metrics to the database. The collector can be called with flags as
described in [Redmine](https://eida.gfz-potsdam.de/redmine/projects/etc/wiki/WFCatalog#2-EIDANG-WFCatalog-Collector) e.g.:

`python WFCatalogCollector.py --dir /data/storage/SDS/2012/NL/ --csegs --flags`

This command will process files recursively in the 2012/NL directory and include
results on continuous segments and mSEED header flags.

## Installation through Docker

