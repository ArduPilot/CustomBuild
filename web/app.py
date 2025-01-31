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
from distutils.dir_util import copy_tree
from flask import Flask, render_template, request, send_from_directory, render_template_string, jsonify, redirect
from threading import Thread, Lock
import sys
import re
import requests

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
        'level': os.getenv('CBS_LOG_LEVEL', default='INFO'),
        'handlers': ['wsgi']
    }
})

# let app.py know about the modules in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import ap_git
import metadata_manager

# run at lower priority
os.nice(20)

import optparse
parser = optparse.OptionParser("app.py")

parser.add_option("", "--basedir", type="string",
                  default=os.getenv(
                      key="CBS_BASEDIR",
                      default=os.path.abspath(os.path.join(os.path.dirname(__file__),"..","base"))
                  ),
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

try:
    repo = ap_git.GitRepo(sourcedir)
except FileNotFoundError:
    repo = ap_git.GitRepo.clone(
        source="https://github.com/ardupilot/ardupilot.git",
        dest=sourcedir,
        recurse_submodules=True,
    )

ap_src_metadata_fetcher = metadata_manager.APSourceMetadataFetcher(
    ap_repo=repo
)
versions_fetcher = metadata_manager.VersionsFetcher(
    remotes_json_path=os.path.join(basedir, 'configs', 'remotes.json'),
    ap_repo=repo
)
versions_fetcher.start()

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
    tmp_src_dir = os.path.join(tmpdir, 'build_src')
    source_repo = ap_git.GitRepo.shallow_clone_at_commit_from_local(
        source=sourcedir,
        remote=task['remote'],
        commit_ref=task['git_hash_short'],
        dest=tmp_src_dir
    )
    # update submodules in temporary source directory
    source_repo.submodule_update(init=True, recursive=True, force=True)
    # checkout to the commit pointing to the requested commit
    source_repo.checkout_remote_commit_ref(
        remote=task['remote'],
        commit_ref=task['git_hash_short'],
        force=True,
        hard_reset=True,
        clean_working_tree=True
    )
    if not os.path.isfile(os.path.join(outdir, 'extra_hwdef.dat')):
        app.logger.error('Build aborted, missing extra_hwdef.dat')
    app.logger.info('Appending to build.log')
    with open(logpath, 'a') as log:

        log.write('Setting vehicle to: ' + task['vehicle'].capitalize() + '\n')
        log.flush()
        # setup PATH to point at our compiler
        env = os.environ.copy()
        bindir1 = os.path.abspath(os.path.join(appdir, "..", "..", "bin"))
        bindir2 = os.path.abspath(os.path.join(appdir, "..", "..", "gcc", "bin"))
        cachedir = os.path.abspath(os.path.join(appdir, "..", "..", "cache"))

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

versions_fetcher.reload_remotes_json()

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

    versions_fetcher.reload_remotes_json()
    return "Successfully refreshed remotes", 200

@app.route('/generate', methods=['GET', 'POST'])
def generate():
    try:
        chosen_version = request.form['version']
        chosen_remote, chosen_commit_reference = chosen_version.split('/', 1)
        chosen_vehicle = request.form['vehicle']
        chosen_version_info = versions_fetcher.get_version_info(
            vehicle=chosen_vehicle,
            remote=chosen_remote,
            commit_ref=chosen_commit_reference
        )

        if chosen_version_info is None:
            raise Exception("Commit reference invalid or not listed to be built for given vehicle for remote")

        chosen_board = request.form['board']
        boards_at_commit, _ = ap_src_metadata_fetcher.get_boards_at_commit(
            remote=chosen_remote,
            commit_ref=chosen_commit_reference
        )
        if chosen_board not in boards_at_commit:
            raise Exception("bad board")

        #ToDo - maybe have the if-statement to check if it's changed.
        build_options = ap_src_metadata_fetcher.get_build_options_at_commit(
            remote=chosen_remote,
            commit_ref=chosen_commit_reference
        )

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

        new_git_hash = repo.commit_id_for_remote_ref(
            remote=chosen_remote,
            commit_ref=chosen_commit_reference
        )
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
                '\nVersion: ' + chosen_version_info.release_type + '-' + chosen_version_info.version_number +
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
            task['version'] = chosen_version_info.release_type + '-' + chosen_version_info.version_number
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

    if not versions_fetcher.is_version_listed(vehicle=vehicle_name, remote=remote_name, commit_ref=commit_reference):
        return "Bad request. Commit reference not allowed to build for the vehicle.", 400

    app.logger.info('Board list and build options requested for %s %s %s' % (vehicle_name, remote_name, commit_reference))
    # getting board list for the branch
    with repo.get_checkout_lock():
        (boards, default_board) = ap_src_metadata_fetcher.get_boards_at_commit(
            remote=remote_name,
            commit_ref=commit_reference
        )

        options = ap_src_metadata_fetcher.get_build_options_at_commit(
            remote=remote_name,
            commit_ref=commit_reference
        )   # this is a list of Feature() objects defined in build_options.py

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
    for version_info in versions_fetcher.get_versions_for_vehicle(vehicle_name=vehicle_name):
        if version_info.release_type == "latest":
            title = f"Latest ({version_info.remote})"
        else:
            title = f"{version_info.release_type} {version_info.version_number} ({version_info.remote})"
        id = f"{version_info.remote}/{version_info.commit_ref}"
        versions.append({
            "title" :   title,
            "id"    :   id,
        })

    return jsonify(sorted(versions, key=lambda x: x['title']))

@app.route("/get_vehicles")
def get_vehicles():
    return jsonify(versions_fetcher.get_all_vehicles_sorted_uniq())

@app.route("/get_defaults/<string:vehicle_name>/<string:remote_name>/<string:commit_reference>/<string:board_name>", methods = ['GET'])
def get_deafults(vehicle_name, remote_name, commit_reference, board_name):
    # Heli is built on copter
    if vehicle_name == "Heli":
        vehicle_name = "Copter"

    commit_reference = base64.urlsafe_b64decode(commit_reference).decode()
    version_info = versions_fetcher.get_version_info(vehicle=vehicle_name, remote=remote_name, commit_ref=commit_reference)

    if version_info is None:
        return "Bad request. Commit reference %s is not allowed for builds for the %s for %s remote." % (commit_reference, vehicle_name, remote_name), 400

    artifacts_dir = version_info.ap_build_artifacts_url

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
