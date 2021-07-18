#!/usr/bin/env python3

import uuid
import os
import sys
import subprocess
import zipfile
import urllib.request
import gzip
from io import BytesIO
import time
import json
import pathlib
import shutil
from distutils.dir_util import copy_tree
import logging

from flask import Flask, render_template, request, flash
from threading import Thread, Lock

queue_lock = Lock()

from logging.config import dictConfig

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})

'''
Directory structure:
  - all paths relative to where the app starts
  - waf builds go into build
  - json queued build files go into buildqueue
  - resulting builds go into done
  - ardupilot is in ardupilot directory
  - templates in CustomBuild/templates

'''

#def get_template(filename):
#    return render_template(filename)

def remove_directory_recursive(dirname):
    # remove a directory recursively
    app.logger.info('removing directory ' + dirname)
    if not os.path.exists(dirname):
        return
    f = pathlib.Path(dirname)
    if f.is_file():
        f.unlink()
    else:
        shutil.rmtree(f, True)


def create_directory(dir_path):
    # create a directory, don't fail if it exists
    app.logger.info('creating ' + dir_path)
    pathlib.Path(dir_path).mkdir(parents=True, exist_ok=True)


def run_build(taskfile, builddir, done_dir):
    # run a build with parameters from task
    app.logger.info('Opening q.json')
    task = json.loads(open(taskfile).read())
    remove_directory_recursive(os.path.join(sourcedir, done_dir))
    remove_directory_recursive(os.path.join(sourcedir, builddir))
    create_directory(os.path.join(sourcedir, done_dir))
    create_directory(os.path.join(sourcedir, builddir))
    app.logger.info('Creating build.log')
    with open(os.path.join(sourcedir, done_dir, 'build.log'), "wb") as log:
        app.logger.info('Submodule update')
        subprocess.run(['git', 'submodule',
                        'update', '--recursive', 
                        '--force', '--init'], stdout=log, stderr=log)
        app.logger.info('Running waf configure')
        subprocess.run(['./waf', 'configure', 
                        '--board', task['board'], 
                        '--out', builddir, 
                        '--extra-hwdef', task['extra_hwdef']],
                        cwd = task['sourcedir'], 
                        stdout=log, stderr=log)
        app.logger.info('Running clean')
        subprocess.run(['./waf', 'clean'], cwd = task['sourcedir'], 
                        stdout=log, stderr=log)
        app.logger.info('Running build')
        subprocess.run(['./waf', task['vehicle']], cwd = task['sourcedir'], 
                        stdout=log, stderr=log)

# background thread to check for queued build requests
def check_queue():
    while(1):
        queue_lock.acquire()
        listing = os.listdir('buildqueue')
        queue_lock.release()
        if listing:
            for token in listing:
                builddir = 'build'
                done_dir = os.path.join('done', token)
                buildqueue_dir = os.path.join('buildqueue', token)
                # check if build exists
                if os.path.isdir(os.path.join(sourcedir, done_dir)):
                    app.logger.info('Build already exists')
                else:
                    try:
                        # run build and rename build directory
                        app.logger.info('Creating ' + 
                                        os.path.join(buildqueue_dir, 'q.json'))
                        f = open(os.path.join(buildqueue_dir, 'q.json'))
                        app.logger.info('Loading ' + 
                                        os.path.join(buildqueue_dir, 'q.json'))
                        task = json.load(f)
                        run_build(os.path.join(buildqueue_dir, 'q.json'), 
                                    builddir, done_dir)
                        app.logger.info('Copying build files from %s to %s', 
                                        os.path.join(sourcedir, builddir, task['board']),
                                        os.path.join(sourcedir, done_dir))
                        copy_tree(os.path.join(sourcedir, builddir, task['board']),
                                    os.path.join(sourcedir, done_dir))
                        app.logger.info('Build successful!')
                    
                    except:
                        app.logger.info('Build failed')
                        continue
                
                # remove working files
                app.logger.info('Removing ' + 
                                os.path.join(buildqueue_dir, 'extra_hwdef.dat'))
                os.remove(os.path.join(buildqueue_dir, 'extra_hwdef.dat'))
                app.logger.info('Removing ' + 
                                os.path.join(buildqueue_dir, 'q.json'))
                os.remove(os.path.join(buildqueue_dir, 'q.json'))
                app.logger.info('Removing ' + 
                                os.path.join(buildqueue_dir))
                os.rmdir(os.path.join(buildqueue_dir))

