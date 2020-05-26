#!/usr/bin/env python3
'''
Generation of all dat files at 100m spacing.
Preprocessing so the website doesn't have to

This will take a long time to process!
'''
import os

from MAVProxy.modules.mavproxy_map import srtm
from terrain_gen import create_degree

downloader = srtm.SRTMDownloader(debug=False, cachedir='./srtmcache')
downloader.loadFileList()

if __name__ == '__main__':

    targetFolder = os.path.join(os.getcwd(), "processedTerrain")
    #create folder if required
    try:
        os.mkdir(targetFolder)
    except FileExistsError:
        pass

    # Loop over the SRTM range - -60->60 latitude and all longitudes
    for long in range(-180, 180):
        for lat in range (-60, 60):
            create_degree(downloader, lat, long, targetFolder, 100)

