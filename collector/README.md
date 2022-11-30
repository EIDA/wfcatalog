# EIDA-NG WFCatalog Collector

Python script for ingestion waveform metadata to MongoDB.

## Collector Requirements

* Python2.7+
* The ObsPy MSEEDMetadata class.
* MongoDB collections (`daily_streams`, `c_segments`)

The collector requires a custom Python class used for metrics calculation that
will be included in future releases of ObsPy. It is currently included in the
master branch of ObsPy on [github](https://github.com/obspy/obspy) and must be
installed through git.

It is important to create two MongoDB collections and apply an index on the
daily streams fileId field before starting the procedure.

    db.daily_streams.createIndex({'fileId': 1})
    db.c_segments.createIndex({'fileId': 1})

## Downloading the source code

The source code of the WFCatalog Service can be downloaded through
git: `git clone https://github.com/EIDA/EIDA.git` and is located in
the `wfcatalog/collector` subdirectory that will be our working directory
during setup.

## Configuring the collector

It is important to edit the `config.json` properly before using the collector.
Pay particular attention to the following settings:

* `MONGO.ENABLED` - `false` will print metrics to stdout and `true` will try to save metrics to MOngoDB
* `MONGO.DB_HOST` - mongodb://host:port of the database
* `MONGO.DB_NAME` - name of the database (recommended: `wfrepo`)
* `MONGO.ALLOW_DOUBLE` - allow double streams to be added to the database (recommended: `false`)
* `ARCHIVE_ROOT` - root directory of the data archive that is used for metric calculation
* `STRUCTURE` - ODC or SDS or SDSbynet.
  * `ODC` has his own data structure
  * `SDS` supposes that the data has the structure : `YYYY/NET/STA/CHAN.D/NET.STA.CHAN.D.YYYY.JJJ`
  * `SDSbynet` supposes that the data has the structure : `NETXT/YYYY/STA/CHAN.D/NET.STA.CHAN.D.YYYY.JJJ`
     where NETXT is an extended network code.
  * If the value is `SDSbynet`, then you need to install the fdsnextender python library `pip install fdsnnetextender`

## Running the collector

The collector can be run with `MONGO.ENABLED` set to `false` to test the script installation
without saving metrics to the database. The collector can be called with flags as
described in [Redmine](https://dev.knmi.nl/projects/eida/wiki/WFCatalog#2-EIDANG-WFCatalog-Collector) e.g.:

    Python WFCatalogCollector.py --dir /data/storage/SDS/2012/NL/ --csegs --flags

This command will process files recursively in the 2012/NL directory and include
results on continuous segments and mSEED header flags.

## Installation through Docker

Alternatively, the collector can also be run as a Docker container by building
the Dockerfile and requires no installation of the ObsPy MSEEDMetadata class.
A detailed description of the installation can be found on the internal
[Redmine Wiki](https://dev.knmi.nl/projects/eida/wiki/WFCatalogDocker).
