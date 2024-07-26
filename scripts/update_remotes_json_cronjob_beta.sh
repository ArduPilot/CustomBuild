#!/bin/bash

# this script is intended to be run from a crontab owned by the
# custom user on ArduPilot's autotest server
# to do a hot reload of remotes.json on custom-beta.ardupilot.org

# CBS_REMOTES_RELOAD_TOKEN can be supplied as an environment
# variable in the crontab line, for example:

# 0 * * * * CBS_REMOTES_RELOAD_TOKEN=8d64ed06945 /home/custom/beta/CustomBuild/scripts/fetch_release_cronjob.sh

# or can be read from base/secrets/reload_token (the token from the file gets the preference)

CUSTOM_HOME=/home/custom
TOPDIR=$CUSTOM_HOME/beta
LOGDIR=$TOPDIR/cron
BASEDIR=$TOPDIR/base

# Maximum number of log files to retain
MAX_LOG_FILES=50

# Get the current timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Function to clean up old log files
cleanup_old_logs() {
  # Find and sort log files by modification time, oldest first
  LOG_FILES=($(ls -1t ${LOGDIR}/fetch_releases_*.log \
                      ${LOGDIR}/fetch_whitelisted_tags_*.log \
                      2>/dev/null))

  # Count the number of log files
  NUM_LOG_FILES=${#LOG_FILES[@]}

  # If the number of log files is greater than the maximum allowed
  if [ $NUM_LOG_FILES -gt $MAX_LOG_FILES ]; then

    # Loop through and delete the oldest files
    for ((i = $MAX_LOG_FILES ; i < $NUM_LOG_FILES ; i++ )); do
      rm -f "${LOG_FILES[$i]}"
    done

  fi
}

# Method to reload remotes on custom build server app
reload_remotes_on_app() {
    local token_file="$BASEDIR/secrets/reload_token"
    local token

    # Check if the token file exists and is readable
    if [[ -f "$token_file" && -r "$token_file" ]]; then
        # Read the token from the file
        token=$(cat "$token_file")
    else
        echo "Token can't be retrieved from the file."
        # Try to get the token from the environment variable
        token=$CBS_REMOTES_RELOAD_TOKEN
    fi

    # Check if token is still empty
    if [[ -z "$token" ]]; then
        echo "Error: Token could not be retrieved."
        return 1
    fi

    # Send the curl request
    curl -X POST https://custom-beta.ardupilot.org/refresh_remotes \
        -H "Content-Type: application/json" \
        -d "{\"token\": \"$token\"}"

    return 0
}

# Call the cleanup function before executing the main script
cleanup_old_logs

# Run fetch_releases.py to add official releases from AP
python3 $TOPDIR/CustomBuild/scripts/fetch_releases.py \
        --basedir $BASEDIR \
        >> $LOGDIR/fetch_releases_${TIMESTAMP}.log 2>&1

# Run fetch_whitelisted_tags.py to add tags from whitelisted repos
python3 $TOPDIR/CustomBuild/scripts/fetch_whitelisted_tags.py \
        --basedir $BASEDIR \
        >> $LOGDIR/fetch_whitelisted_tags_${TIMESTAMP}.log 2>&1

# Call the reload_remotes_on_app function to refresh remotes.json on app
reload_remotes_on_app
