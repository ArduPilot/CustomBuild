import uuid
import os
import subprocess
import zipfile
import urllib.request
import gzip
from io import BytesIO
import time

from flask import Flask # using flask as the framework
from flask import render_template
from flask import request

# Directory of this file
this_path = os.path.dirname(os.path.realpath(__file__))

# Where the user requested tile are stored
output_path = os.path.join(this_path, '..', 'userRequestFirmware')

# Where the data database is
tile_path = os.path.join(this_path, '..', 'data', 'tiles')

# The output folder for all gzipped build requests
app = Flask(__name__, static_url_path='/builds', static_folder=output_path,)

def compressFiles(fileList, uuidkey):
    # create a zip file comprised of dat.gz tiles
    zipthis = os.path.join(output_path, uuidkey + '.zip')

    # create output dirs if needed
    try:
        os.makedirs(output_path)
    except OSError:
        pass
    try:
        os.makedirs(tile_path)
    except OSError:
        pass

    try:
        with zipfile.ZipFile(zipthis, 'w') as terrain_zip:
            for fn in fileList:
                if not os.path.exists(fn):
                    #download if required
                    print("Downloading " + os.path.basename(fn))
                    g = urllib.request.urlopen('https://terrain.ardupilot.org/data/tiles/' +
                                               os.path.basename(fn))
                    print("Downloaded " + os.path.basename(fn))
                    with open(fn, 'b+w') as f:
                        f.write(g.read())

                # need to decompress file and pass to zip
                with gzip.open(fn, 'r') as f_in:
                    myio = BytesIO(f_in.read())
                    print("Decomp " + os.path.basename(fn))

                    # and add file to zip
                    terrain_zip.writestr(os.path.basename(fn)[:-3], myio.read(),
                                         compress_type=zipfile.ZIP_DEFLATED)

    except Exception as ex:
        print("Unexpected error: {0}".format(ex))
        return False

    return True

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['GET', 'POST'])
def generate():
    if request.method == 'POST':
        # request.form['username']
        features = []
        for i in range(1,8):
            value = request.form["option" + str(i)]
            features.append(value)
            undefine = "undef " + value.split()[1]
            features.insert(0,undefine)
        extra_hwdef = '\n'.join(features)

        print("features: ", features)

        print("running...")

        file = open('extra_hwdef.dat',"w")
        
        file.write(extra_hwdef)
        file.close()

        git_hash = subprocess.check_output(['git', 'rev-parse', 'master'])
        git_hash = git_hash[:len(git_hash)-1]

        md5sum = subprocess.check_output(['md5sum', 'extra_hwdef.dat'])
        md5sum = md5sum[:len(md5sum)-18]

        builddir = '/tmp/build'
        sourcedir = '../ardupilot/'
        appdir = os.path.abspath(os.curdir)
        board = 'Beastf7'
        subprocess.run(['./waf', 'configure', 
                        '--board', board, 
                        '--out', builddir, 
                        '--extra-hwdef', os.path.join(appdir, 'extra_hwdef.dat')],
                        cwd = sourcedir)
        subprocess.run(['./waf', 'copter'], cwd = sourcedir)

        print("git hash: ", git_hash)
        print("md5sum: ", md5sum)
        print("token: ", git_hash+md5sum)

        # UUID for this terrain generation
        uuidkey = str(uuid.uuid1())


        # remove duplicates
        #filelist = list(dict.fromkeys(filelist))
        #print(filelist)

        #compress
        #success = compressFiles(filelist, uuidkey)

        # as a cleanup, remove any generated terrain older than 24H
        #for f in os.listdir(output_path):
        #    if os.stat(os.path.join(output_path, f)).st_mtime < time.time() - 24 * 60 * 60:
        #        print("Removing old file: " + str(os.path.join(output_path, f)))
        #        os.remove(os.path.join(output_path, f))

        #if success:
        #    print("Generated " + "/terrain/" + uuidkey + ".zip")
        #    return render_template('generate.html', urlkey="/terrain/" + uuidkey + ".zip",
        #                           uuidkey=uuidkey, outsideLat=outsideLat)
        #else:
        #    print("Failed " + "/terrain/" + uuidkey + ".zip")
        #    return render_template('generate.html', error="Cannot generate terrain",
        #                           uuidkey=uuidkey)
    else:
        print("Bad get")
        return render_template('generate.html', error="Need to use POST, not GET")

if __name__ == "__main__":
    app.run()
