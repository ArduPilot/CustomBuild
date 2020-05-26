import uuid
import threading
import time
import queue
import os
import zipfile
import shutil
import sys

from flask import Flask
from flask import render_template
from flask import request
from flask import json, jsonify

from MAVProxy.modules.mavproxy_map import srtm
from terrain_gen import add_offset

# The output folder for all zipped terrain requests
app = Flask(__name__,static_url_path='/terrain', static_folder='outputTer',)

def clamp(n, smallest, largest):
    return max(smallest, min(n, largest))

def getDatFile(lat, lon):
    if lat < 0:
        NS = 'S'
    else:
        NS = 'N'
    if lon < 0:
        EW = 'W'
    else:
        EW = 'E'
    return "%c%02u%c%03u.DAT" % (NS, min(abs(int(lat)), 99),
                                    EW, min(abs(int(lon)), 999))

def compressFiles(fileList, uuidkey, outfolder):
    # create a zip file comprised of dat tiles
    zipthis = os.path.join(os.getcwd(), outfolder, uuidkey + '.zip')
    terrain_zip = zipfile.ZipFile(zipthis, 'w')
     
    try:
        for fileSingle in fileList:
            # terrain_zip.write(os.path.join(folder, file), file, compress_type = zipfile.ZIP_DEFLATED)
            terrain_zip.write(fileSingle, os.path.basename(fileSingle), compress_type = zipfile.ZIP_DEFLATED)
    except:
        print("Unexpected error:", sys.exc_info()[0])
        terrain_zip.close()
        return False
        
     
    terrain_zip.close()
    return True

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods = ['GET', 'POST'])
def generate():
    if request.method == 'POST':
        # parse and sanitise the input
        try:
            # request.form['username']
            lat = float(request.form['lat'])
            lon = float(request.form['long'])
            radius = int(request.form['radius'])
            assert lat < 90
            assert lon < 180
            assert lat > -90
            assert lon > -180
            radius = clamp(radius, 1, 400)
        except:
            print("Bad data")
            return render_template('generate.html', error = "Error with input")

        # UUID for this terrain generation
        uuidkey = str(uuid.uuid1())

        # get a list of files required to cover area
        filelist = []
        done = set()
        for dx in range(-radius, radius):
            for dy in range(-radius, radius):
                (lat2,lon2) = add_offset(lat*1e7, lon*1e7, dx*1000.0, dy*1000.0)
                lat_int = int(round(lat2 * 1.0e-7))
                lon_int = int(round(lon2 * 1.0e-7))
                tag = (lat_int, lon_int)
                if tag in done:
                    #numpercent += 1
                    continue
                done.add(tag)
                #create_degree(downloader, lat_int, lon_int, folderthis, spacing)
                filelist.append(os.path.join(os.getcwd(), "processedTerrain", getDatFile(lat_int, lon_int)))

        #create_degree(downloader, lat, lon, folderthis, spacing)
        #filelist.append(getDatFile(lat, lon))
        print(filelist)

        #compress
        success = compressFiles(filelist, uuidkey, 'outputTer')
        
        if success:
            print("Generated " + "/terrain/" + uuidkey + ".zip")
            return render_template('generate.html', urlkey="/terrain/" + uuidkey + ".zip", uuidkey=uuidkey)
        else:
            print("Failed " + "/terrain/" + uuidkey + ".zip")
            return render_template('generate.html', error = "Processing terrain", uuidkey=uuidkey)
    else:
        print("Bad get")
        return render_template('generate.html', error = "Need to use POST, not GET")

