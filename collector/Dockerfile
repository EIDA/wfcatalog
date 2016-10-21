# Dockerizing Obspy & MongoDB python client: Dockerfile for building wfcatalog-collector images
# Based on ubuntu:14.04, installs  following the instructions from:
# https://dev.knmi.nl/projects/eida/wiki/WFCatalog
# Description:
# BASE OBSPY / MONGOCLIENT
# 
# imageName:'wfcatalog-collector:1'
# Use:
# build command: sudo docker build -t "[<docker_user>/]wfcatalog-collector:1" .
# run command: sudo docker run -ti -v /home/massimo/STORE/archive_B:/usr/src/collector/datastore -v /home/massimo/A__WORK/test_wfcatalog:/usr/src/collector --link mongo_server_wf:mongodb --name coll_wfcat  massimo1962/wfcatalog:1


FROM ubuntu:14.04

MAINTAINER Mathijs Koymans

RUN apt-get update

#install dependencies
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y wget git vim python-dev python-pycurl python-simplejson \
    libcurl4-gnutls-dev libssl-dev pkg-config gcc-4.9 \
    python python-psutil python-requests python-jsonschema \
    python-setuptools python-dev build-essential python-pip \
    libxml2-dev libxslt1-dev libz-dev libfreetype6-dev \
    python-numpy python-scipy python-matplotlib

# mongo driver
RUN pip install pymongo

#make app dir
RUN mkdir -p /usr/src/collector

# obspy
WORKDIR /
RUN git clone https://github.com/obspy/obspy.git
WORKDIR /obspy

RUN pip install -e .

# Copy in app directory / optional we can mount the source dir instead of copy
WORKDIR /usr/src/collector

# Copy the application source to this directory
COPY . /usr/src/collector






    
    
    
    
    
    
