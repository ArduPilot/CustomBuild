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
from flask import Flask, render_template, request, send_from_directory, render_template_string, jsonify
from threading import Thread, Lock
import sys
import re
import requests
# run at lower priority
os.nice(20)

#BOARDS = [ 'BeastF7', 'BeastH7' ]

appdir = os.path.dirname(__file__)

builds_dict = {}

class Vehicle:
    def __init__(self, name, dir):
        self.name = name
        self.dir = dir

# create vehicle objects
copter = Vehicle('Copter', 'ArduCopter')
plane = Vehicle('Plane', 'ArduPlane')
rover = Vehicle('Rover', 'Rover')
sub = Vehicle('Sub', 'ArduSub')
tracker = Vehicle('AntennaTracker', 'AntennaTracker')
blimp = Vehicle('Blimp', 'Blimp')
heli = Vehicle('Heli', 'ArduCopter')

VEHICLES = [copter, plane, rover, sub, tracker, blimp, heli]
default_vehicle = copter
# Note: Current implementation of BRANCHES means we can't have multiple branches with the same name even if they're in different remote repos.
# Branch names (the git branch name not the Label) also cannot contain anything not valid in folder names.
# the first branch in this list is always the default branch
BRANCHES = [
    {
        'full_name'         : 'upstream/master',
        'label'             : 'Latest',
        'allowed_vehicles'  : [copter, plane, rover, sub, tracker, blimp, heli]
    },
    {
        'full_name'         : 'upstream/Plane-4.3',
        'label'             : 'Plane 4.3 stable',
        'allowed_vehicles'  : [plane]
    },
    {
        'full_name'         : 'upstream/Copter-4.3',
        'label'             : 'Copter 4.3 stable',
        'allowed_vehicles'  : [copter, heli]
    },
    {
        'full_name'         : 'upstream/Rover-4.3',
        'label'             : 'Rover 4.3 stable',
        'allowed_vehicles'  : [rover]
    },
]
default_branch = BRANCHES[0]

def get_vehicle_names():
    return sorted([vehicle.name for vehicle in VEHICLES])

def get_default_vehicle_name():
    return default_vehicle.name

def get_branch_names():
    return sorted([branch['full_name'] for branch in BRANCHES])

def get_branches():
    return sorted(BRANCHES, key=lambda x: x['full_name'])

def get_default_branch_name():
    return default_branch['full_name']

# LOCKS
queue_lock = Lock()
head_lock = Lock()  # lock git HEAD, i.e., no branch change until this lock is released

def is_valid_vehicle(vehicle_name):
    return vehicle_name in get_vehicle_names()

def is_valid_branch(branch_name):
    return branch_name in get_branch_names()

def run_git(cmd, cwd):
    app.logger.info("Running git: %s" % ' '.join(cmd))
    return subprocess.run(cmd, cwd=cwd, shell=False)

def get_git_hash(branch):
    app.logger.info("Running git rev-parse %s in %s" % (branch, sourcedir))
    return subprocess.check_output(['git', 'rev-parse', branch], cwd=sourcedir, encoding='utf-8', shell=False).rstrip()

def on_branch(branch):
    git_hash_target = get_git_hash(branch)
    app.logger.info("Expected branch git-hash '%s'" % git_hash_target)
    git_hash_current = get_git_hash('HEAD')
    app.logger.info("Current branch git-hash '%s'" % git_hash_current)
    return git_hash_target == git_hash_current

def delete_branch(branch_name, s_dir):
    run_git(['git', 'checkout', get_default_branch_name()], cwd=s_dir) # to make sure we are not already on branch to be deleted
    run_git(['git', 'branch', '-D', branch_name], cwd=s_dir)    # delete branch

def checkout_branch(targetBranch, s_dir, fetch_and_reset=False, temp_branch_name=None):
    '''checkout to given branch and return the git hash'''
    # Note: remember to acquire head_lock before calling this method
    if not is_valid_branch(targetBranch):
        app.logger.error("Checkout requested for an invalid branch")
        return None 
    remote =  targetBranch.split('/', 1)[0]
    if not on_branch(targetBranch):
        app.logger.info("Checking out to %s branch" % targetBranch)
        run_git(['git', 'checkout', targetBranch], cwd=s_dir)
    if fetch_and_reset:
        run_git(['git', 'fetch', remote], cwd=s_dir)
        run_git(['git', 'reset', '--hard', targetBranch], cwd=s_dir)
    if temp_branch_name is not None:
        delete_branch(temp_branch_name, s_dir=s_dir) # delete temp branch if it already exists
        run_git(['git', 'checkout', '-b', temp_branch_name, targetBranch], cwd=s_dir)    # creates new temp branch
    git_hash = get_git_hash('HEAD')
    return git_hash

