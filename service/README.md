# EIDA-NG WFCatalog
[Node](https://nodejs.org/en/) powered implementation for the EIDA WFCatalog.

# Service Requirements and Documentation
* NodeJS
* npm
* MongoDB populated by the WFCatalog collector

`npm` is a package manager for Node, and is usually included with an installation of Node. Documentation on the service can be found on [Redmine](https://dev.knmi.nl/projects/eida/wiki/WFCatalog#3-EIDANG-WFCatalog-Web-Service).

# Download the source
The source code of the WFCatalog Service can be downloaded through git: `git clone https://github.com/EIDA/EIDA.git` and is located in the `wfcatalog/service` subdirectory that will be our working directory during setup.

# Configuring the service
It is important to edit the `configuration.json` properly before starting the service. Pay particular attention to th
e following options:

* `NAME` - Service name
* `ARCHIVE` - Name of archive running the service
* `HOST` - host where the service will be available
* `PORT` - port where the service will be available
* `MONGO.HOST` - host:port/database of the collections used by the service

# Installing dependencies and testing the service
The service dependencies must be installed through `npm install` and the installation can be tested through `npm test`.

# Running the service
To start a single instance or cluster of processes of the service issue `node server.js` or `node cluster.js` respectively. The cluster module will run one process for each available core on the machine up to the configured limit of `MAXIMUM_CORES` in the configuration.json.

# Installation through Docker
Alternatively, the service can also be run as a Docker container by building the Dockerfile and requires no installation of `Node/npm`. A detailed description of the installation can be found on the internal [Redmine Wiki](https://dev.knmi.nl/projects/eida/wiki/WFCatalogDocker).
