# Dockerizing NodeJs: Dockerfile for building NodeJS-APP images
# Based on node:argon, followed the instructions from:
# https://nodejs.org/en/docs/guides/nodejs-docker-webapp/
#
# Description:
# BASE NODEJS+APP inside
# 
# imageName:'node-ws-wfcat:1'
# Use:
# build command (inside source app dir): sudo docker build -t "<docker_user>/node-ws-wfcat:1" .
# run command: sudo docker run -p 8888:8888 --link<container-mongo>:mongodb -d <docker_user>/node-ws-wfcat:1
#

FROM node:argon

MAINTAINER massimo.fares@ingv.it

# Create app directory
RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

# Install app dependencies
COPY package.json /usr/src/app/
RUN npm install

# Bundle app source
COPY . /usr/src/app

# Create log directory (see the configuration.json file for matching this value)
RUN mkdir -p /var/log/wfcatalog

# see the configuration.json file for matching this value ("PORT") and note that "HOST" must have  "0.0.0.0" for localhost
EXPOSE 8888
CMD [ "npm", "start" ]
