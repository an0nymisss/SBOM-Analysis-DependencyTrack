# Python script to fetch component info from DependencyTrack API and retrieve their version release dates
# Easily extendable for all current/future supported Repos in DependencyTrack
# Just define the repo function in main(), define URL in Globals, and send output to csv after parsing the data
# Author: Riddhi Suryavanshi

import subprocess
import requests
import json
import csv
import os
from urllib3.exceptions import InsecureRequestWarning
from datetime import datetime

''' Globals '''
PROJECT_UUID = ""  # From DependencyTrack
BASE_URL = "https://x.x.x.x"  # DependencyTrack Base URL
COMPONENT_INFO_URL = BASE_URL + "/api/v1/component/project/" + PROJECT_UUID + "?onlyOutdated=false&onlyDirect=false&searchText=&pageSize=100&pageNumber="
MAVEN_URL = "https://search.maven.org/solrsearch/select?q=g:{group}%20AND%20a:{artifact}%20AND%20v:{version}&rows=20&wt=json"
PYPI_URL = "https://pypi.org/pypi/{name}/{version}/json"
GO_URL = "https://proxy.golang.org/{namespace}/{name}/@v/{version}.info"
CARGO_URL = "https://crates.io/api/v1/crates/{name}/{version}"

# Read API key from file
file = open("api_key", "r")
API_KEY = file.read().strip()

def get_component_info():
    print('Fetching components from DependencyTrack...')
    # Suppress the warnings from urllib3
    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
    pageNumber = 1
    combined_data = []
    while True:
        response = requests.get(COMPONENT_INFO_URL + str(pageNumber), headers={"accept":"application/json", "X-Api-Key":API_KEY}, verify=False)
        data = response.text
        json_data = json.loads(data)
        pageNumber += 1
        if(len(json_data) == 0):   # break if no more pages are left to parse
            break
        # Append data of new page to old page's data
        combined_data.extend(json_data)
    number_of_components = len(combined_data)

    # Parse and store JSON data in a list of dictionaries for each component  
    component_data = []
    for component in range(number_of_components):
        if combined_data[component] and combined_data[component].get("repositoryMeta") and combined_data[component]["repositoryMeta"].get("namespace") is not None:
            component_data.append(
                {
                    "repositoryType" : combined_data[component]["repositoryMeta"]["repositoryType"],
                    "namespace" : combined_data[component].get("repositoryMeta").get("namespace"), # using get() to suprress KeyError
                    "name" : combined_data[component]["repositoryMeta"]["name"],
                    "version" : combined_data[component]["version"],
                    "latestVersion" : combined_data[component]["repositoryMeta"]["latestVersion"]
                }
            )
        elif combined_data[component].get("repositoryMeta") and combined_data[component].get("repositoryMeta").get("namespace") is None:
        # handle empty namespaces
            component_data.append(
                {
                    "repositoryType" : combined_data[component]["repositoryMeta"]["repositoryType"],
                    "namespace" : None,
                    "name" : combined_data[component]["repositoryMeta"]["name"],
                    "version" : combined_data[component]["version"],
                    "latestVersion" : combined_data[component]["repositoryMeta"]["latestVersion"]
                }
            )
    print('Data fetched. Please wait while release dates are gathered from repositories...')
    if response.status_code == 401:
        return False
    return component_data


def get_npm_release_date(namespace, name, version, latestVersion):
    release_date_installed_version: dict = {}
    release_date_latest_version: dict = {}
    try:
        if namespace is None:
            full_package_name = name  # For non-scoped packages
        else:
            full_package_name = f"{namespace}/{name}"
        # Run node docker image and remove it after command is run
        command = ["docker", "run", "--rm", "node:20.17.0-slim", "npm", "show", f"{full_package_name}", "time", "--json", "--no-warnings"]
        result = subprocess.run(command, capture_output=True, text=True, check=True, stderr=None)
        # Parse the JSON output
        release_times = json.loads(result.stdout)
        if version in release_times:
            release_date_installed_version = release_times[version]
        if latestVersion in release_times:
            release_date_latest_version = release_times[latestVersion]
        send_to_csv(namespace, name, version, release_date_installed_version, latestVersion, release_date_latest_version)
    except subprocess.CalledProcessError as e:
        print(f"Error while running npm command: {e}")
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON output: {e}")
    return release_date_installed_version, release_date_latest_version


def get_maven_release_date(namespace, name, version, latestVersion):
    try:
        Maven_url_version = MAVEN_URL.format(group = namespace, artifact = name, version = version)
        Maven_url_latest_version = MAVEN_URL.format(group = namespace, artifact = name, version = latestVersion)
        # Fetch info for installed version
        response_v = requests.get(Maven_url_version, verify=False)
        data_v = response_v.text
        json_data_v = json.loads(data_v)
        timestamp_epoch_v = json_data_v['response']['docs'][0]['timestamp']
        release_date_installed_version = datetime.utcfromtimestamp(timestamp_epoch_v / 1000).strftime('%Y-%m-%d %H:%M:%S')
        # Fetch info for latest version
        response_lv = requests.get(Maven_url_latest_version, verify=False)
        data_lv = response_lv.text
        json_data_lv = json.loads(data_lv)
        timestamp_epoch_lv = json_data_lv['response']['docs'][0]['timestamp']
        release_date_latest_version = datetime.utcfromtimestamp(timestamp_epoch_lv / 1000).strftime('%Y-%m-%d %H:%M:%S')
        send_to_csv(namespace, name, version, release_date_installed_version, latestVersion, release_date_latest_version)
    except:
        print('Error parsing Maven data')


