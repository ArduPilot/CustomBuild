#!/usr/bin/env python3

import os
import subprocess
import json
import pathlib
import shutil
import glob
import time
import fcntl
import base64
import hashlib
import fnmatch
from distutils.dir_util import copy_tree
from flask import Flask, render_template, request, send_from_directory, render_template_string, jsonify, redirect
from threading import Thread, Lock
import sys
import re
import requests
import jsonschema
# run at lower priority
os.nice(20)

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

appdir = os.path.dirname(__file__)

builds_dict = {}
REMOTES = None

# LOCKS
queue_lock = Lock()
head_lock = Lock()  # lock git HEAD, i.e., no branch change until this lock is released
remotes_lock = Lock()  # lock for accessing and updating REMOTES list

def get_remotes():
    with remotes_lock:
        return REMOTES
    
def set_remotes(remotes):
    with remotes_lock:
        global REMOTES
        REMOTES = remotes

def find_hash_for_ref(remote_name, ref):
    result = subprocess.run(['git', 'ls-remote', remote_name], cwd=sourcedir, encoding='utf-8', capture_output=True, shell=False)

    for line in result.stdout.split('\n')[:-1]:
        (git_hash, r) = line.split('\t')
        if r == ref:
            return git_hash

    raise Exception('Branch ref not found on remote')

def ref_is_branch(commit_reference):
    prefix = 'refs/heads'
    return commit_reference[:len(prefix)] == prefix

def ref_is_tag(commit_reference):
    prefix = 'refs/tags'
    return commit_reference[:len(prefix)] == prefix

def load_remotes():
    # load file contianing vehicles listed to be built for each remote along with the braches/tags/commits on which the firmware can be built
    with open(os.path.join(basedir, 'configs', 'remotes.json'), 'r')  as f, open(os.path.join(appdir, 'remotes.schema.json'), 'r') as s:
        remotes = json.loads(f.read())
        schema = json.loads(s.read())
        # validate schema
        jsonschema.validate(remotes, schema=schema)
        set_remotes(remotes)


def find_version_info(vehicle_name, remote_name, commit_reference):
    if None in (vehicle_name, remote_name, commit_reference):
        return None
    
    # find the object for requested remote
    remote = next((r for r in get_remotes() if r['name'] == remote_name), None)

    if remote is None:
        return None
    
    # find the object requested vehicle in remote metadata
    vehicle = next((v for v in remote['vehicles'] if v['name'] == vehicle_name), None)

    if vehicle is None:
        return None
    
    # find version metadata for asked commit reference
    release = next((r for r in vehicle['releases'] if r['commit_reference'] == commit_reference), None)
    return release


def run_git(cmd, cwd):
    app.logger.info("Running git: %s" % ' '.join(cmd))
    return subprocess.run(cmd, cwd=cwd, shell=False)

def delete_branch(branch_name, s_dir):
    run_git(['git', 'checkout', 'master'], cwd=s_dir) # to make sure we are not already on branch to be deleted
    run_git(['git', 'branch', '-D', branch_name], cwd=s_dir)    # delete branch

def do_checkout(remote, commit_reference, s_dir, force_fetch=False, temp_branch_name=None):
    '''checkout to given commit/branch and return the git hash'''
    # Note: remember to acquire head_lock before calling this method
    if force_fetch:
        run_git(['git', 'fetch', remote], cwd=s_dir)

    git_hash_target = commit_reference
    if ref_is_branch(commit_reference) or ref_is_tag(commit_reference):
        git_hash_target = find_hash_for_ref(remote, commit_reference)

    app.logger.info("Checking out to %s (%s/%s)" % (git_hash_target, remote, commit_reference))

    result = run_git(['git', 'checkout', git_hash_target], cwd=s_dir)
    if result.returncode != 0:
        # commit with the given hash isn't fetched? fetch and try again
        run_git(['git', 'fetch', remote], cwd=s_dir)
        result = run_git(['git', 'checkout', git_hash_target], cwd=s_dir)
        if result.returncode != 0:
            raise Exception("Could not checkout to the requested commit")

    if temp_branch_name is not None:
        delete_branch(temp_branch_name, s_dir=s_dir) # delete temp branch if it already exists
        run_git(['git', 'checkout', '-b', temp_branch_name, git_hash_target], cwd=s_dir)    # creates new temp branch
    return git_hash_target

