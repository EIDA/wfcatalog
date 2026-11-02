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
| `server.js` | starts a single instance of the service |
| `cluster.js` | starts one process for each available core up to `MAXIMUM_CORES` |
| `wfcatalog.js` | the service implementation |
| `application.wadl` | WADL description of the service |
| `root.html` | service landing page |
| `runtests.js` | test runner, started with `npm test` |

## Contribution

Issues and pull requests are managed on <https://github.com/EIDA/wfcatalog>.

## Code quality requirements

- [x] Unit tests (`npm test`)
- [ ] Linted code
- [ ] Dependencies lock
- [x] CI jobs: `.github/workflows/publish-container.yml` builds and publishes the container images on push
