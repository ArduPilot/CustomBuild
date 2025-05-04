"""
This script automates the listing of tagged versions of
the ArduPilot source code from various white-listed forks
from GitHub on the Custom Build Server.
It performs the following tasks:

1. **Fetch Tags**: Utilizes the GitHub API to retrieve the list of tags from
   the specified remote repository.
2. **Filter Tags**: Identifies tags that start with the prefix 'custom-build/'.
3. **Update remotes.json**: Adds information about these custom-build tags to
   the `remotes.json` file, enabling building these versions.

Tag Naming Conventions:
- Tags named in the format `custom-build/xyz` are allowed to be built
  for all vehicles.
- Tags in the format `custom-build/vehicle/xyz` are allowed to be built
  for the specified vehicle only.

Examples:
- A tag named `custom-build/some-test-work` will be listed under all
  the vehicles.
- A tag named `custom-build/Copter/some-test-work` will be listed under
  Copter only.

Note:
- Vehicle names are case-sensitive. e.g., copter is not Copter.
"""
import json
import optparse
import os
import requests


# TODO: move this to base/configs/whitelisted_custom_tag_remotes.json
remotes = [
    "ardupilot",
    "tridge",
    "peterbarker",
    "rmackay9",
    "shiv-tyagi",
    "andyp1per",
]

vehicles = [
    'Copter',
    'Plane',
    'Rover',
    'Sub',
    'AntennaTracker',
    'Blimp',
    'Heli',
    'AP_Periph',
]


def fetch_tags_from_github(remote):
    """Returns a list of dictionaries with tag details (name and commit SHA)
    for the ardupilot repo in the specified remote using the GitHub API
    See https://docs.github.com/en/rest/git/refs?apiVersion=2022-11-28
    for more details
    """
    url = f'https://api.github.com/repos/{remote}/ardupilot/git/refs/tags'
    headers = {
        'X-GitHub-Api-Version': '2022-11-28',
        'Accept': 'application/vnd.github+json'
    }

    token = os.getenv("CBS_GITHUB_ACCESS_TOKEN")
    if token:
        headers['Authorization'] = f"Bearer {token}"

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


def construct_versions_map(remotes, vehicles):
    """
    Returns a dictionary containing the list of versions
    allowed to be built for different remotes and vehicles.

    The returned dictionary is structured as follows:
    - The first-level keys represent the remote names.
    - Each first-level key maps to a nested dictionary.
    - The nested dictionary has keys representing vehicle names.
    - Each vehicle name key maps to a list of dictionaries
    containing the information about the versions allowed
    to be built for that particular remote and vehicle.
    - Refer remotes.schema.json to see the schema of the
    dictionaries about the version information.

    Example:
    {
        'remote1': {
            'vehicleA': [{...}, {...}],
            'vehicleB': [{...}, {...}, {...}]
        },
        'remote2': {
            'vehicleA': [{...}, {...}],
            'vehicleB': [{...}, {...}, {...}]
            'vehicleC': [{...}, {...}],
        }
    }
    """

    ret = {
        remote: {
            vehicle: [] for vehicle in vehicles
        } for remote in remotes
    }

    for remote in remotes:
        try:
            # fetch tag info for ardupilot repo in the remote from github
            tag_objs = fetch_tags_from_github(remote)
        except Exception as e:
            print(e)
            print("Skipping this remote...")
            continue

        for tag_info in tag_objs:
            ref = tag_info['ref']
            ref = ref.replace('refs/tags/', '')

            s = ref.split('/', 3)

            # skip if tag name does not start with custom-build/
            if len(s) <= 1 or s[0] != 'custom-build':
                continue

            vehicles_for_tag = []
            if s[1] in vehicles:
                if len(s) == 2:
                    print(f'Found {ref}. Incomplete tag. Skipping.')
                    # tag is named like custom-build/vehicle
                    # this format is incorrect
                    continue

                # tag is in the format custom-build/vehicle/xyz
                # list the tag only under this vehicle
                vehicles_for_tag = [s[1],]
                print(f'Found {ref}. Adding to {s[1]}.')
            else:
                # tag is in the format custom-build/xyz
                # no vehicle is specified in tag name
                # list the tag under all vehicles
                vehicles_for_tag = vehicles
                print(f'Found {ref}. Adding to all vehicles.')

            for vehicle in vehicles_for_tag:
                # append an entry to the list of versions listed to be built
                # for the remote and vehicle
                ret[remote][vehicle].append(
                    {
                        'release_type': 'tag',
                        'version_number': s[-1],
                        'ap_build_artifacts_url': f'https://firmware.ardupilot.org/{vehicle}/latest',  # noqa # use master defaults for auto-fetched tags
                        'commit_reference': tag_info['object']['sha']
                    }
                )

    return ret


