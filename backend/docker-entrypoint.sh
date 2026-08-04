#!/bin/sh
set -e

find "$CBS_BASEDIR" \! -user ardupilot -exec chown ardupilot '{}' +
exec gosu ardupilot "$@"