def branch_and_clone(remote, commit_reference, sourcedir, out_dir, temp_branch_name):
    remove_directory_recursive(out_dir)
    head_lock.acquire()
    do_checkout(remote, commit_reference, s_dir=sourcedir, force_fetch=True, temp_branch_name=temp_branch_name)
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
    # creates a branch from the commit reference and clones it into a new repository
    tmp_src_dir = os.path.join(tmpdir, 'build_src')
    branch_and_clone(task['remote'], task['git_hash_short'], sourcedir, tmp_src_dir, task['git_hash_short']+'_clone')
    # update submodules in temporary source directory
    update_submodules(tmp_src_dir)
    # checkout to the commit pointing to the requested commit
    do_checkout(task['remote'], task['git_hash_short'], tmp_src_dir)
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
        log.write('Running waf configure\n')
        log.flush()
        subprocess.run(['python3', './waf', 'configure',
                        '--board', task['board'], 
                        '--out', tmpdir, 
                        '--extra-hwdef', task['extra_hwdef']],
                        cwd = tmp_src_dir,
                        env=env,
                        stdout=log, stderr=log, shell=False)
        app.logger.info('Running clean')
        log.write('Running clean\n')
        log.flush()
        subprocess.run(['python3', './waf', 'clean'],
                        cwd = tmp_src_dir, 
                        env=env,
                        stdout=log, stderr=log, shell=False)
        app.logger.info('Running build')
        log.write('Running build\n')
        log.flush()
        subprocess.run(['python3', './waf', task['vehicle']],
                        cwd = tmp_src_dir,
                        env=env,
                        stdout=log, stderr=log, shell=False)
        log.write('done build\n')
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

load_remotes()
app.logger.info('Initial fetch')
# checkout to default branch, fetch remote, update submodules
do_checkout("upstream", "master", s_dir=sourcedir, force_fetch=True)
update_submodules(s_dir=sourcedir)

app.logger.info('Python version is: %s' % sys.version)

def get_auth_token():
    try:
        # try to read the secret token from the file
        with open(os.path.join(basedir, 'secrets', 'reload_token'), 'r') as file:
            token = file.read().strip()
            return token
    except (FileNotFoundError, PermissionError):
        app.logger.error("Couldn't open token file. Checking environment for token.")
        # if the file does not exist, check the environment variable
        return os.getenv('CBS_REMOTES_RELOAD_TOKEN')

@app.route('/refresh_remotes', methods=['POST'])
def refresh_remotes():
    auth_token = get_auth_token()

    if auth_token is None:
        app.logger.error("Couldn't retrieve authorization token")
        return "Internal Server Error", 500

    token = request.get_json().get('token')
    if not token or token != auth_token:
        return "Unauthorized", 401

    load_remotes()
    return "Successfully refreshed remotes", 200

@app.route('/generate', methods=['GET', 'POST'])
def generate():
    try:
        chosen_version = request.form['version']
        chosen_remote, chosen_commit_reference = chosen_version.split('/', 1)
        chosen_vehicle = request.form['vehicle']
        chosen_version_info = find_version_info(vehicle_name=chosen_vehicle, remote_name=chosen_remote, commit_reference=chosen_commit_reference)

        if chosen_version_info is None:
            raise Exception("Commit reference invalid or not listed to be built for given vehicle for remote")

        chosen_board = request.form['board']
        head_lock.acquire()
        do_checkout(chosen_remote, chosen_commit_reference, s_dir=sourcedir)
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

        new_git_hash = chosen_commit_reference
        if ref_is_branch(chosen_commit_reference) or ref_is_tag(chosen_commit_reference):
            new_git_hash = find_hash_for_ref(chosen_remote, chosen_commit_reference)
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
                '\nRemote: ' + chosen_remote +
                '\ngit-sha: ' + git_hash_short +
                '\nVersion: ' + chosen_version_info['release_type'] + '-' + chosen_version_info['version_number'] +
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
            task['remote'] = chosen_remote
            task['git_hash_short'] = git_hash_short
            task['version'] = chosen_version_info['release_type'] + '-' + chosen_version_info['version_number']
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
        app.logger.info('Redirecting to /viewlog')
        return redirect('/viewlog/'+token)

    except Exception as ex:
        app.logger.error(ex)
        return render_template('error.html', ex=ex)

