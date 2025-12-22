#!/usr/bin/env python3

import os
import base64
from flask import Flask, render_template, request, send_from_directory, jsonify, redirect
from threading import Thread
import sys
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
import build_manager
from builder import Builder

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
outdir_parent = os.path.join(basedir, 'artifacts')
workdir_parent = os.path.join(basedir, 'workdir')

appdir = os.path.dirname(__file__)

builds_dict = {}
REMOTES = None

repo = ap_git.GitRepo.clone_if_needed(
    source="https://github.com/ardupilot/ardupilot.git",
    dest=sourcedir,
    recurse_submodules=True,
)

vehicles_manager = metadata_manager.VehiclesManager()
ap_src_metadata_fetcher = metadata_manager.APSourceMetadataFetcher(
    ap_repo=repo,
    caching_enabled=True,
    redis_host=os.getenv('CBS_REDIS_HOST', default='localhost'),
    redis_port=os.getenv('CBS_REDIS_PORT', default='6379'),
)
versions_fetcher = metadata_manager.VersionsFetcher(
    remotes_json_path=os.path.join(basedir, 'configs', 'remotes.json'),
    ap_repo=repo
)

manager = build_manager.BuildManager(
    outdir=outdir_parent,
    redis_host=os.getenv('CBS_REDIS_HOST', default='localhost'),
    redis_port=os.getenv('CBS_REDIS_PORT', default='6379')
)
cleaner = build_manager.BuildArtifactsCleaner()
progress_updater = build_manager.BuildProgressUpdater()

versions_fetcher.start()
cleaner.start()
progress_updater.start()

if os.getenv('CBS_ENABLE_INBUILT_BUILDER', default='1') == '1':
    builder = Builder(
        workdir=workdir_parent,
        source_repo=repo
    )
    builder_thread = Thread(
        target=builder.run,
        daemon=True
    )
    builder_thread.start()

app = Flask(__name__, template_folder='templates')

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
        version = request.form['version']
        remote_name, commit_ref = version.split('/', 1)
        remote_info = versions_fetcher.get_remote_info(remote_name)

        if remote_info is None:
            raise Exception(f"Remote {remote_name} is not whitelisted.")

        vehicle = request.form['vehicle']
        version_info = versions_fetcher.get_version_info(
            vehicle_name=vehicle,
            remote=remote_name,
            commit_ref=commit_ref
        )

        if version_info is None:
            raise Exception("Commit reference invalid or not listed to be built for given vehicle for remote")

        board = request.form['board']
        boards_at_commit = ap_src_metadata_fetcher.get_boards(
            remote=remote_name,
            commit_ref=commit_ref,
            vehicle=vehicle,
        )
        if board not in boards_at_commit:
            raise Exception("bad board")

        all_features = ap_src_metadata_fetcher.get_build_options_at_commit(
            remote=remote_name,
            commit_ref=commit_ref
        )

        chosen_defines = {
            feature.define
            for feature in all_features
            if request.form.get(feature.label) == "1"
        }

        git_hash = repo.commit_id_for_remote_ref(
            remote=remote_name,
            commit_ref=commit_ref
        )

        build_info = build_manager.BuildInfo(
            vehicle=vehicle,
            remote_info=remote_info,
            git_hash=git_hash,
            board=board,
            selected_features=chosen_defines
        )

        forwarded_for = request.headers.get('X-Forwarded-For', None)
        if forwarded_for:
            client_ip = forwarded_for.split(',')[0].strip()
        else:
            client_ip = request.remote_addr

        build_id = manager.submit_build(
            build_info=build_info,
            client_ip=client_ip,
        )

        app.logger.info('Redirecting to /viewlog')
        return redirect('/viewlog/'+build_id)

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

@app.route("/builds/<string:build_id>/artifacts/<path:name>")
def download_file(build_id, name):
    path = os.path.join(
        basedir,
        'artifacts',
        build_id,
    )
    app.logger.info('Downloading %s/%s' % (path, name))
    return send_from_directory(path, name, as_attachment=False)

@app.route("/boards_and_features/<string:vehicle_name>/<string:remote_name>/<string:commit_reference>", methods=['GET'])
def boards_and_features(vehicle_name, remote_name, commit_reference):
    commit_reference = base64.urlsafe_b64decode(commit_reference).decode()

    if not versions_fetcher.is_version_listed(vehicle_name=vehicle_name, remote=remote_name, commit_ref=commit_reference):
        return "Bad request. Commit reference not allowed to build for the vehicle.", 400

    app.logger.info('Board list and build options requested for %s %s %s' % (vehicle_name, remote_name, commit_reference))
    # getting board list for the branch
    with repo.get_checkout_lock():
        boards = ap_src_metadata_fetcher.get_boards(
            remote=remote_name,
            commit_ref=commit_reference,
            vehicle=vehicle_name,
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
        'default_board' : boards[0],
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
    return jsonify(vehicles_manager.get_all_vehicle_names_sorted())

@app.route("/get_defaults/<string:vehicle_name>/<string:remote_name>/<string:commit_reference>/<string:board_name>", methods = ['GET'])
def get_deafults(vehicle_name, remote_name, commit_reference, board_name):
    # Heli is built on copter
    if vehicle_name == "Heli":
        vehicle_name = "Copter"
        board_name += "-heli"

    commit_reference = base64.urlsafe_b64decode(commit_reference).decode()
    version_info = versions_fetcher.get_version_info(vehicle_name=vehicle_name, remote=remote_name, commit_ref=commit_reference)

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

@app.route('/builds', methods=['GET'])
def get_all_builds():
    all_build_ids = manager.get_all_build_ids()
    all_build_info = [
        {
            **manager.get_build_info(build_id).to_dict(),
            'build_id': build_id
        }
        for build_id in all_build_ids
    ]

    all_build_info_sorted = sorted(
        all_build_info,
        key=lambda x: x['time_created'],
        reverse=True,
    )

    return (
        jsonify(all_build_info_sorted),
        200
    )

@app.route('/builds/<string:build_id>', methods=['GET'])
def get_build_by_id(build_id):
    if not manager.build_exists(build_id):
        response = {
            'error': f'build with id {build_id} does not exist.',
        }
        return jsonify(response), 200

    response = {
        **manager.get_build_info(build_id).to_dict(),
        'build_id': build_id
    }

    return jsonify(response), 200

if __name__ == '__main__':
    app.run()