# define source and app directories
sourcedir = os.path.abspath(os.path.join('..', 'ardupilot'))
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
app = Flask(__name__, static_url_path='/builds', 
            static_folder=output_path, template_folder='templates')

@app.route('/')
def index():
    app.logger.info('Rendering index.html')
    return render_template('index.html')

@app.route('/generate', methods=['GET', 'POST'])
def generate():
    #if request.method == 'POST':
    features = []
    task = {}

    try:
        # fetch features from user input
        app.logger.info('Fetching features from user input')
        for i in range(1,8):
            value = request.form["option" + str(i)]
            features.append(value)
            undefine = "undef " + value.split()[1]
            features.insert(0,undefine)
        extra_hwdef = '\n'.join(features)

        #print("features: ", features)

        queue_lock.acquire()

        # create extra_hwdef.dat file and obtain md5sum
        app.logger.info('Creating ' + os.path.join('buildqueue', 'extra_hwdef.dat'))
        file = open(os.path.join('buildqueue', 'extra_hwdef.dat'),"w")
        app.logger.info('Writing\n' + extra_hwdef)
        file.write(extra_hwdef)
        file.close()
        app.logger.info('Getting md5sum')
        md5sum = subprocess.check_output(['md5sum', 'buildqueue/extra_hwdef.dat'],
                                            encoding = 'utf-8')
        md5sum = md5sum[:len(md5sum)-29]
        app.logger.info('md5sum = ' + md5sum)
        app.logger.info('Removing ' + os.path.join('buildqueue', 'extra_hwdef.dat'))
        os.remove(os.path.join('buildqueue', 'extra_hwdef.dat'))

        # obtain git-hash of source
        app.logger.info('Getting git hash')
        git_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD'], 
                                            cwd = sourcedir,
                                            encoding = 'utf-8')
        git_hash = git_hash[:len(git_hash)-1]
        app.logger.info('Git hash = ' + git_hash)

        # create directories using concatenated token of git-hash and md5sum of hwdef
        token = git_hash + "-" + md5sum
        app.logger.info('token = ' + token)
        buildqueue_dir = os.path.join(appdir, 'buildqueue', token)
        if not os.path.isdir(buildqueue_dir):
            app.logger.info('Creating ' + buildqueue_dir)
            os.mkdir(buildqueue_dir)
        app.logger.info('Opening ' + os.path.join(buildqueue_dir, 'extra_hwdef.dat'))
        file = open(os.path.join(buildqueue_dir, 'extra_hwdef.dat'),"w")
        app.logger.info('Writing\n' + extra_hwdef)
        file.write(extra_hwdef)
        file.close()
        
        # fill dictionary of variables and create json file
        task['hwdef_md5sum'] = md5sum
        task['git_hash'] = git_hash
        task['token'] = token
        task['sourcedir'] = sourcedir
        task['extra_hwdef'] = os.path.join(buildqueue_dir, 'extra_hwdef.dat')
        task['board'] = request.form["board"]
        task['vehicle'] = request.form["vehicle"]
        app.logger.info('Opening ' + os.path.join(buildqueue_dir, 'q.json'))
        jfile = open(os.path.join(buildqueue_dir, 'q.json'), "w")
        app.logger.info('Writing task file to ' + os.path.join(buildqueue_dir, 'q.json'))
        jfile.write(json.dumps(task))
        jfile.close()

        queue_lock.release()

        #print(task)

        apache_build_dir = "http://localhost:8080/" + token
        apache_build_log = "http://localhost:8080/" + token + "/build.log"
        app.logger.info('Rendering generate.html')
        return render_template('generate.html', 
                                apache_build_dir=apache_build_dir, 
                                apache_build_log=apache_build_log,
                                token=token)
    
    except:
        return render_template('generate.html', error='Error occured')

@app.route('/home', methods=['POST'])
def home():
    app.logger.info('Rendering index.html')
    return render_template('index.html')

if __name__ == "__main__":
    app.run()
