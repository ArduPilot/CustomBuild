import json
import optparse
import os
import re
import requests

IGNORE_VERSIONS_BEFORE = '4.3'


def version_number_and_type(git_hash, ap_source_subdir):
    url = (
        "https://raw.githubusercontent.com/ArduPilot/ardupilot/"
        f"{git_hash}/{ap_source_subdir}/version.h"
    )
    response = requests.get(url=url)

    if response.status_code != 200:
        print(response.text)
        print(url)
        raise Exception(
            "Couldn't fetch version.h from github server. "
            f"Got status code {response.status_code}"
        )

    exp = re.compile(
        r'#define FIRMWARE_VERSION (\d+),(\d+),(\d+),FIRMWARE_VERSION_TYPE_(\w+)'  # noqa
    )
    matches = re.findall(exp, response.text)
    major, minor, patch, fw_type = matches[0]
    fw_type = fw_type.lower()

    if fw_type == 'official':
        # to avoid any confusion, beta is also 'official' ;-)
        fw_type = 'stable'
    return f'{major}.{minor}.{patch}', fw_type


def fetch_tags_from_github():
    url = 'https://api.github.com/repos/ardupilot/ardupilot/git/refs/tags'
    headers = {
        'X-GitHub-Api-Version': '2022-11-28',
        'Accept': 'application/vnd.github+json'
    }
    response = requests.get(url=url, headers=headers)
    if response.status_code != 200:
        print(response.text)
        print(url)
        raise Exception(
            "Couldn't fetch tags from github server. "
            f"Got status code {response.status_code}"
        )

    tags_objs = response.json()
    return tags_objs


def remove_duplicate_entries(releases):
    temp = {}
    for release in releases:
        # if we have already seen a version with similar hash
        # and we now see a beta release with same hash, we skip it
        if temp.get(release['commit_reference']) and \
           release['release_type'] == 'beta':
            continue

        temp[release['commit_reference']] = release

    return list(temp.values())


def construct_vehicle_versions_list(vehicle, ap_source_subdir,
                                    fw_server_vehicle_sdir,
                                    tag_filter_exps, tags):
    ret = []
    for tag_info in tags:
        tag = tag_info['ref'].replace('refs/tags/', '')

        matches = []
        for exp in tag_filter_exps:
            # the regexes capture two groups
            # first group is the matched substring itself
            # second group is the tag body (e.g., beta, stable, 4.5.1 etc)
            matches.extend(re.findall(re.compile(exp), tag))

        if matches:
            matched_string, tag_body = matches[0]

            if len(matched_string) < len(tag):
                print(
                    f"Partial match. Ignoring. Matched '{matched_string}' "
                    f"in '{tag}'."
                )
                continue

            try:
                v_num, v_type = version_number_and_type(
                    tag_info['object']['sha'],
                    ap_source_subdir
                )
            except Exception as e:
                print(f'Cannot determine version number for tag {tag}')
                print(e)
                continue

            if v_num < IGNORE_VERSIONS_BEFORE:
                print(f"{v_num} Version too old. Ignoring.")
                continue

            if re.search(r'\d+\.\d+\.\d+', tag_body):
                # we do stable version tags in this format
                # e.g. Rover-4.5.1, Copter-4.5.1, where Rover and Copter
                # are prefixes and 4.5.1 is the tag body
                # artifacts for these versions are stored in firmware
                # server at stable-x.y.z subdirs
                afcts_url = (
                    f'https://firmware.ardupilot.org/{fw_server_vehicle_sdir}'
                    f'/stable-{tag_body}'
                )
            else:
                afcts_url = (
                    f'https://firmware.ardupilot.org/{fw_server_vehicle_sdir}'
                    f'/{tag_body}'
                )

            ret.append({
                'release_type': v_type,
                'version_number': v_num,
                'ap_build_artifacts_url': afcts_url,
                'commit_reference': tag_info['object']['sha']
            })

    ret = remove_duplicate_entries(ret)

    # entry for master
    ret.append({
        'release_type': 'latest',
        'version_number': 'NA',
        'ap_build_artifacts_url': (
            f'https://firmware.ardupilot.org/{fw_server_vehicle_sdir}/latest'
        ),
        'commit_reference': 'refs/heads/master'
    })

    return {
        'name': vehicle,
        'releases': ret
    }


def run(base_dir, remote_name):
    remotes_json_path = os.path.join(base_dir, 'configs', 'remotes.json')

    tags = fetch_tags_from_github()
    vehicles = []

    vehicles.append(construct_vehicle_versions_list(
        "Copter",
        "ArduCopter",
        "Copter",
        [
            "(ArduCopter-(beta-4.3|beta|stable))",
            "(Copter-(\d+\.\d+\.\d+))"  # noqa
        ],
        tags
    ))

    vehicles.append(construct_vehicle_versions_list(
        "Plane",
        "ArduPlane",
        "Plane",
        [
            "(ArduPlane-(beta-4.3|beta|stable))",
            "(Plane-(\d+\.\d+\.\d+))"  # noqa
        ],
        tags
    ))

    vehicles.append(construct_vehicle_versions_list(
        "Rover",
        "Rover",
        "Rover",
        [
            "(APMrover2-(beta-4.3|beta|stable))",
            "(Rover-(\d+\.\d+\.\d+))"  # noqa
        ],
        tags
    ))

    vehicles.append(construct_vehicle_versions_list(
        "Sub",
        "ArduSub",
        "Sub",
        [
            "(ArduSub-(beta-4.3|beta|stable))",
            "(Sub-(\d+\.\d+\.\d+))"  # noqa
        ],
        tags
    ))

    vehicles.append(construct_vehicle_versions_list(
        "AntennaTracker",
        "AntennaTracker",
        "AntennaTracker",
        [
            "(AntennaTracker-(beta-4.3|beta|stable))",
            "(Tracker-(\d+\.\d+\.\d+))"  # noqa
        ],
        tags
    ))

    vehicles.append(construct_vehicle_versions_list(
        "Blimp",
        "Blimp",
        "Blimp",
        [
            "(Blimp-(beta-4.3|beta|stable|\d+\.\d+\.\d+))"  # noqa
        ],
        tags
    ))

    vehicles.append(construct_vehicle_versions_list(
        "Heli",
        "ArduCopter",
        "Copter",
        [
            "(ArduCopter-(beta-4.3|beta|stable)-heli)"
        ],
        tags
    ))

    remotes_json = {
        "name": remote_name,
        "url": "https://github.com/ardupilot/ardupilot.git",
        "vehicles": vehicles
    }

    try:
        with open(remotes_json_path, 'r') as f:
            remotes = json.loads(f.read())

        # remove existing remote entry from the list
        temp = []
        for remote in remotes:
            if remote['name'] != remote_name:
                temp.append(remote)
        remotes = temp
    except Exception as e:
        print(e)
        print("Writing to empty file")
        remotes = []

    with open(remotes_json_path, 'w') as f:
        remotes.append(remotes_json)
        f.write(json.dumps(remotes, indent=2))
        print(f"Wrote {remotes_json_path}")


if __name__ == "__main__":
    parser = optparse.OptionParser("fetch_releases.py")
    parser.add_option(
        "", "--basedir", type="string",
        default=os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "base")
        ),
        help="base directory"
    )

    parser.add_option(
        "", "--remotename", type="string",
        default="ardupilot",
        help="Remote name to write in json file"
    )

    cmd_opts, cmd_args = parser.parse_args()
    basedir = os.path.abspath(cmd_opts.basedir)
    remotename = cmd_opts.remotename
    run(base_dir=basedir, remote_name=remotename)