@app.route('/add_build')
def add_build():
    app.logger.info('Rendering add_build.html')
    return render_template('add_build.html')


def filter_build_options_by_category(build_options, category):
    return sorted([f for f in build_options if f.category == category], key=lambda x: x.description.lower())

def parse_build_categories(build_options):
    return sorted(list(set([f.category for f in build_options])))

@app.route('/', defaults={'token': None}, methods=['GET'])
@app.route('/viewlog/<token>', methods=['GET'])
def home(token):
    if token:
        app.logger.info("Showing log for build id " + token)
    app.logger.info('Rendering index.html')
    return render_template('index.html', token=token)

@app.route("/builds/<path:name>")
def download_file(name):
    app.logger.info('Downloading %s' % name)
    return send_from_directory(os.path.join(basedir,'builds'), name, as_attachment=False)

@app.route("/boards_and_features/<string:vehicle_name>/<string:remote_name>/<string:commit_reference>", methods=['GET'])
def boards_and_features(vehicle_name, remote_name, commit_reference):
    commit_reference = base64.urlsafe_b64decode(commit_reference).decode()

    if find_version_info(vehicle_name, remote_name, commit_reference) is None:
        return "Bad request. Commit reference not allowed to build for the vehicle.", 400

    app.logger.info('Board list and build options requested for %s %s %s' % (vehicle_name, remote_name, commit_reference))
    # getting board list for the branch
    head_lock.acquire()
    do_checkout(remote_name, commit_reference, s_dir=sourcedir)
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

@app.route("/get_versions/<string:vehicle_name>", methods=['GET'])
def get_versions(vehicle_name):
    versions = list()
    for remote in get_remotes():
        for vehicle in remote['vehicles']:
            if vehicle['name'] == vehicle_name:
                for release in vehicle['releases']:
                    if release['release_type'] == "latest":
                        title = f'Latest ({remote["name"]})'
                    else:
                        title = f'{release["release_type"]} {release["version_number"]} ({remote["name"]})'
                    id = f'{remote["name"]}/{release["commit_reference"]}'
                    versions.append({
                        "title" :   title,
                        "id"    :   id,
                    })

    return jsonify(sorted(versions, key=lambda x: x['title']))

@app.route("/get_vehicles")
def get_vehicles():
    vehicle_set = set()
    for remote in get_remotes():
        vehicle_set = vehicle_set.union(set([vehicle['name'] for vehicle in remote['vehicles']]))

    return jsonify(sorted(list(vehicle_set)))

@app.route("/get_defaults/<string:vehicle_name>/<string:remote_name>/<string:commit_reference>/<string:board_name>", methods = ['GET'])
def get_deafults(vehicle_name, remote_name, commit_reference, board_name):
    # Heli is built on copter
    if vehicle_name == "Heli":
        vehicle_name = "Copter"

    commit_reference = base64.urlsafe_b64decode(commit_reference).decode()
    version_info = find_version_info(vehicle_name, remote_name, commit_reference)

    if version_info is None:
        return "Bad request. Commit reference %s is not allowed for builds for the %s for %s remote." % (commit_reference, vehicle_name, remote_name), 400

    artifacts_dir = version_info.get("ap_build_atrifacts_url", None)

    if artifacts_dir is None:
        return "Couldn't find artifacts for requested release/branch/commit on ardupilot server", 404

    url_to_features_txt = artifacts_dir + '/' + board_name + '/features.txt'
    response = requests.get(url_to_features_txt, timeout=30)

    if not response.status_code == 200:
        return ("Could not retrieve features.txt for given vehicle, version and board combination (Status Code: %d, url: %s)" % (response.status_code, url_to_features_txt), response.status_code)
    # split response by new line character to get a list of defines
    result = response.text.split('\n')
    # omit the last two elements as they are always blank
    return jsonify(result[:-2])

if __name__ == '__main__':
    app.run()
