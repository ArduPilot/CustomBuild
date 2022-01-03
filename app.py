#!/usr/bin/env python3

import os
import subprocess
import json
import pathlib
import shutil
import glob
import time
import fcntl
import hashlib
import fnmatch
from distutils.dir_util import copy_tree
from flask import Flask, render_template, request, send_from_directory, render_template_string
from threading import Thread, Lock

# run at lower priority
os.nice(20)

#BOARDS = [ 'BeastF7', 'BeastH7' ]

appdir = os.path.dirname(__file__)

VEHICLES = [ 'Copter', 'Plane', 'Rover', 'Sub', 'Tracker' ]
default_vehicle = 'Copter'

def get_boards():
    '''return a list of boards to build'''
    import importlib.util
    spec = importlib.util.spec_from_file_location("board_list.py",
                                                  os.path.join(sourcedir, 
                                                  'Tools', 'scripts', 
                                                  'board_list.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    all_boards = mod.AUTOBUILD_BOARDS
    default_board = mod.AUTOBUILD_BOARDS[0]
    exclude_patterns = [ 'fmuv*', 'SITL*' ]
    boards = []
    for b in all_boards:
        excluded = False
        for p in exclude_patterns:
            if fnmatch.fnmatch(b.lower(), p.lower()):
                excluded = True
                break
        if not excluded:
            boards.append(b)
    boards.sort()
    return (boards, boards[0])

def get_build_options_from_ardupilot_tree():
    '''return a list of build options'''
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "build_options.py",
        os.path.join(sourcedir, 'Tools', 'scripts', 'build_options.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.BUILD_OPTIONS

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


def run_build(task, tmpdir, outdir, logpath):
    '''run a build with parameters from task'''
    remove_directory_recursive(tmpdir_parent)
    create_directory(tmpdir)
    if not os.path.isfile(os.path.join(outdir, 'extra_hwdef.dat')):
        app.logger.error('Build aborted, missing extra_hwdef.dat')
    app.logger.info('Appending to build.log')
    with open(logpath, 'a') as log:

        # setup PATH to point at our compiler
        env = os.environ.copy()
        bindir1 = os.path.abspath(os.path.join(appdir, "..", "bin"))
        bindir2 = os.path.abspath(os.path.join(appdir, "..", "gcc", "bin"))
        cachedir = os.path.abspath(os.path.join(appdir, "..", "cache"))

        env["PATH"] = bindir1 + ":" + bindir2 + ":" + env["PATH"]
        env['CCACHE_DIR'] = cachedir

        app.logger.info('Running waf configure')
        subprocess.run(['python3', './waf', 'configure',
                        '--board', task['board'], 
                        '--out', tmpdir, 
                        '--extra-hwdef', task['extra_hwdef']],
                        cwd = task['sourcedir'],
                        env=env,
                        stdout=log, stderr=log)
        app.logger.info('Running clean')
        subprocess.run(['python3', './waf', 'clean'],
                        cwd = task['sourcedir'], 
                        env=env,
                        stdout=log, stderr=log)
        app.logger.info('Running build')
        subprocess.run(['python3', './waf', task['vehicle']],
                        cwd = task['sourcedir'],
                        env=env,
                        stdout=log, stderr=log)

def sort_json_files(reverse=False):
    json_files = list(filter(os.path.isfile,
                             glob.glob(os.path.join(outdir_parent,
                                                    '*', 'q.json'))))
    json_files.sort(key=lambda x: os.path.getmtime(x), reverse=reverse)
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
    logpath = os.path.abspath(os.path.join(outdir, 'build.log'))
    app.logger.info("LOGPATH: %s" % logpath)
    try:
        # run build and rename build directory
        run_build(task, tmpdir, outdir, logpath)
        app.logger.info('Copying build files from %s to %s',
                        os.path.join(tmpdir, task['board']),
                            outdir)
        copy_tree(os.path.join(tmpdir, task['board'], 'bin'), outdir)
        app.logger.info('Build successful!')
        remove_directory_recursive(tmpdir)

    except Exception as ex:
        app.logger.info('Build failed: ', ex)
        pass
    open(logpath,'a').write("\nBUILD_FINISHED\n")

def file_age(fname):
    '''return file age in seconds'''
    return time.time() - os.stat(fname).st_mtime

def remove_old_builds():
    '''as a cleanup, remove any builds older than 24H'''
    for f in os.listdir(outdir_parent):
        bdir = os.path.join(outdir_parent, f)
        if os.path.isdir(bdir) and file_age(bdir) > 24 * 60 * 60:
            remove_directory_recursive(bdir)
    time.sleep(5)

def queue_thread():
    while True:
        try:
            check_queue()
            remove_old_builds()
        except Exception as ex:
            app.logger.error('Failed queue: ', ex)
            pass

def get_build_status():
    '''return build status tuple list
     returns tuples of form (status,age,board,vehicle,genlink)
    '''
    ret = []

    # get list of directories
    blist = []
    for b in os.listdir(outdir_parent):
        if os.path.isdir(os.path.join(outdir_parent,b)):
            blist.append(b)
    blist.sort(key=lambda x: os.path.getmtime(os.path.join(outdir_parent,x)), reverse=True)

    for b in blist:
        a = b.split(':')
        if len(a) < 2:
            continue
        vehicle = a[0].capitalize()
        board = a[1]
        link = "/view?token=%s" % b
        age_min = int(file_age(os.path.join(outdir_parent,b))/60.0)
        age_str = "%u:%02u" % ((age_min // 60), age_min % 60)
        feature_file = os.path.join(outdir_parent, b, 'selected_features.json')
        app.logger.info('Opening ' + feature_file)
        selected_features_dict = json.loads(open(feature_file).read())
        selected_features = selected_features_dict['selected_features']
        git_hash_short = selected_features_dict['git_hash_short']
        features = ''
        for feature in selected_features:
            if features == '':
                features = features + feature
            else:
                features = features + ", " + feature
        if os.path.exists(os.path.join(outdir_parent,b,'q.json')):
            status = "Pending"
        elif not os.path.exists(os.path.join(outdir_parent,b,'build.log')):
            status = "Error"
        else:
            build = open(os.path.join(outdir_parent,b,'build.log')).read()
            if build.find("'%s' finished successfully" % vehicle.lower()) != -1:
                status = "Finished"
            elif build.find('The configuration failed') != -1 or build.find('Build failed') != -1 or build.find('compilation terminated') != -1:
                status = "Failed"
            elif build.find('BUILD_FINISHED') == -1:
                status = "Running"
            else:
                status = "Failed"
        ret.append((status,age_str,board,vehicle,link,features,git_hash_short))
    return ret

def create_status():
    '''create status.html'''
    build_status = get_build_status()
    tmpfile = os.path.join(outdir_parent, "status.tmp")
    statusfile = os.path.join(outdir_parent, "status.html")
    f = open(tmpfile, "w")
    app2 = Flask("status")
    with app2.app_context():
        f.write(render_template_string(open(os.path.join(appdir, 'templates', 'status.html')).read(),
                                       build_status=build_status))
    f.close()
    os.replace(tmpfile, statusfile)

def status_thread():
    while True:
        try:
            create_status()
        except Exception as ex:
            app.logger.info(ex)
            pass
        time.sleep(3)

def update_source():
    '''update submodules and ardupilot git tree'''
    app.logger.info('Fetching ardupilot upstream')
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

try:
    lock_file = open(os.path.join(basedir, "queue.lck"), "w")
    fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    app.logger.info("Got queue lock")
    # we only want one set of threads
    thread = Thread(target=queue_thread, args=())
    thread.daemon = True
    thread.start()

    status_thread = Thread(target=status_thread, args=())
    status_thread.daemon = True
    status_thread.start()
except IOError:
    app.logger.info("No queue lock")

@app.route('/generate', methods=['GET', 'POST'])
def generate():
    try:
        update_source()

        # fetch features from user input
        extra_hwdef = []
        feature_list = []
        selected_features = []
        app.logger.info('Fetching features from user input')

        # get build options from source:
        BUILD_OPTIONS = get_build_options_from_ardupilot_tree()

        # add all undefs at the start
        for f in BUILD_OPTIONS:
            extra_hwdef.append('undef %s' % f.define)

        for f in BUILD_OPTIONS:
            if f.label not in request.form or request.form[f.label] != '1':
                extra_hwdef.append('define %s 0' % f.define)
            else:
                extra_hwdef.append('define %s 1' % f.define)
                feature_list.append(f.description)
                selected_features.append(f.label)

        extra_hwdef = '\n'.join(extra_hwdef)
        spaces = '\n'
        feature_list = spaces.join(feature_list)
        selected_features_dict = {}
        selected_features_dict['selected_features'] = selected_features

        queue_lock.acquire()

        # create extra_hwdef.dat file and obtain md5sum
        app.logger.info('Creating ' + 
                        os.path.join(outdir_parent, 'extra_hwdef.dat'))
        file = open(os.path.join(outdir_parent, 'extra_hwdef.dat'), 'w')
        app.logger.info('Writing\n' + extra_hwdef)
        file.write(extra_hwdef)
        file.close()

        md5sum = hashlib.md5(extra_hwdef.encode('utf-8')).hexdigest()
        app.logger.info('Removing ' +
                        os.path.join(outdir_parent, 'extra_hwdef.dat'))
        os.remove(os.path.join(outdir_parent, 'extra_hwdef.dat'))

        # obtain git-hash of source
        app.logger.info('Getting git hash')
        git_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD'], 
                                            cwd = sourcedir,
                                            encoding = 'utf-8')
        git_hash_short = git_hash[:10]
        git_hash = git_hash[:len(git_hash)-1]
        app.logger.info('Git hash = ' + git_hash)
        selected_features_dict['git_hash_short'] = git_hash_short

        # create directories using concatenated token 
        # of vehicle, board, git-hash of source, and md5sum of hwdef
        vehicle = request.form['vehicle']
        if not vehicle in VEHICLES:
            raise Exception("bad vehicle")

        board = request.form['board']
        if board not in get_boards()[0]:
            raise Exception("bad board")

        token = vehicle.lower() + ':' + board + ':' + git_hash + ':' + md5sum
        app.logger.info('token = ' + token)
        global outdir
        outdir = os.path.join(outdir_parent, token)
        
        if os.path.isdir(outdir):
            app.logger.info('Build already exists')
        else:
            create_directory(outdir)
            # create build.log
            build_log_info = ('Vehicle: ' + vehicle +
                '\nBoard: ' + board +
                '\nSelected Features:\n' + feature_list +
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
            task['vehicle'] = vehicle.lower()
            task['board'] = board
            task['ip'] = request.remote_addr
            app.logger.info('Opening ' + os.path.join(outdir, 'q.json'))
            jfile = open(os.path.join(outdir, 'q.json'), 'w')
            app.logger.info('Writing task file to ' + 
                            os.path.join(outdir, 'q.json'))
            jfile.write(json.dumps(task, separators=(',\n', ': ')))
            jfile.close()
            # create selected_features.dat for status table
            feature_file = open(os.path.join(outdir, 'selected_features.json'), 'w')
            app.logger.info('Writing\n' + os.path.join(outdir, 'selected_features.json'))
            feature_file.write(json.dumps(selected_features_dict))
            feature_file.close()

        queue_lock.release()

        base_url = request.url_root
        app.logger.info(base_url)
        app.logger.info('Rendering generate.html')
        return render_template('generate.html', token=token)
    
    except Exception as ex:
        app.logger.error(ex)
        return render_template('generate.html', error='Error occured: ', ex=ex)

@app.route('/view', methods=['GET'])
def view():
    '''view a build from status'''
    token=request.args['token']
    app.logger.info("viewing %s" % token)
    return render_template('generate.html', token=token)

    
def get_build_options(BUILD_OPTIONS, category):
    return sorted([f for f in BUILD_OPTIONS if f.category == category], key=lambda x: x.description.lower())

def get_build_categories(BUILD_OPTIONS):
    return sorted(list(set([f.category for f in BUILD_OPTIONS])))

def get_vehicles():
    return (VEHICLES, default_vehicle)

@app.route('/')
def home():
    app.logger.info('Rendering index.html')
    BUILD_OPTIONS = get_build_options_from_ardupilot_tree()
    return render_template('index.html',
                           get_boards=get_boards,
                           get_vehicles=get_vehicles,
                           get_build_options=lambda x : get_build_options(BUILD_OPTIONS, x),
                           get_build_categories=lambda : get_build_categories(BUILD_OPTIONS))

@app.route("/builds/<path:name>")
def download_file(name):
    app.logger.info('Downloading %s' % name)
    return send_from_directory(os.path.join(basedir,'builds'), name, as_attachment=False)

if __name__ == '__main__':
    app.run()
