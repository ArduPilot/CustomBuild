#!/usr/bin/env python3

import os
import subprocess
import json
import pathlib
import shutil
import glob
import time
from distutils.dir_util import copy_tree
from flask import Flask, render_template, request, url_for, send_from_directory
from threading import Thread, Lock

#BOARDS = [ 'BeastF7', 'BeastH7' ]

def get_boards():
    '''return a list of boards to build'''
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_binaries.py",
                                                  os.path.join(sourcedir, 
                                                  'Tools', 'scripts', 
                                                  'board_list.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.AUTOBUILD_BOARDS
    
    #return BOARDS

# list of build options to offer
BUILD_OPTIONS = [ 
    ('EKF2', 'HAL_NAVEKF2_AVAILABLE', 'Enable EKF2'),
    ('EKF3', 'HAL_NAVEKF3_AVAILABLE', 'Enable EKF3'),
    ('DSP',  'HAL_WITH_DSP', 'Enable DSP'),
    ('SPRAYER', 'HAL_SPRAYER_ENABLED', 'Enable Sprayer'),
    ('PARACHUTE', 'HAL_PARACHUTE_ENABLED', 'Enable Parachute'),
    ('MOUNT', 'HAL_MOUNT_ENABLED', 'Enable Mount'),
    ('HOTT_TELEM', 'HAL_HOTT_TELEM_ENABLED', 'Enable HoTT Telemetry'),
    ('BATTMON_FUEL', 'HAL_BATTMON_FUEL_ENABLE', 'Enable Fuel BatteryMonitor')
    ]

VEHICLES = [ 'Copter', 'Plane', 'Rover', 'Sub' ]

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
    '''remove a directory recursively'''
    app.logger.info('Removing directory ' + dirname)
    if not os.path.exists(dirname):
        return
    f = pathlib.Path(dirname)
    if f.is_file():
        f.unlink()
    else:
        shutil.rmtree(f, True)


def create_directory(dir_path):
    '''create a directory, don't fail if it exists'''
    app.logger.info('Creating ' + dir_path)
    pathlib.Path(dir_path).mkdir(parents=True, exist_ok=True)


def run_build(task, tmpdir, outdir):
    '''run a build with parameters from task'''
    remove_directory_recursive(tmpdir_parent)
    create_directory(tmpdir)
    if not os.path.isfile(os.path.join(outdir, 'extra_hwdef.dat')):
        app.logger.error('Build aborted, missing extra_hwdef.dat')
    app.logger.info('Appending to build.log')
    logpath = os.path.abspath(os.path.join(outdir, 'build.log'))
    app.logger.info("LOGPATH: %s" % logpath)
    with open(logpath, 'a') as log:
        app.logger.info('Running waf configure')
        subprocess.run(['python3', './waf', 'configure',
                        '--board', task['board'], 
                        '--out', tmpdir, 
                        '--extra-hwdef', task['extra_hwdef']],
                        cwd = task['sourcedir'], 
                        stdout=log, stderr=log)
        app.logger.info('Running clean')
        subprocess.run(['python3', './waf', 'clean'],
                        cwd = task['sourcedir'], 
                        stdout=log, stderr=log)
        app.logger.info('Running build')
        subprocess.run(['python3', './waf', task['vehicle']],
                        cwd = task['sourcedir'],
                        stdout=log, stderr=log)

def sort_json_files():
    json_files = list(filter(os.path.isfile,
                             glob.glob(os.path.join(outdir_parent,
                                                    '*', 'q.json'))))
    json_files.sort(key=lambda x: os.path.getmtime(x))
    return json_files

def check_queue():
    '''thread to continuously run queued builds'''
    queue_lock.acquire()
    json_files = sort_json_files()
    queue_lock.release()
    if len(json_files) == 0:
        return
    # remove multiple build requests from same ip address (keep newest)
    queue_lock.acquire()
    ip_list = []
    for f in json_files:
        file = json.loads(open(f).read())
        ip_list.append(file['ip'])
    seen = set()
    ip_list.reverse()
    for index, value in enumerate(ip_list):
        if value in seen:
            file = json.loads(open(json_files[-index-1]).read())
            outdir_to_delete = os.path.join(outdir_parent, file['token'])
            remove_directory_recursive(outdir_to_delete)
        else:
            seen.add(value)
    queue_lock.release()
    if len(json_files) == 0:
        return
    # open oldest q.json file
    json_files = sort_json_files()
    taskfile = json_files[0]
    app.logger.info('Opening ' + taskfile)
    task = json.loads(open(taskfile).read())
    app.logger.info('Removing ' + taskfile)
    os.remove(taskfile)
    outdir = os.path.join(outdir_parent, task['token'])
    tmpdir = os.path.join(tmpdir_parent, task['token'])
    try:
        # run build and rename build directory
        run_build(task, tmpdir, outdir)
        app.logger.info('Copying build files from %s to %s',
                        os.path.join(tmpdir, task['board']),
                            outdir)
        copy_tree(os.path.join(tmpdir, task['board'], 'bin'), outdir)
        app.logger.info('Build successful!')
        remove_directory_recursive(tmpdir)
        # remove extra_hwdef.dat and q.json
        app.logger.info('Removing ' +
                        os.path.join(outdir, 'extra_hwdef.dat'))
        os.remove(os.path.join(outdir, 'extra_hwdef.dat'))

    except Exception as ex:
        app.logger.info('Build failed')
        app.logger.error(ex)
        pass

def remove_old_builds():
    '''as a cleanup, remove any builds older than 24H'''
    for f in os.listdir(outdir_parent):
        if os.stat(os.path.join(outdir_parent, f)).st_mtime < \
        time.time() - 24 * 60 * 60:
            remove_directory_recursive(
                os.path.join(outdir_parent, f))
    time.sleep(5)

def queue_thread():
    while True:
        try:
            check_queue()
            remove_old_builds()
        except Exception as ex:
            app.logger.error(ex)('Failed queue: ', ex)
            pass

def update_source():
    '''update submodules and ardupilot git tree'''
    app.logger.info('Fetching ardupilot origin')
    subprocess.run(['git', 'fetch', 'upstream'],
                   cwd=sourcedir)
    app.logger.info('Updating ardupilot git tree')
    subprocess.run(['git', 'reset', '--hard',
                    'upstream/master'],
                       cwd=sourcedir)
    app.logger.info('Updating submodules')
    subprocess.run(['git', 'submodule',
                    'update', '--recursive',
                        '--force', '--init'],
                       cwd=sourcedir)
        
import optparse
parser = optparse.OptionParser("app.py")


parser.add_option("", "--basedir", type="string",
                  default=os.path.abspath(os.path.join(os.path.dirname(__file__),"..","base")),
                  help="base directory")
cmd_opts, cmd_args = parser.parse_args()
                
# define directories
basedir = os.path.abspath(cmd_opts.basedir)
sourcedir = os.path.abspath(os.path.join(basedir, 'ardupilot'))
outdir_parent = os.path.join(basedir, 'builds')
tmpdir_parent = os.path.join(basedir, 'tmp')

app = Flask(__name__, template_folder='templates')

if not os.path.isdir(outdir_parent):
    create_directory(outdir_parent)

thread = Thread(target=queue_thread, args=())
thread.daemon = True
thread.start()

@app.route('/generate', methods=['GET', 'POST'])
def generate():
    try:
        update_source()

        # fetch features from user input
        extra_hwdef = []
        feature_list = []
        app.logger.info('Fetching features from user input')
        for (label, define, text) in BUILD_OPTIONS:
            if label not in request.form:
                continue
            extra_hwdef.append(request.form[label])
            if request.form[label][-1] == '1':
                feature_list.append(text)
            undefine = 'undef ' + define
            extra_hwdef.insert(0, undefine)
        extra_hwdef = '\n'.join(extra_hwdef)
        spaces = '\n' + ' '*len('Selected Features: ')
        feature_list = spaces.join(feature_list)

        queue_lock.acquire()

        # create extra_hwdef.dat file and obtain md5sum
        app.logger.info('Creating ' + 
                        os.path.join(outdir_parent, 'extra_hwdef.dat'))
        file = open(os.path.join(outdir_parent, 'extra_hwdef.dat'), 'w')
        app.logger.info('Writing\n' + extra_hwdef)
        file.write(extra_hwdef)
        file.close()
        app.logger.info('Getting md5sum')
        md5sum = subprocess.check_output(['md5sum', 
                                            os.path.join(outdir_parent, 
                                            'extra_hwdef.dat')],
                                            encoding = 'utf-8')
        md5sum = md5sum[:len(md5sum)
                        -(3+len(os.path.join(outdir_parent, 
                                            'extra_hwdef.dat')))]
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
        vehicle = request.form['vehicle'].lower()
        board = request.form['board']
        token = vehicle + '-' + board + '-' + git_hash + '-' + md5sum
        app.logger.info('token = ' + token)
        global outdir
        outdir = os.path.join(outdir_parent, token)
        
        if os.path.isdir(outdir):
            app.logger.info('Build already exists')
        else:
            create_directory(outdir)
            # create build.log
            build_log_info = ('Vehicle: ' + request.form['vehicle'] +
                '\nBoard: ' + request.form['board'] +
                '\nSelected Features: ' + feature_list +
                '\n\nWaiting for build to start...\n\n')
            app.logger.info('Creating build.log')
            build_log = open(os.path.join(outdir, 'build.log'), 'w')
            build_log.write(build_log_info)
            build_log.close()
            # create hwdef.dat
            app.logger.info('Opening ' + 
                            os.path.join(outdir, 'extra_hwdef.dat'))
            file = open(os.path.join(outdir, 'extra_hwdef.dat'),'w')
            app.logger.info('Writing\n' + extra_hwdef)
            file.write(extra_hwdef)
            file.close()
            # fill dictionary of variables and create json file
            task = {}
            task['token'] = token
            task['sourcedir'] = sourcedir
            task['extra_hwdef'] = os.path.join(outdir, 'extra_hwdef.dat')
            task['vehicle'] = vehicle
            task['board'] = board
            task['ip'] = request.remote_addr
            app.logger.info('Opening ' + os.path.join(outdir, 'q.json'))
            jfile = open(os.path.join(outdir, 'q.json'), 'w')
            app.logger.info('Writing task file to ' + 
                            os.path.join(outdir, 'q.json'))
            jfile.write(json.dumps(task, separators=(',\n', ': ')))
            jfile.close()

        queue_lock.release()

        base_url = request.url_root
        app.logger.info(base_url)
        apache_build_dir = base_url + os.path.join('builds', token)
        apache_build_log = base_url + os.path.join('builds', token, 'build.log')
        apache_all_builds = base_url + 'builds'
        app.logger.info('Rendering generate.html')
        return render_template('generate.html',
                                apache_build_dir=apache_build_dir, 
                                apache_build_log=apache_build_log,
                                apache_all_builds=apache_all_builds,
                                token=token)
    
    except Exception as ex:
        app.logger.error(ex)
        return render_template('generate.html', error='Error occured')

def get_build_options():
    return BUILD_OPTIONS

def get_vehicles():
    return VEHICLES

@app.route('/')
@app.route('/home', methods=['POST'])
def home():
    app.logger.info('Rendering index.html')
    return render_template('index.html',
                           get_boards=get_boards,
                           get_vehicles=get_vehicles,
                           get_build_options=get_build_options)

@app.route("/builds/<path:name>")
def download_file(name):
    app.logger.info('Downloading %s' % name)
    return send_from_directory(os.path.join(basedir,'builds'), name, as_attachment=False)

if __name__ == '__main__':
    app.run()
