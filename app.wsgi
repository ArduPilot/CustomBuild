#!/usr/bin/env python3

import logging
import sys
import os
logging.basicConfig(stream=sys.stderr)
sys.path.insert(0, os.path.dirname(__file__))
from app import app as application
application.secret_key = 'key'