def read_remotes_json_file(path):
    """Returns python object constructed from the contents of
    remotes.json file

    If the file cannot be read, it returns an empty list
    """
    try:
        with open(path, 'r') as f:
            remotes = json.loads(f.read())
    except Exception as e:
        print(e)
        print("Returning empty list")
        remotes = []

    return remotes


def write_remotes_json_file(path, remotes_json_obj):
    """Serialize the remotes_json_obj object and
    write to the remotes.json file
    """
    with open(path, 'w') as f:
        f.write(json.dumps(remotes_json_obj, indent=2))
        print(f"Wrote {path}")


def update_remotes_json(path, new_versions_map):
    """Update remotes.json with the versions listed in new_versions_map
    """
    remotes_json_obj = read_remotes_json_file(path)

    # create a dict remote names mapped to the objects containing the
    # information about that remote in remotes_json_obj to avoid
    # iterating over the list to access the object every time
    rname_obj_map = {
        remote['name']: remote for remote in remotes_json_obj
    }

    # create another dict with remote names mapped to a dict.
    # In the secondary dict, the vehicle names are mapped
    # to the objects in the remotes_json_obj containing
    # the information about the vehicles listed under the remote
    rname_vname_obj_map = {
        remote['name']: {
            vehicle['name']: vehicle for vehicle in remote['vehicles']
        } for remote in remotes_json_obj
    }

    for remote_name, vehicles_obj_dict in new_versions_map.items():
        # we do not have the remote listed in existing remotes_json_obj
        if not rname_obj_map.get(remote_name):
            print(f'Remote {remote_name} '
                  f'does not exist in existing remotes.json. Adding.')
            # create object containing the information about the remote
            remote_obj = {
                'name': remote_name,
                'url': f'https://github.com/{remote_name}/ardupilot.git',
                'vehicles': []
            }

            # append to the remotes_json_obj
            remotes_json_obj.append(remote_obj)
            # add a reference to the object in rname_obj_map
            rname_obj_map[remote_name] = remote_obj
            # no vehicles are listed for this remote yet,
            # we populate them as we see them ahead
            rname_vname_obj_map[remote_name] = dict()

        for vehicle_name, versions in vehicles_obj_dict.items():
            # the vehicle is not listed under this remote
            if not rname_vname_obj_map[remote_name].get(vehicle_name):
                print(f'Vehicle {vehicle_name} does not exist '
                      f'for remote {remote_name} '
                      f'in existing remotes.json. Adding.')
                # create vehicle object
                vehicle_obj = {
                    'name': vehicle_name,
                    'releases': []
                }

                # append the vehicle object to the list of vehicle
                # objects under the remote
                rname_obj_map[remote_name]['vehicles'].append(vehicle_obj)
                # add a reference to this object under the remote
                # and the vehicle name
                rname_vname_obj_map[remote_name][vehicle_name] = vehicle_obj

            # remove duplicates and merge lists
            existing_list = rname_vname_obj_map[remote_name][vehicle_name]['releases']  # noqa
            new_versions_list = []
            for i in range(len(existing_list)):
                prefix = "tag"
                if existing_list[i]['release_type'][:len(prefix)] != prefix:
                    new_versions_list.append(existing_list[i])
            new_versions_list.extend(versions)

            # add the versions listed for this vehicle and
            # the remote in remotes_json_obj as mentioned above
            rname_vname_obj_map[remote_name][vehicle_name]['releases'] = new_versions_list  # noqa

    # write the updated obj to the remotes.json file
    write_remotes_json_file(path, remotes_json_obj)
    return


def run(base_dir):
    remotes_json_path = os.path.join(base_dir, 'configs', 'remotes.json')
    new_versions_map = construct_versions_map(remotes, vehicles)
    update_remotes_json(remotes_json_path, new_versions_map)


if __name__ == "__main__":
    parser = optparse.OptionParser("fetch_releases.py")
    parser.add_option(
        "", "--basedir", type="string",
        default=os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "base")
        ),
        help="base directory"
    )

    cmd_opts, cmd_args = parser.parse_args()
    basedir = os.path.abspath(cmd_opts.basedir)
    run(base_dir=basedir)
