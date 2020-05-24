# ArduPilot terrain generator

## Summary

This is a website that pre-generates terrain files for Ardupilot. The user enters in the details
of the area they wish the generate terrain for, then the website will download (if not already cached)
the raw terrain from ardupilot.org and process it. The user will end up with a terrain.zip that they
then need to unzip to a "terrain" folder on the SD card in their flight controller.

## For developers

This website uses the flask library.

To install dependencies:

``pip install flask wheel numpy mavproxy crc16 pytest``

To run:

```
export FLASK_APP=app.py
flask run
```

The cached terrain files are stored in ./srtmcache

The unzipped processed files are temporarily stored in ./outputTer-tmp. These are deleted upon the zipping into a single
downloadable file

The downloadable files are stored in ./outputTer

Each user request is given a UUID, which is incorporated into the folder/filename of the terrain files.

To run the unit tests, type ``pytest``

## Deployment

Use gunicorn for deployment:

``pip install gunicorn``

``gunicorn app:app``
