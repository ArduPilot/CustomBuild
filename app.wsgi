#! /usr/bin/python3

import logging
import sys
logging.basicConfig(stream=sys.stderr)
sys.path.insert(0, '/home/will/GitHub/CustomBuild')
from app import app as application
application.secret_key = 'key'