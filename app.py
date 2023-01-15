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
# run at lower priority
os.nice(20)

#BOARDS = [ 'BeastF7', 'BeastH7' ]

appdir = os.path.dirname(__file__)

VEHICLES = [ 'Copter', 'Plane', 'Rover', 'Sub', 'AntennaTracker', 'Blimp', 'Heli']
default_vehicle = 'Copter'
#Note: Current implementation of BRANCHES means we can't have multiple branches with the same name even if they're in different remote repos.
#Branch names (the git branch name not the display name) also cannot contain anything not valid in folder names.
BRANCHES = {
    'upstream/master' : 'Latest',
    'upstream/Plane-4.2' : 'Plane 4.2 stable',
    'upstream/Copter-4.2' : 'Copter 4.2 stable',
    'upstream/Rover-4.2' : 'Rover 4.2 stable'
}
default_branch = 'upstream/master'

def get_vehicles():
    return VEHICLES

def get_default_vehicle():
    return default_vehicle

def get_branches():
    return BRANCHES

def get_default_branch():
    return default_branch

# LOCKS
queue_lock = Lock()
head_lock = Lock()  # lock git HEAD, i.e., no branch change until this lock is released

def is_valid_branch(branch):
    return get_branches().get(branch) is not None

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
    run_git(['git', 'checkout', default_branch], cwd=s_dir) # to make sure we are not already on branch to be deleted
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
checkout_branch(default_branch, s_dir=sourcedir, fetch_and_reset=True)
update_submodules(s_dir=sourcedir)

app.logger.info('Python version is: %s' % sys.version)

@app.route('/generate', methods=['GET', 'POST'])
def generate():
    try:
        chosen_branch = request.form['branch']
        if not is_valid_branch(chosen_branch):
            raise Exception("bad branch")

        chosen_vehicle = request.form['vehicle']
        if not chosen_vehicle in VEHICLES:
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


def filter_build_options_by_category(build_options, category):
    return sorted([f for f in build_options if f.category == category], key=lambda x: x.description.lower())

def parse_build_categories(build_options):
    return sorted(list(set([f.category for f in build_options])))

@app.route('/')
def home():
    app.logger.info('Rendering index.html')
    return render_template('index.html',
                           get_branches=get_branches,
                           get_vehicles=get_vehicles,
                           get_default_branch=get_default_branch,
                           get_default_vehicle=get_default_vehicle)

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

if __name__ == '__main__':
    app.run()
