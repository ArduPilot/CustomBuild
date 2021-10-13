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
from dataclasses import dataclass

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


@dataclass
class Feature:
    category: str
    label: str
    define: str
    description: str
    default: int
    dependency: str

# list of build options to offer
# NOTE: the dependencies must be written as a single string with commas and no spaces, eg. 'dependency1,dependency2'
BUILD_OPTIONS = [
    Feature('AHRS', 'EKF3', 'HAL_NAVEKF3_AVAILABLE', 'Enable EKF3', 1, None),
    Feature('AHRS', 'EKF2', 'HAL_NAVEKF2_AVAILABLE', 'Enable EKF2', 0, None),
    Feature('AHRS', 'AHRS_EXT', 'HAL_EXTERNAL_AHRS_ENABLED', 'Enable External AHRS', 0, None),
    Feature('AHRS', 'TEMPCAL', 'HAL_INS_TEMPERATURE_CAL_ENABLE', 'Enable IMU Temperature Calibration', 0, None),
    Feature('AHRS', 'VISUALODOM', 'HAL_VISUALODOM_ENABLED', 'Enable Visual Odometry', 0, None),

    Feature('Safety', 'PARACHUTE', 'HAL_PARACHUTE_ENABLED', 'Enable Parachute', 0, None),
    Feature('Safety', 'PROXIMITY', 'HAL_PROXIMITY_ENABLED', 'Enable Proximity', 0, None),

    Feature('Battery', 'BATTMON_FUEL', 'HAL_BATTMON_FUEL_ENABLE', 'Enable Fuel BatteryMonitor', 0, None),
    Feature('Battery', 'BATTMON_SMBUS', 'HAL_BATTMON_SMBUS_ENABLE', 'Enable SMBUS BatteryMonitor', 0, None),

    Feature('Ident', 'ADSB', 'HAL_ADSB_ENABLED', 'Enable ADSB', 0, None),
    Feature('Ident', 'ADSB_SAGETECH', 'HAL_ADSB_SAGETECH_ENABLED', 'Enable SageTech ADSB', 0, 'ADSB'),
    Feature('Ident', 'ADSB_UAVIONIX', 'HAL_ADSB_UAVIONIX_MAVLINK_ENABLED', 'Enable Uavionix ADSB', 0, 'ADSB'),
    Feature('Ident', 'AIS', 'HAL_AIS_ENABLED', 'Enable AIS', 0, None),

    Feature('Telemetry', 'CRSF', 'HAL_CRSF_TELEM_ENABLED', 'Enable CRSF Telemetry', 0, None),
    Feature('Telemetry', 'CRSFText', ' HAL_CRSF_TELEM_TEXT_SELECTION_ENABLED', 'Enable CRSF Text Param Selection', 0, 'CRSF'),
    Feature('Telemetry', 'HIGHLAT2', 'HAL_HIGH_LATENCY2_ENABLED', 'Enable HighLatency2 Support', 0, None),
    Feature('Telemetry', 'HOTT', 'HAL_HOTT_TELEM_ENABLED', 'Enable HOTT Telemetry', 0, None),
    Feature('Telemetry', 'SPEKTRUM', 'HAL_SPEKTRUM_TELEM_ENABLED', 'Enable Spektrum Telemetry', 0, None),

    Feature('MSP', 'MSP', 'HAL_MSP_ENABLED', 'Enable MSP Telemetry and MSP OSD', 0, 'OSD'),
    Feature('MSP', 'MSP_SENSORS', 'HAL_MSP_SENSORS_ENABLED', 'Enable MSP Sensors', 0, 'MSP_GPS,MSP_BARO,MSP_COMPASS,MSP_AIRSPEED,MSP,MSP_OPTICALFLOW,MSP_RANGEFINDER,OSD'),
    Feature('MSP', 'MSP_GPS', 'HAL_MSP_GPS_ENABLED', 'Enable MSP GPS', 0, 'MSP,OSD'),
    Feature('MSP', 'MSP_COMPASS', 'HAL_MSP_COMPASS_ENABLED', 'Enable MSP Compass', 0, 'MSP,OSD'),
    Feature('MSP', 'MSP_BARO', 'HAL_MSP_BARO_ENABLED', 'Enable MSP Baro', 0, 'MSP,OSD'),
    Feature('MSP', 'MSP_AIRSPEED', 'HAL_MSP_AIRSPEED_ENABLED', 'Enable MSP AirSpeed', 0, 'MSP,OSD'),
    Feature('MSP', 'MSP_OPTICALFLOW', 'HAL_MSP_OPTICALFLOW_ENABLED', 'Enable MSP OpticalFlow', 0, 'MSP,OSD'), # also OPTFLOW dep
    Feature('MSP', 'MSP_RANGEFINDER', 'HAL_MSP_RANGEFINDER_ENABLED', 'Enable MSP Rangefinder', 0, 'MSP,OSD'),
    Feature('MSP', 'MSP_DISPLAYPORT', 'HAL_WITH_MSP_DISPLAYPORT', 'Enable MSP DisplayPort OSD (aka CANVAS MODE)', 0, 'MSP,OSD'),

    Feature('ICE', 'EFI', 'HAL_EFI_ENABLED', 'Enable EFI Monitoring', 0, None),
    Feature('ICE', 'EFI_NMPWU', 'HAL_EFI_NWPWU_ENABLED', 'Enable EFI NMPMU', 0, None),

    Feature('OSD', 'OSD', 'OSD_ENABLED', 'Enable OSD', 0, None),
    Feature('OSD', 'PLUSCODE', 'HAL_PLUSCODE_ENABLE', 'Enable PlusCode', 0, None),
    Feature('OSD', 'RUNCAM', 'HAL_RUNCAM_ENABLED', 'Enable RunCam', 0, None),
    Feature('OSD', 'SMARTAUDIO', 'HAL_SMARTAUDIO_ENABLED', 'Enable SmartAudio', 0, None),
    Feature('OSD', 'OSD_PARAM', 'OSD_PARAM_ENABLED', 'Enable OSD param', 0, 'OSD'),
    Feature('OSD', 'OSD_SIDEBARS', 'HAL_OSD_SIDEBAR_ENABLE', 'Enable Scrolling Sidebars', 0, 'OSD'),

    Feature('CAN', 'PICCOLOCAN', 'HAL_PICCOLO_CAN_ENABLE', 'Enable PiccoloCAN', 0, None),
    Feature('CAN', 'MPPTCAN', 'HAL_MPPT_PACKETDIGITAL_CAN_ENABLE', 'Enable MPPT CAN', 0, None),

    Feature('Mode', 'MODE_ZIGZAG', 'MODE_ZIGZAG_ENABLED', 'Enable Mode ZigZag', 0, None),
    Feature('Mode', 'MODE_SYSTEMID', 'MODE_SYSTEMID_ENABLED', 'Enable Mode SystemID', 0, None),
    Feature('Mode', 'MODE_SPORT', 'MODE_SPORT_ENABLED', 'Enable Mode Sport', 0, None),
    Feature('Mode', 'MODE_FOLLOW', 'MODE_FOLLOW_ENABLED', 'Enable Mode Follow', 0, None),
    Feature('Mode', 'MODE_TURTLE', 'MODE_TURTLE_ENABLED', 'Enable Mode Turtle', 0, None),
    Feature('Mode', 'MODE_GUIDED_NOGPS', 'MODE_GUIDED_NOGPS_ENABLED', 'Enable Mode Guided NoGPS', 0, None),

    Feature('Gimbal', 'MOUNT', 'HAL_MOUNT_ENABLED', 'Enable Mount', 0, None),
    Feature('Gimbal', 'SOLOGIMBAL', 'HAL_SOLO_GIMBAL_ENABLED', 'Enable Solo Gimbal', 0, None),

    Feature('Other', 'SOARING', 'HAL_SOARING_ENABLED', 'Enable Soaring', 0, None),
    Feature('Other', 'DEEPSTALL', 'HAL_LANDING_DEEPSTALL_ENABLED', 'Enable Deepstall Landing', 0, None),
    Feature('Other', 'DSP',  'HAL_WITH_DSP', 'Enable DSP for In-Flight FFT', 0, None),
    Feature('Other', 'SPRAYER', 'HAL_SPRAYER_ENABLED', 'Enable Sprayer', 0, None),
    Feature('Other', 'TORQEEDO', 'HAL_TORQEEDO_ENABLED', 'Enable Torqeedo Motors', 0, None),
    Feature('Other', 'RPM', 'RPM_ENABLED', 'Enable RPM sensors', 0, None),
    Feature('Other', 'DISPLAY', 'HAL_DISPLAY_ENABLED', 'Enable I2C Displays', 0, None),
    Feature('Other', 'GRIPPER', 'GRIPPER_ENABLED', 'Enable Gripper', 0, None),
    Feature('Other', 'BEACON', 'BEACON_ENABLED', 'Enable Beacon', 0, None),
    Feature('Other', 'LANDING_GEAR', 'LANDING_GEAR_ENABLED', 'Enable Landing Gear', 0, None),
    Feature('Other', 'NMEA_OUTPUT', 'HAL_NMEA_OUTPUT_ENABLED', 'Enable NMEA Output', 0, None),
    Feature('Other', 'BARO_WIND_COMP', 'HAL_BARO_WIND_COMP_ENABLED', 'Enable Baro Wind Compensation', 0, None),
    Feature('Other', 'GENERATOR', 'HAL_GENERATOR_ENABLED', 'Enable Generator', 0, None),
    Feature('Other', 'AC_OAPATHPLANNER', 'AC_OAPATHPLANNER_ENABLED', 'Enable Object Avoidance Path Planner', 0, None),
    Feature('Other', 'WINCH', 'WINCH_ENABLED', 'Enable Winch', 0, None),
    Feature('Other', 'GPS_MOVING_BASELINE', 'GPS_MOVING_BASELINE', 'Enable GPS Moving Baseline', 0, None),
    # disable OPTFLOW until we cope with enum clash
    # Feature('Other', 'OPTFLOW', 'OPTFLOW', 'Enable Optical Flow', 0, None),

    Feature('Plane', 'QUADPLANE', 'HAL_QUADPLANE_ENABLED', 'Enable QuadPlane support', 0, None),
    ]

BUILD_OPTIONS.sort(key=lambda x: x.category)

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
        app.logger.info(ex)('Build failed: ', ex)
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
            app.logger.error(ex)('Failed queue: ', ex)
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
            elif build.find('The configuration failed') != -1 or build.find('Build failed') != -1:
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

    
def get_build_options(category):
    return sorted([f for f in BUILD_OPTIONS if f.category == category], key=lambda x: x.description.lower())

def get_build_categories():
    return sorted(list(set([f.category for f in BUILD_OPTIONS])))

def get_vehicles():
    return (VEHICLES, default_vehicle)

@app.route('/')
def home():
    app.logger.info('Rendering index.html')
    return render_template('index.html',
                           get_boards=get_boards,
                           get_vehicles=get_vehicles,
                           get_build_options=get_build_options,
                           get_build_categories=get_build_categories)

@app.route("/builds/<path:name>")
def download_file(name):
    app.logger.info('Downloading %s' % name)
    return send_from_directory(os.path.join(basedir,'builds'), name, as_attachment=False)

if __name__ == '__main__':
    app.run()
