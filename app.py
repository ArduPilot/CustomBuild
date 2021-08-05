#!/usr/bin/env python3

import os
import subprocess
import json
import pathlib
import shutil
import glob
from distutils.dir_util import copy_tree
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
    app.logger.info('Creating ' + dir_path)
    pathlib.Path(dir_path).mkdir(parents=True, exist_ok=True)


def run_build(taskfile, tmpdir, outdir):
    # run a build with parameters from task
    app.logger.info('Opening ' + taskfile)
    task = json.loads(open(taskfile).read())
    app.logger.info('Removing ' + taskfile)
    os.remove(taskfile)
    remove_directory_recursive(tmpdir)
    create_directory(tmpdir)
    if not os.path.isfile(os.path.join(outdir, 'extra_hwdef.dat')):
        app.logger.error('Build aborted, missing extra_hwdef.dat')
    app.logger.info('Creating build.log')
    #os.remove(os.path.join(outdir, 'build.log'))
    with open(os.path.join(outdir, 'build.log'), 'a') as log:
        app.logger.info('Submodule update')
        subprocess.run(['git', 'submodule',
                        'update', '--recursive', 
                        '--force', '--init'], 
                        stdout=log, stderr=log)
        app.logger.info('Running waf configure')
        subprocess.run(['./waf', 'configure', 
                        '--board', task['board'], 
                        '--out', tmpdir, 
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
        json_files = list(filter(os.path.isfile, 
                                    glob.glob(os.path.join(outdir_parent, 
                                                '*', 'q.json'))))
        json_files.sort(key=lambda x: os.path.getmtime(x))
        queue_lock.release()
        if json_files:
            for taskfile in json_files:
                #taskfile = os.path.join(outdir, file)
                app.logger.info('Opening ' + taskfile)
                task = json.loads(open(taskfile).read())
                outdir = os.path.join(outdir_parent, task['token'])
                tmpdir = os.path.join(tmpdir_parent, task['token'])
                # check if build exists
                #if os.path.isdir(outdir):
                    #app.logger.info('Build already exists')
                    #app.logger.info('Removing ' + taskfile)
                    #os.remove(taskfile)
                #else:
                try:
                    # run build and rename build directory
                    app.logger.info('Opening ' + taskfile)
                    f = open(taskfile)
                    app.logger.info('Loading ' + taskfile)
                    task = json.load(f)
                    run_build(taskfile, tmpdir, outdir)
                    app.logger.info('Copying build files from %s to %s', 
                                    os.path.join(tmpdir, task['board']),
                                    outdir)
                    copy_tree(os.path.join(tmpdir, task['board'], 'bin'), 
                                outdir)
                    app.logger.info('Build successful!')
                    app.logger.info('Removing ' + tmpdir)
                    remove_directory_recursive(tmpdir)
                    # remove extra_hwdef.dat
                    app.logger.info('Removing ' + 
                                    os.path.join(outdir, 'extra_hwdef.dat'))
                    os.remove(os.path.join(outdir, 'extra_hwdef.dat'))
                
                except:
                    app.logger.info('Build failed')
                    continue

import optparse
parser = optparse.OptionParser("app.py")

parser.add_option("", "--basedir", type="string",
                  default="..", help="base directory")
cmd_opts, cmd_args = parser.parse_args()
                
# define directories
basedir = os.path.abspath(cmd_opts.basedir)
sourcedir = os.path.abspath(os.path.join(basedir, 'ardupilot'))
outdir_parent = os.path.join(basedir, 'builds')
tmpdir_parent = os.path.join(basedir, 'tmp')

# Directory of this file
this_path = os.path.dirname(os.path.realpath(__file__))

# Where the user requested tile are stored
output_path = os.path.join(this_path, '..', 'userRequestFirmware')

# Where the data database is
tile_path = os.path.join(this_path, '..', 'data', 'tiles')

# The output folder for all gzipped build requests
app = Flask(__name__, static_url_path='/builds', 
            static_folder=output_path, template_folder='templates')

if not os.path.isdir(outdir_parent):
    create_directory(outdir_parent)

thread = Thread(target=check_queue, args=())
thread.daemon = True
thread.start()

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
            value = request.form['option' + str(i)]
            features.append(value)
            undefine = 'undef ' + value.split()[1]
            features.insert(0,undefine)
        extra_hwdef = '\n'.join(features)

        queue_lock.acquire()

        # create extra_hwdef.dat file and obtain md5sum
        app.logger.info('Creating ' + 
                        os.path.join(outdir_parent, 'extra_hwdef.dat'))
        file = open(os.path.join(outdir_parent, 'extra_hwdef.dat'),'w')
        app.logger.info('Writing\n' + extra_hwdef)
        file.write(extra_hwdef)
        file.close()
        app.logger.info('Getting md5sum')
        md5sum = subprocess.check_output(['md5sum', 
                                            os.path.join(outdir_parent, 
                                            'extra_hwdef.dat')],
                                            encoding = 'utf-8')
        md5sum = md5sum[:len(md5sum)
                        -(3+len(os.path.join(outdir_parent, 'extra_hwdef.dat')))]
        app.logger.info('md5sum = ' + md5sum)
        app.logger.info('Removing ' + 
                        os.path.join(outdir_parent, 'extra_hwdef.dat'))
        os.remove(os.path.join(outdir_parent, 'extra_hwdef.dat'))

        # obtain git-hash of source
        app.logger.info('Getting git hash')
        git_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD'], 
                                            cwd = sourcedir,
                                            encoding = 'utf-8')
        git_hash = git_hash[:len(git_hash)-1]
        app.logger.info('Git hash = ' + git_hash)

        # create directories using concatenated token 
        # of vehicle, board, git-hash of source, and md5sum of hwdef
        vehicle = request.form['vehicle']
        board = request.form['board']
        token = vehicle + '-' + board + '-' + git_hash + '-' + md5sum
        app.logger.info('token = ' + token)
        outdir = os.path.join(outdir_parent, token)
        
        if os.path.isdir(outdir):
            app.logger.info('Build already exists')
        else:
            app.logger.info('Creating ' + outdir)
            create_directory(outdir)
            # create build.log
            app.logger.info('Creating build.log')
            build_log = open(os.path.join(outdir, 'build.log'), 'w')
            build_log.write('Waiting for build to start...\n')
            build_log.close()
            # create hwdef.dat
            app.logger.info('Opening ' + os.path.join(outdir, 'extra_hwdef.dat'))
            file = open(os.path.join(outdir, 'extra_hwdef.dat'),'w')
            app.logger.info('Writing\n' + extra_hwdef)
            file.write(extra_hwdef)
            file.close()
            # fill dictionary of variables and create json file
            task['hwdef_md5sum'] = md5sum
            task['git_hash'] = git_hash
            task['token'] = token
            task['sourcedir'] = sourcedir
            task['extra_hwdef'] = os.path.join(outdir, 'extra_hwdef.dat')
            task['board'] = board
            task['vehicle'] = vehicle
            app.logger.info('Opening ' + os.path.join(outdir, 'q.json'))
            jfile = open(os.path.join(outdir, 'q.json'), 'w')
            app.logger.info('Writing task file to ' + os.path.join(outdir, 'q.json'))
            jfile.write(json.dumps(task))
            jfile.close()

        queue_lock.release()

        apache_build_dir = 'http://localhost:8080/' \
                            + os.path.join('builds', token)
        apache_build_log = 'http://localhost:8080/' \
                            + os.path.join('builds', token, 'build.log')
        apache_all_builds = 'http://localhost:8080/' \
                            + 'builds'
        app.logger.info('Rendering generate.html')
        return render_template('generate.html', 
                                apache_build_dir=apache_build_dir, 
                                apache_build_log=apache_build_log,
                                apache_all_builds=apache_all_builds,
                                token=token)
    
    except:
        return render_template('generate.html', error='Error occured')

@app.route('/home', methods=['POST'])
def home():
    app.logger.info('Rendering index.html')
    return render_template('index.html')

if __name__ == '__main__':
    app.run()
