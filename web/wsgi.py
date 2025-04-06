#!/usr/bin/env python3

import logging
import sys
import os

cbs_basedir = os.environ.get('CBS_BASEDIR')

if cbs_basedir:
    # Ensure base subdirectories exist
    os.makedirs(os.path.join(cbs_basedir, 'builds'), exist_ok=True)
    os.makedirs(os.path.join(cbs_basedir, 'configs'), exist_ok=True)

    # Ensure remotes.json exists
    remotes_json_path = os.path.join(cbs_basedir, 'configs', 'remotes.json')
    if not os.path.isfile(remotes_json_path):
        print("Creating remotes.json...")
        from scripts import fetch_releases
        fetch_releases.run(
            base_dir=os.path.join(
                os.path.dirname(remotes_json_path),
                '..',
            ),
            remote_name="ardupilot",
        )

logging.basicConfig(stream=sys.stderr)
sys.path.insert(0, os.path.dirname(__file__))
from app import app as application
application.secret_key = 'key'
