# Copyright (C) 2017 
# Triantafyllis Nikolaos
# EIDA Technical Committee @ National Observatory of Athens, Greece
#
# This script is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This script is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this script.  If not, see <http://www.gnu.org/licenses/>.


#!/bin/bash

# This script sets the white list with the channels that are distributed through FDSNWS.
# In that case, WFCatalog will collect meta-data only from EIDA served data 
# and not from the entire archive.
# Run this script just before daily WFCatalog Collection.


# directory path where the config.json is going to be saved
path='/home/sysop/myWFCatalogCollector'

# url of the FDSNWS where we request all channels for all networks that we serve
url='http://eida.gein.noa.gr/fdsnws/station/1/query?network=*&level=channel&format=text'


# set the white list variable with all the found channels
text=""
while read line; do
  text+=", \"$line\""
done < <(curl $url | tail -n +2 | awk -F '|' '{print $1"."$2".*."$4".*"}')

white="\"WHITE\": [${text:2}],"

sed -i "s/\"WHITE\(.*\),/$white/" $path/config.json


