# ArduPilot terrain generator

## Summary

This is a website that pre-generates terrain files for Ardupilot. The user enters in the details
of the area they wish the generate terrain for, then the website will generate a terrain.zip file containing
the relevant dat files. The user will download this file and then
then need to unzip to a "terrain" folder on the SD card in their flight controller.

## Pre-generation of Terrain

To ensure the website operates responsively, the terrain for the whole (-60 -> +60 latitude) world
must be pregenerated. This will take some time.

Run ``offline_gen.py`` to download the SRTM files from ardupilot.org and convert them to the dat
file format. These files will be stored in the processedTerrain folder.

## For developers

This website uses the flask library.

To install dependencies:

``pip install flask wheel uwsgi numpy mavproxy crc16 pytest``

To run:

```
python3 app.py
```

The unzipped processed files are temporarily stored in ./outputTer-tmp. These are deleted upon the zipping into a single
downloadable file

The downloadable files are stored in ./outputTer

Each user request is given a UUID, which is incorporated into the folder/filename of the terrain files.

To run the unit tests, type ``pytest``


