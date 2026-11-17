---
author: Nikos Sokos
created: 2026-11-02
service: wfcatalog
tags:
  - developer
---

# Development

## Program stack

- Python 3.13 or newer, managed with [uv](https://docs.astral.sh/uv/)
- [ObsPy](https://docs.obspy.org/) 1.5 or newer, `obspy.signal.quality_control.MSEEDMetadata` for metadata extraction
- [pymongo](https://pymongo.readthedocs.io/) 4.17 or newer
- fdsnnetextender 5.0, for the `SDSbynet` archive structure
- pytest, as the dev dependency group

## Architecture

The collector is started as a module from the `collector` directory:
`python -m src.WFCatalogCollector`. The source is split into modules under `collector/src/`:

| Module | Purpose |
| --- | --- |
| `WFCatalogCollector.py` | WFCatalog Collector and Synchronization: file selection, filters, change detection, logging and the command line |
| `config.py` | Configuration loading from `config.json` or the `WFCAT_*` environment variables |
| `archive.py` | Archive path logic: file name parsing, SDS, SDSbynet and ODC directory structures, neighbouring day files |
| `metrics.py` | Metric computation: the single place where ObsPy's mSEED quality control is called, guarded by the per-file processing timeout |
| `FastMSEEDMetadata.py` | Subclass of ObsPy's `MSEEDMetadata` with its own sample metrics; the class `metrics.py` uses |
| `mapping.py` | Document mapping: turns the metadata dictionary returned by ObsPy into the compact documents stored in MongoDB |
| `db.py` | MongoDB access |
| `multithreader.py` | Runs the collector on several dates in parallel |

The collector can also be used through an import. Options are identical to the
command line flags and passed as `{'key': value}` pairs in a dictionary:

```python
from src.WFCatalogCollector import WFCatalogCollector
mmc = WFCatalogCollector(logfile)
mmc.process({'dir': '/PATH/TO/FILES', 'csegs': True, 'flags': True})
```

## Contribution

Issues and pull requests are managed on <https://github.com/EIDA/wfcatalog>.

Tests run from the `collector` directory:

```bash
uv run pytest
```

`tests/test_database_sync.py` runs the collector against a MongoDB at
`WFCAT_TEST_MONGO_HOST`:`WFCAT_TEST_MONGO_PORT` (default `127.0.0.1:27017`), in a database
of its own named `wfcatalog_pytest`; without a MongoDB these tests are skipped.

`tests/test_collector_output.py` runs the collector on the bundled day files in
`collector/archive/` with MongoDB disabled and compares the output with
`tests/expected/bundled_archive_output.txt`. To accept an intended change of
output, regenerate the expected file with `UPDATE_EXPECTED=1 uv run pytest tests/test_collector_output.py`.

## Code quality requirements

- [x] Unit tests (`uv run pytest`)
- [ ] Linted code
- [x] Dependencies lock (`uv.lock`)
- [x] CI jobs: `.github/workflows/tests.yml` runs `uv run pytest` on Python 3.13 and 3.14 and builds the container image for every pull request and for pushes to `master`;
  `.github/workflows/publish-container.yml` builds and publishes the container images on push
