import uuid
import os
import subprocess
import zipfile
import urllib.request
import gzip
from io import BytesIO
import time
import json

from flask import Flask, render_template, request, flash
from threading import Thread, Lock

queue_lock = Lock()

def run_build(taskfile):
    # run a build with parameters from task
    task = json.loads(open(taskfile).read())
    builddir = '/tmp/build'
    subprocess.run(['./waf', 'configure', 
                    '--board', task['board'], 
                    '--out', builddir, 
                    '--extra-hwdef', task['extra_hwdef']],
                    cwd = task['sourcedir'])
    subprocess.run(['./waf', 'clean'], cwd = task['sourcedir'])
    subprocess.run(['./waf', task['vehicle']], cwd = task['sourcedir'])

# background thread to check for queued build requests
def check_queue():
    while(1):
        queue_lock.acquire()
        listing = os.listdir(os.path.join(appdir, 'buildqueue'))
        queue_lock.release()
        if listing:
            for token in listing:
                print(token)
                builddir = os.path.join('/private/tmp/build', token)
                buildqueue_dir = os.path.join(appdir, 'buildqueue', token)
                # check if build exists
                if os.path.isdir(builddir):
                    print("Build already exists")
                else:
                    # run build and rename build directory
                    print(buildqueue_dir)
                    run_build(os.path.join(buildqueue_dir, 'q.json'))
                    f = open(os.path.join(buildqueue_dir, 'q.json'))
                    task = json.load(f)
                    os.rename(os.path.join('/private/tmp/build', task['board']), builddir)
                
                # remove working files
                os.remove(os.path.join(buildqueue_dir, 'extra_hwdef.dat'))
                os.remove(os.path.join(buildqueue_dir, 'q.json'))
                os.rmdir(os.path.join(buildqueue_dir))

                print("Build successful")
        #time.sleep(1)

# define source and app directories
sourcedir = os.path.abspath('../ardupilot/')
appdir = os.path.abspath(os.curdir)

if not os.path.isdir('buildqueue'):
    os.mkdir('buildqueue')

thread = Thread(target=check_queue, args=())
thread.daemon = True
thread.start()

# Directory of this file
this_path = os.path.dirname(os.path.realpath(__file__))

# Where the user requested tile are stored
output_path = os.path.join(this_path, '..', 'userRequestFirmware')

# Where the data database is
tile_path = os.path.join(this_path, '..', 'data', 'tiles')

# The output folder for all gzipped build requests
app = Flask(__name__, static_url_path='/builds', static_folder=output_path,)

#def compressFiles(fileList, uuidkey):
    # create a zip file comprised of dat.gz tiles
    #zipthis = os.path.join(output_path, uuidkey + '.zip')

    # create output dirs if needed
    #try:
    #    os.makedirs(output_path)
    #except OSError:
    #    pass
    #try:
    #    os.makedirs(tile_path)
    #except OSError:
    #    pass

    #try:
    #    with zipfile.ZipFile(zipthis, 'w') as terrain_zip:
    #        for fn in fileList:
    #            if not os.path.exists(fn):
    #                #download if required
    #                print("Downloading " + os.path.basename(fn))
    #                g = urllib.request.urlopen('https://terrain.ardupilot.org/data/tiles/' +
    #                                           os.path.basename(fn))
    #                print("Downloaded " + os.path.basename(fn))
    #                with open(fn, 'b+w') as f:
    #                    f.write(g.read())

                # need to decompress file and pass to zip
    #            with gzip.open(fn, 'r') as f_in:
    #                myio = BytesIO(f_in.read())
    #                print("Decomp " + os.path.basename(fn))

                    # and add file to zip
    #                terrain_zip.writestr(os.path.basename(fn)[:-3], myio.read(),
    #                                     compress_type=zipfile.ZIP_DEFLATED)

    #except Exception as ex:
    #    print("Unexpected error: {0}".format(ex))
    #    return False

    #return True

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['GET', 'POST'])
def generate():
    #if request.method == 'POST':
    features = []
    task = {}

    # fetch features from user input
    for i in range(1,8):
        value = request.form["option" + str(i)]
        features.append(value)
        undefine = "undef " + value.split()[1]
        features.insert(0,undefine)
    extra_hwdef = '\n'.join(features)

    #print("features: ", features)

    queue_lock.acquire()

    # create extra_hwdef.dat file and obtain md5sum
    file = open('buildqueue/extra_hwdef.dat',"w")
    file.write(extra_hwdef)
    file.close()
    md5sum = subprocess.check_output(['md5sum', 'buildqueue/extra_hwdef.dat'],
                                        encoding = 'utf-8')
    md5sum = md5sum[:len(md5sum)-29]
    os.remove('buildqueue/extra_hwdef.dat')

    # obtain git-hash of source
    git_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD'], 
                                        cwd = sourcedir,
                                        encoding = 'utf-8')
    git_hash = git_hash[:len(git_hash)-1]

    # create directories using concatenated token of git-hash and md5sum of hwdef
    token = git_hash + "-" + md5sum
    buildqueue_dir = os.path.join(appdir, 'buildqueue', token)
    if not os.path.isdir(buildqueue_dir):
        os.mkdir(buildqueue_dir)
    file = open(os.path.join(buildqueue_dir, 'extra_hwdef.dat'),"w")
    file.write(extra_hwdef)
    file.close()
    
    # fill dictionary of variables and create json file
    task['hwdef_md5sum'] = md5sum
    task['git_hash'] = git_hash
    task['sourcedir'] = sourcedir
    task['extra_hwdef'] = os.path.join(buildqueue_dir, 'extra_hwdef.dat')
    task['board'] = request.form["board"]
    task['vehicle'] = request.form["vehicle"]
    jfile = open(os.path.join(buildqueue_dir, 'q.json'), "w")
    jfile.write(json.dumps(task))
    jfile.close()

    queue_lock.release()

    #print(task)

    return render_template('building.html')

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
    #else:
    #    print("Bad get")
    #    return render_template('generate.html', error="Need to use POST, not GET")

@app.route('/home', methods=['POST'])
def home():
    return render_template('index.html')

if __name__ == "__main__":
    app.run()
