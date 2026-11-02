---
author: Nikos Sokos
created: 2026-11-02
service: wfcatalog
tags:
  - operator
---

# Installation

## Requirements

- NodeJS
- npm
- MongoDB populated by the WFCatalog collector

`npm` is a package manager for Node, and is usually included with an installation
of Node.

## Install

### Download the source

The source code of the WFCatalog Service can be downloaded through
git: `git clone https://github.com/EIDA/wfcatalog.git` and is located in
the `service` subdirectory that will be our working directory during setup.

### Installing dependencies and testing the service

The service dependencies must be installed through `npm install` and the
installation can be tested through `npm test`.

Before starting, edit `configuration.json` as described in [Configuration](configuration.md).

### Running the service

To start a single instance or cluster of processes of the service
issue `node server.js` or `node cluster.js` respectively. The cluster module
will run one process for each available core on the machine up to the
configured limit of `MAXIMUM_CORES` in the configuration.json.

### Installation through Docker

Alternatively, the service can also be run as a Docker container by building
the Dockerfile and requires no installation of `Node/npm`. The image runs
`npm start` and exposes port 8888. A published image is available as
`ghcr.io/eida/wfcatalog`.