def get_pypi_release_date(namespace, name, version, latestVersion):   
    try:  # assuming namespace is empty
        pypi_url_version = PYPI_URL.format(name = name, version = version)
        pypi_url_latest_version = PYPI_URL.format(name = name, version = latestVersion)
        # Fetch info for installed version
        response_v = requests.get(pypi_url_version, verify=False)
        json_data_v = response_v.json()
        release_date_installed_version = json_data_v['urls'][0]['upload_time']
        # Fetch info for latest version
        response_lv = requests.get(pypi_url_latest_version, verify=False)
        json_data_lv = response_lv.json()
        release_date_latest_version = json_data_lv['urls'][0]['upload_time']
        send_to_csv(namespace, name, version, release_date_installed_version, latestVersion, release_date_latest_version)
    except:
        print('Error parsing PyPi data')


def get_go_release_date(namespace, name, version, latestVersion):
    # DependencyTrack fetches from https://proxy.golang.org/
    try:
        go_url_version = GO_URL.format(namespace = namespace, name = name, version = version)
        go_url_latest_version = GO_URL.format(namespace = namespace, name = name, version = latestVersion)
        # Fetch info for installed version
        response_v = requests.get(go_url_version, verify=False)
        json_data_v = response_v.json()
        release_date_installed_version = json_data_v['Time']
        # Fetch info for latest version
        response_lv = requests.get(go_url_latest_version, verify=False)
        json_data_lv = response_lv.json()
        release_date_latest_version = json_data_lv['Time']
        send_to_csv(namespace, name, version, release_date_installed_version, latestVersion, release_date_latest_version)
    except:
        print('Error parsing Go Modules data')


def get_cargo_release_date(namespace, name, version, latestVersion):
    # DependencyTrack fetches from crates.io
    try:
        cargo_url_version = CARGO_URL.format(name = name, version = version)
        cargo_url_latest_version = CARGO_URL.format(name = name, version = latestVersion)
        # Fetch info for installed version
        response_v = requests.get(cargo_url_version, verify=False)
        json_data_v = response_v.json()
        release_date_installed_version = json_data_v['version']['created_at']
        # Fetch info for latest version
        response_lv = requests.get(cargo_url_latest_version, verify=False)
        json_data_lv = response_lv.json()
        release_date_latest_version = json_data_lv['version']['created_at']
        send_to_csv(namespace, name, version, release_date_installed_version, latestVersion, release_date_latest_version)
    except:
        print('Error parsing Cargo data')


# TODO:integrate remaining repos here


def send_to_csv(namespace, name, version, release_date_installed_version, latestVersion, release_date_latest_version):
    file_path = 'release_dates.csv'
    file_exists = os.path.isfile(file_path)
    with open(file_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        # If the file doesn't exist, write the header row
        if not file_exists:
            writer.writerow(['Namespace', 'Name', 'Installed Version', 'Release Date Installed Version', 'Latest Version', 'Release Date Latest Version'])
        writer.writerow([namespace, name, version, release_date_installed_version, latestVersion, release_date_latest_version])


def main():

    component_data = get_component_info()
    if not component_data:
        print("No component data found or authentication failed (DependencyTrack).")
        return
    
    for component in component_data:
        repositoryType = component["repositoryType"]
        namespace = component["namespace"]
        name = component["name"]
        version = component["version"]
        latestVersion = component["latestVersion"]
        if repositoryType == 'NPM':
            get_npm_release_date(namespace, name, version, latestVersion)  
        elif repositoryType == 'MAVEN':
            get_maven_release_date(namespace, name, version, latestVersion)
        elif repositoryType == 'GITHUB':
            #get_github_release_date(namespace, name, version, latestVersion)
            pass
        elif repositoryType == 'GEM':
            #get_gem_release_date(namespace, name, version, latestVersion)
            pass
        elif repositoryType == 'CARGO':
            get_cargo_release_date(namespace, name, version, latestVersion)
        elif repositoryType == 'COMPOSER':
            #get_composer_release_date(namespace, name, version, latestVersion)
            pass
        elif repositoryType == 'CPAN':
            #get_cpan_release_date(namespace, name, version, latestVersion)
            pass
        elif repositoryType == 'GO_MODULES':
            get_go_release_date(namespace, name, version, latestVersion)
        elif repositoryType == 'HACKAGE':
            #get_hackage_release_date(namespace, name, version, latestVersion)
            pass
        elif repositoryType == 'NIXPKGS':
            #get_nixpkgs_release_date(namespace, name, version, latestVersion)
            pass
        elif repositoryType == 'PYPI':
            get_pypi_release_date(namespace, name, version, latestVersion)
        elif repositoryType == 'NUGET':
            #get_nuget_release_date(namespace, name, version, latestVersion)
            pass
        elif repositoryType == 'HEX':
            #get_hex_release_date(namespace, name, version, latestVersion)
            pass
    print('Data is ready. Output file: release_dates.csv')

if __name__ == "__main__":
    main()
