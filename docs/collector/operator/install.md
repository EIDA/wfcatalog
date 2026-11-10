---
author: Nikos Sokos
created: 2026-11-02
service: wfcatalog
tags:
  - operator
---

# Installation

## Requirements

- Python 3.13 or newer
- MongoDB collections (`daily_streams`, `c_segments`)

It is important to create two MongoDB collections and apply an index on the
daily streams fileId field before starting the procedure.

```bash
db.daily_streams.createIndex({'fileId': 1})
db.c_segments.createIndex({'fileId': 1})
```

If the archive structure is `SDSbynet`, then you need to install the fdsnextender
python library `pip install fdsnnetextender`.

## Install

### Downloading the source code

The source code of the WFCatalog Collector can be downloaded through
git: `git clone https://github.com/EIDA/wfcatalog.git` and is located in
the `collector` subdirectory that will be our working directory
during setup.

### Running with uv (recommended)

[Get uv](https://docs.astral.sh/uv/getting-started/installation/), then from the `collector` directory:

```bash
uv run python -m src.WFCatalogCollector
```

The collector can be run with `MONGO.ENABLED` set to `false` to test the script installation
without saving metrics to the database. The collector can be called with flags, e.g.:

```bash
uv run python -m src.WFCatalogCollector --dir /data/storage/SDS/2012/NL/ --csegs --flags
```

This command will process files recursively in the 2012/NL directory and include
results on continuous segments and mSEED header flags.

### Alternatively as a container

```bash
podman run ghcr.io/eida/wfcatalog-collector:latest
```

The container entrypoint is `python3 -m src.WFCatalogCollector`; the command line
flags are passed as container arguments and the configuration through the
environment variables listed in [Configuration](configuration.md).

### Command line flags

Boolean flags:

| Flag | Description |
| --- | --- |
| `--update` | start synchronization on input files with changes |
| `--force` | forces synchronization on all input files |
| `--csegs` | include continuous segments |
| `--flags` | include miniseed header percentages, timing correction, and timing quality |
| `--hourly` | include hourly granules |
| `--delete` | delete files from database |
| `--config` | show Collector configuration |
| `--version` | show Collector version |

File input options:

| Flag | Description |
| --- | --- |
| `--dir $DIR` | all files in this directory are processed |
| `--file $FILE` | process a specific file |
| `--glob $PATTERN` | glob expression for files to be processed |
| `--list $ARRAY` | Array of files to be processed |
| `--date $DATE` | process files for a specific date (`YYYY-MM-DD` or `YYYY-JJJ`) |
| `--range $N` | number of days after a specific date |
| `--past $ENUM` | files in date range matching this criteria will be processed {today, yesterday, week, fortnight, month} |

Other flags:

| Flag | Description |
| --- | --- |
| `--logfile` | specify a custom logfile |
| `--stdout` | outputs everything to stdout |

Giving the `--update` flag does a checksum change detection on
all input files. The documents in the database that are dependent
on the changed files are removed, reprocessed, and inserted. Updating
does NOT insert any new files in the directory.
An update can be forced by giving `--force` which skips the checksum change detection and reprocesses all files.

### Keeping the catalogue consistent with the archive

A day document is computed from its own file and from the neighbouring day
files that hold data of that day, typically the last record of the previous
day. The names and checksums of the files used are stored with the document.

- `--delete` removes the documents of the given files and then recomputes
  every document that used one of those files.
- `--update` compares the checksum of each given file with the checksum
  stored in the documents that used it, and recomputes those documents when
  the file changed.
- Give `--update` and `--delete` the same `--hourly`, `--csegs` and `--flags`
  as the original run. A recomputed document is stored with the options of the
  current run; parts that are not computed again are lost, and the collector
  logs a warning for each of them.
- A file that arrives after the next day was processed is not picked up by
  the next day's document, and `--update` cannot detect it because the
  document never recorded that file. Run `--update --force --file` on the
  next day's file.
