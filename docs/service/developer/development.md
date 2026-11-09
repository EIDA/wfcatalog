---
author: Nikos Sokos
created: 2026-11-02
service: wfcatalog
tags:
  - developer
---

# Development

## Program stack

- NodeJS (container image based on `node:19`)
- [express](https://expressjs.com/) 4.18
- [mongodb](https://www.npmjs.com/package/mongodb) driver 4.12
- [bunyan](https://www.npmjs.com/package/bunyan) logging, with optional Elasticsearch output

## Architecture

| File | Purpose |
| --- | --- |
| `server.js` | the service implementation; run directly, it starts a single instance |
| `cluster.js` | starts one process for each available core up to `MAXIMUM_CORES` |
| `application.wadl` | WADL description of the service |
| `root.html` | service landing page |
| `runtests.js` | test runner, started with `npm test` |

## Tests

Tests run from the `service` directory and need a `configuration.json` that
points to a running MongoDB:

```bash
npm install
npm test
```

`runtests.js` starts the service and sends requests to it. The exit code is 0
only if every test passed, and a test that has not answered after 10 seconds is
reported as failed.

The suite does not read or change the configured database. It creates a
database named after the configured one with `_runtests` appended, and removes
it at the end. With `MONGO.AUTHENTICATE` enabled, the configured user needs
write access to that database.

The documents it loads are those in
`collector/tests/expected/mapped_documents.json`, which the collector tests
keep frozen. The service is therefore tested on what the collector stores.

## Contribution

Issues and pull requests are managed on <https://github.com/EIDA/wfcatalog>.

## Code quality requirements

- [x] Unit tests (`npm test`)
- [ ] Linted code
- [ ] Dependencies lock
- [x] CI jobs: `.github/workflows/publish-container.yml` builds and publishes the container images on push