def clone_branch(targetBranch, sourcedir, out_dir, temp_branch_name):
    # check if target branch is a valid branch
    if not is_valid_branch(targetBranch):
        return False
    remove_directory_recursive(out_dir)
    head_lock.acquire()
    checkout_branch(targetBranch, s_dir=sourcedir, fetch_and_reset=True, temp_branch_name=temp_branch_name)
    output = run_git(['git', 'clone', '--single-branch', '--branch='+temp_branch_name, sourcedir, out_dir], cwd=sourcedir)
    delete_branch(temp_branch_name, sourcedir) # delete temp branch
    head_lock.release()
    return output.returncode == 0

def get_boards_from_ardupilot_tree(s_dir):
    '''return a list of boards to build'''
    tstart = time.time()
    import importlib.util
    spec = importlib.util.spec_from_file_location("board_list.py",
                                                  os.path.join(s_dir, 
                                                  'Tools', 'scripts', 
                                                  'board_list.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    all_boards = mod.AUTOBUILD_BOARDS
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
    app.logger.info('Took %f seconds to get boards' % (time.time() - tstart))
    boards.sort()
    default_board = boards[0]
    return (boards, default_board)

def get_build_options_from_ardupilot_tree(s_dir):
    '''return a list of build options'''
    tstart = time.time()
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "build_options.py",
        os.path.join(s_dir, 'Tools', 'scripts', 'build_options.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    app.logger.info('Took %f seconds to get build options' % (time.time() - tstart))
    return mod.BUILD_OPTIONS

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
    # clone target branch in temporary source directory
    tmp_src_dir = os.path.join(tmpdir, 'build_src')
    clone_branch(task['branch'], sourcedir, tmp_src_dir, task['branch']+'_clone')
    # update submodules in temporary source directory
    update_submodules(tmp_src_dir)
    if not os.path.isfile(os.path.join(outdir, 'extra_hwdef.dat')):
        app.logger.error('Build aborted, missing extra_hwdef.dat')
    app.logger.info('Appending to build.log')
    with open(logpath, 'a') as log:

        log.write('Setting vehicle to: ' + task['vehicle'].capitalize() + '\n')
        log.flush()
        # setup PATH to point at our compiler
        env = os.environ.copy()
        bindir1 = os.path.abspath(os.path.join(appdir, "..", "bin"))
        bindir2 = os.path.abspath(os.path.join(appdir, "..", "gcc", "bin"))
        cachedir = os.path.abspath(os.path.join(appdir, "..", "cache"))

        env["PATH"] = bindir1 + ":" + bindir2 + ":" + env["PATH"]
        env['CCACHE_DIR'] = cachedir

        app.logger.info('Running waf configure')
        log.write('Running waf configure')
        log.flush()
        subprocess.run(['python3', './waf', 'configure',
                        '--board', task['board'], 
                        '--out', tmpdir, 
                        '--extra-hwdef', task['extra_hwdef']],
                        cwd = tmp_src_dir,
                        env=env,
                        stdout=log, stderr=log, shell=False)
        app.logger.info('Running clean')
        log.write('Running clean')
        log.flush()
        subprocess.run(['python3', './waf', 'clean'],
                        cwd = tmp_src_dir, 
                        env=env,
                        stdout=log, stderr=log, shell=False)
        app.logger.info('Running build')
        log.write('Running build')
        log.flush()
        subprocess.run(['python3', './waf', task['vehicle']],
                        cwd = tmp_src_dir,
                        env=env,
                        stdout=log, stderr=log, shell=False)
        log.write('done build')
        log.flush()

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
        app.logger.info('MIR: Running build ' + str(task))
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

def get_build_progress(build_id, build_status):
    '''return build progress on scale of 0 to 100'''
    if build_status in ['Pending', 'Error']:
        return 0
    
    if build_status == 'Finished':
        return 100
    
    log_file_path = os.path.join(outdir_parent,build_id,'build.log')
    app.logger.info('Opening ' + log_file_path)
    build_log = open(log_file_path, encoding='utf-8').read()
    compiled_regex = re.compile(r'(\[\D*(\d+)\D*\/\D*(\d+)\D*\])')
    all_matches = compiled_regex.findall(build_log)

    if (len(all_matches) < 1):
        return 0

    completed_steps, total_steps = all_matches[-1][1:]
    if (int(total_steps) < 20):
        # these steps are just little compilation and linking that happen at initialisation
        # these do not contribute significant percentage to overall build progress
        return 1
    
    if (int(total_steps) < 200):
        # these steps are for building the OS
        # we give this phase 4% weight in the whole build progress
        return (int(completed_steps) * 4 // int(total_steps)) + 1
    
    # these steps are the major part of the build process
    # we give 95% of weight to these
    return (int(completed_steps) * 95 // int(total_steps)) + 5


def get_build_status(build_id):
    build_id_split = build_id.split(':')
    if len(build_id_split) < 2:
        raise Exception('Invalid build id')

    if os.path.exists(os.path.join(outdir_parent,build_id,'q.json')):
        status = "Pending"
    elif not os.path.exists(os.path.join(outdir_parent,build_id,'build.log')):
        status = "Error"
    else:
        log_file_path = os.path.join(outdir_parent,build_id,'build.log')
        app.logger.info('Opening ' + log_file_path)
        build_log = open(log_file_path, encoding='utf-8').read()
        if build_log.find("'%s' finished successfully" % build_id_split[0].lower()) != -1:
            status = "Finished"
        elif build_log.find('The configuration failed') != -1 or build_log.find('Build failed') != -1 or build_log.find('compilation terminated') != -1:
            status = "Failed"
        elif build_log.find('BUILD_FINISHED') == -1:
            status = "Running"
        else:
            status = "Failed"
    return status

def update_build_dict():
    '''update the build_dict dictionary which keeps track of status of all builds'''
    global builds_dict
    # get list of directories
    blist = []
    for b in os.listdir(outdir_parent):
        if os.path.isdir(os.path.join(outdir_parent,b)):
            blist.append(b)

    #remove deleted builds from build_dict
    for build in builds_dict:
        if build not in blist:
            builds_dict.pop(build, None)

    for b in blist:
        build_id_split = b.split(':')
        if len(build_id_split) < 2:
            continue
        build_info = builds_dict.get(b, None)
        # add an entry for the build in build_dict if not exists
        if (build_info is None):
            build_info = {}
            build_info['vehicle'] = build_id_split[0].capitalize()
            build_info['board'] = build_id_split[1]
            feature_file = os.path.join(outdir_parent, b, 'selected_features.json')
            app.logger.info('Opening ' + feature_file)
            selected_features_dict = json.loads(open(feature_file).read())
            selected_features = selected_features_dict['selected_features']
            build_info['git_hash_short'] = selected_features_dict['git_hash_short']
            features = ''
            for feature in selected_features:
                if features == '':
                    features = features + feature
                else:
                    features = features + ", " + feature
            build_info['features'] = features

        age_min = int(file_age(os.path.join(outdir_parent,b))/60.0)
        build_info['age'] = "%u:%02u" % ((age_min // 60), age_min % 60)

        # refresh build status only if it was pending, running or not initialised
        if (build_info.get('status', None) in ['Pending', 'Running', None]):
            build_info['status'] = get_build_status(b)
            build_info['progress'] = get_build_progress(b, build_info['status'])

        # update dictionary entry
        builds_dict[b] = build_info

    temp_list = sorted(list(builds_dict.items()), key=lambda x: os.path.getmtime(os.path.join(outdir_parent,x[0])), reverse=True)
    builds_dict = {ele[0] : ele[1]  for ele in temp_list}

def create_status():
    '''create status.json'''
    global builds_dict
    update_build_dict()
    tmpfile = os.path.join(outdir_parent, "status.tmp")
    statusfile = os.path.join(outdir_parent, "status.json")
    json_object = json.dumps(builds_dict)
    with open(tmpfile, "w") as outfile:
        outfile.write(json_object)
    os.replace(tmpfile, statusfile)

def status_thread():
    while True:
        try:
            create_status()
        except Exception as ex:
            app.logger.info(ex)
            pass
        time.sleep(3)

def update_submodules(s_dir):
    if not os.path.exists(s_dir):
        return
    app.logger.info('Updating submodules')
    run_git(['git', 'submodule', 'update', '--recursive', '--force', '--init'], cwd=s_dir)

import optparse
parser = optparse.OptionParser("app.py")


parser.add_option("", "--basedir", type="string",
                  default=os.path.abspath(os.path.join(os.path.dirname(__file__),"..","base")),
                  help="base directory")
cmd_opts, cmd_args = parser.parse_args()
                
# define directories
basedir = os.path.abspath(cmd_opts.basedir)
sourcedir = os.path.join(basedir, 'ardupilot')
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

app.logger.info('Initial fetch')
# checkout to default branch, fetch remote, update submodules
checkout_branch(get_default_branch_name(), s_dir=sourcedir, fetch_and_reset=True)
update_submodules(s_dir=sourcedir)

app.logger.info('Python version is: %s' % sys.version)

@app.route('/generate', methods=['GET', 'POST'])
def generate():
    try:
        chosen_branch = request.form['branch']
        if not is_valid_branch(chosen_branch):
            raise Exception("bad branch")

        chosen_vehicle = request.form['vehicle']
        if not is_valid_vehicle(chosen_vehicle):
            raise Exception("bad vehicle")

        chosen_board = request.form['board']
        head_lock.acquire()
        checkout_branch(targetBranch=chosen_branch, s_dir=sourcedir)
        if chosen_board not in get_boards_from_ardupilot_tree(s_dir=sourcedir)[0]:
            raise Exception("bad board")

        #ToDo - maybe have the if-statement to check if it's changed.
        build_options = get_build_options_from_ardupilot_tree(s_dir=sourcedir)
        head_lock.release()

        # fetch features from user input
        extra_hwdef = []
        feature_list = []
        selected_features = []
        app.logger.info('Fetching features from user input')

        # add all undefs at the start
        for f in build_options:
            extra_hwdef.append('undef %s' % f.define)

        for f in build_options:
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

        extra_hwdef_md5sum = hashlib.md5(extra_hwdef.encode('utf-8')).hexdigest()
        app.logger.info('Removing ' +
                        os.path.join(outdir_parent, 'extra_hwdef.dat'))
        os.remove(os.path.join(outdir_parent, 'extra_hwdef.dat'))

        new_git_hash = get_git_hash(chosen_branch)
        git_hash_short = new_git_hash[:10]
        app.logger.info('Git hash = ' + new_git_hash)
        selected_features_dict['git_hash_short'] = git_hash_short

        # create directories using concatenated token 
        # of vehicle, board, git-hash of source, and md5sum of hwdef
        token = chosen_vehicle.lower() + ':' + chosen_board + ':' + new_git_hash + ':' + extra_hwdef_md5sum
        app.logger.info('token = ' + token)
        outdir = os.path.join(outdir_parent, token)

        if os.path.isdir(outdir):
            app.logger.info('Build already exists')
        else:
            create_directory(outdir)
            # create build.log
            build_log_info = ('Vehicle: ' + chosen_vehicle +
                '\nBoard: ' + chosen_board +
                '\nBranch: ' + chosen_branch +
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
            task['branch'] = chosen_branch
            task['extra_hwdef'] = os.path.join(outdir, 'extra_hwdef.dat')
            task['vehicle'] = chosen_vehicle.lower()
            task['board'] = chosen_board
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
        app.logger.info('Rendering index.html')
        return render_template('index.html', token=token)

    except Exception as ex:
        app.logger.error(ex)
        return render_template('error.html', ex=ex)

@app.route('/add_build')
def add_build():
    app.logger.info('Rendering add_build.html')
    return render_template('add_build.html',
                            get_vehicle_names=get_vehicle_names,
                            get_default_vehicle_name=get_default_vehicle_name)


def filter_build_options_by_category(build_options, category):
    return sorted([f for f in build_options if f.category == category], key=lambda x: x.description.lower())

def parse_build_categories(build_options):
    return sorted(list(set([f.category for f in build_options])))

@app.route('/')
def home():
    app.logger.info('Rendering index.html')
    return render_template('index.html',
                           token=None)

@app.route("/builds/<path:name>")
def download_file(name):
    app.logger.info('Downloading %s' % name)
    return send_from_directory(os.path.join(basedir,'builds'), name, as_attachment=False)

@app.route("/boards_and_features/<string:remote>/<string:branch_name>", methods = ['GET'])
def boards_and_features(remote, branch_name):
    branch = remote + '/' + branch_name
    if not is_valid_branch(branch):
        app.logger.error("Bad branch")
        return ("Bad branch", 400)

    app.logger.info('Board list and build options requested for %s' % branch)
    # getting board list for the branch
    head_lock.acquire()
    checkout_branch(targetBranch=branch, s_dir=sourcedir)
    (boards, default_board) = get_boards_from_ardupilot_tree(s_dir=sourcedir)
    options = get_build_options_from_ardupilot_tree(s_dir=sourcedir)   # this is a list of Feature() objects defined in build_options.py
    head_lock.release()
    # parse the set of categories from these objects
    categories = parse_build_categories(options)
    features = []
    for category in categories:
        filtered_options = filter_build_options_by_category(options, category)
        category_options = []   # options belonging to a given category
        for option in filtered_options:
            category_options.append({
                'label' : option.label,
                'description' : option.description,
                'default' : option.default,
                'define' : option.define,
                'dependency' : option.dependency,
            })
        features.append({
            'name' : category,
            'options' : category_options,
        })
    # creating result dictionary
    result = {
        'boards' : boards,
        'default_board' : default_board,
        'features' : features,
    }
    # return jsonified result dict
    return jsonify(result)

@app.route("/get_allowed_branches/<string:vehicle_name>", methods=['GET'])
def get_allowed_branches(vehicle_name):
    if not is_valid_vehicle(vehicle_name):
        app.logger.error("Bad vehicle")
        return ("Bad Vehicle", 400)

    app.logger.info("Supported branches requested for %s" % vehicle_name)
    branches = []
    for branch in get_branches():
        if vehicle_name in [vehicle.name for vehicle in branch['allowed_vehicles']]:
            branches.append({
                'full_name': branch['full_name'],
                'label' : branch['label']
            })

    result = {
        'branches' : branches,
        'default_branch' : get_default_branch_name()
    }
    # return jsonified result dictionary
    return jsonify(result)

def get_firmware_version(vehicle_name, branch):
    app.logger.info("Retrieving firmware version information for %s on branch: %s" % (vehicle_name, branch))
    dir = ""
    for vehicle in VEHICLES:
        if vehicle.name == vehicle_name:
            dir = vehicle.dir
            break

    if dir == "":
        raise Exception("Could not determine vehicle directory")
    head_lock.acquire()
    output = subprocess.check_output(['git', 'show', branch+':'+dir+'/version.h'], cwd=sourcedir, encoding='utf-8', shell=False).rstrip()
    head_lock.release()
    match = re.search('define.THISFIRMWARE[\s\S]+V([0-9]+.[0-9]+.[0-9]+)', output)
    if match is None:
        raise Exception("Failed to retrieve firmware version from version.h")
    firmware_version = match.group(1)
    return firmware_version

@app.route("/get_defaults/<string:vehicle_name>/<string:remote>/<string:branch_name>/<string:board>", methods = ['GET'])
def get_deafults(vehicle_name, remote, branch_name, board):
    if not remote == "upstream":
        app.logger.error("Defaults requested for remote '%s' which is not supported" % remote)
        return ("Bad remote. Only upstream is supported.", 400)

    branch = remote + '/' + branch_name
    if not is_valid_branch(branch):
        app.logger.error("Bad branch")
        return ("Bad branch", 400)

    if not is_valid_vehicle(vehicle_name):
        app.logger.error("Bad vehicle")
        return ("Bad Vehicle", 400)

    # Heli is built on copter
    if vehicle_name == "Heli":
        vehicle_name = "Copter"

    artifacts_dir = vehicle_name
    if branch_name == "master":
        artifacts_dir += "/latest"
    else:
        artifacts_dir += ("/stable-"+get_firmware_version(vehicle_name, branch))

    artifacts_dir += "/"+board
    path = "https://firmware.ardupilot.org/"+artifacts_dir+"/features.txt"
    response = requests.get(path, timeout=30)

    if not response.status_code == 200:
        return ("Could not retrieve features.txt for given vehicle, branch and board combination (Status Code: %d, path: %s)" % (response.status_code, path), response.status_code)
    # split response by new line character to get a list of defines
    result = response.text.split('\n')
    # omit the last string as its always blank
    return jsonify(result[:-1])

if __name__ == '__main__':
    app.run()
