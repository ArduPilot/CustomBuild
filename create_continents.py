#!/usr/bin/env python3
'''
create ardupilot terrain database files as continents
'''
import os

from MAVProxy.modules.mavproxy_map import srtm
from argparse import ArgumentParser
from app import compressFiles

this_path = os.path.dirname(os.path.realpath(__file__))

parser = ArgumentParser(description='terrain data continent creator')

parser.add_argument("infolder", type=str, default="./files")
parser.add_argument("outfolder", type=str, default="./continents")

args = parser.parse_args()

downloader = srtm.SRTMDownloader(debug=False)
downloader.loadFileList()

continents = {}

# Create mappings of long/lat to continent
for (lonlat, contfile) in downloader.filelist.items():
    continent = str(contfile[0][:-1])
    filename = os.path.join(this_path, args.infolder, str(contfile[1]).split(".")[0] + ".DAT.gz")
    print(continent + " in " + filename)

    # add to database
    if continent != '' and continent != 'USGS':
        if continent in continents:
            continents[continent].append(filename)
        else:
            continents[continent] = [filename]

print("Continents are: " + str(continents.keys()))

# Add the files
for continent in continents:
    print("Processing: " + continent)
    files = continents[continent]
    compressFiles(files, continent, args.outfolder)
