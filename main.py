import json
import os
import sys
import time
from datetime import datetime

import psutil
import requests

# set this to match the end of the non-Sonar device names for both the headset and mic
HEADSET_DEVICE_NAME = "(Arctis Nova 7)"

# set this to how often you want to query Sonar and the Windows Audio service
SLEEP_DURATION = 10

# location of SteelSeries GG's coreprops.json file (likely won't need to change except for maybe the drive letter)
COREPROPS_FILE = "C:/ProgramData/SteelSeries/SteelSeries Engine 3/coreProps.json"

# disable ignored-ssl-cert warning since all of these API servers will have invalid localhost certs
requests.packages.urllib3.disable_warnings(  # pylint: disable=no-member
    requests.packages.urllib3.exceptions.InsecureRequestWarning  # pylint: disable=no-member
)


def timestamp():
    return datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")


def get_coreprops():
    # {"encryptedAddress":"127.0.0.1:61956","ggEncryptedAddress":"127.0.0.1:6327","address":"127.0.0.1:61950"}
    with open(COREPROPS_FILE, encoding="utf-8") as f:
        return json.load(f)


# get "encryptedAddress" or "address" field URLs from coreprops file
def get_core_address(https=False):
    j = get_coreprops()
    if https:
        return "https://" + j["encryptedAddress"]
    return "http://" + j["address"]


# get "ggEncryptedAddress" field URL from coreprops file
def get_gg_address():
    j = get_coreprops()
    return "https://" + j["ggEncryptedAddress"]


# query ggEncryptedAddress URL for list of subApps then return URL for a given subApp
def get_gg_subapps(subapp):
    # https://127.0.0.1:1234/subApps
    # {"subApps": {
    #    "engine":{"name":"engine","isEnabled":true,"isReady":true,"isRunning":true,"exitCode":0,"shouldAutoStart":true,
    #              "isWindowsSupported":true,"isMacSupported":true,"toggleViaSettings":false,"isBrowserViewSupported":false,
    #              "metadata":{"encryptedWebServerAddress":"127.0.0.1:63592","webServerAddress":"","offlineFrontendAddress":"",
    #              "onlineFrontendAddress":""},"secretMetadata":{"encryptedWebServerAddressCertText":"pemcert\n"}},
    #    "sonar":{"name":"sonar","isEnabled":true,"isReady":true,"isRunning":true,"exitCode":0,"shouldAutoStart":true,
    #              "isWindowsSupported":true,"isMacSupported":false,"toggleViaSettings":true,"isBrowserViewSupported":false,
    #              "metadata":{"encryptedWebServerAddress":"","webServerAddress":"http://127.0.0.1:63676",
    #              "offlineFrontendAddress":"","onlineFrontendAddress":""},"secretMetadata":{"encryptedWebServerAddressCertText":""}},
    #    "threeDAT":{"name":"threeDAT","isEnabled":true,"isReady":false,"isRunning":false,"exitCode":0,"shouldAutoStart":false,
    #              "isWindowsSupported":true,"isMacSupported":false,"toggleViaSettings":false,"isBrowserViewSupported":true,
    #              "metadata":{"encryptedWebServerAddress":"","webServerAddress":"",
    #              "offlineFrontendAddress":"file://C:\\Program Files\\SteelSeries\\GG\\apps\\threeDAT\\frontend\\offline\\index.html",
    #              "onlineFrontendAddress":""},"secretMetadata":{"encryptedWebServerAddressCertText":""}}
    # }}

    # search each app for the key following keys: webServerAddress, encryptedWebServerAddress, and offlineFrontendAddress
    # "webServerAddress":"http://127.0.0.1:1234"
    # "encryptedWebServerAddress":"127.0.0.1:12345"
    # "offlineFrontendAddress":"file://C:\\Program Files\\SteelSeries\\GG\\apps\\threeDAT

    baseurl = get_gg_address()
    url = baseurl + "/subApps"
    r = requests.get(url=url, timeout=10, verify=False)
    try:
        j = r.json()
    except json.decoder.JSONDecodeError:
        j = {}
    subapp_metadata = j.get("subApps", {}).get(subapp, {}).get("metadata", {})
    v = subapp_metadata.get("webServerAddress")
    if v:
        return v
    v = subapp_metadata.get("encryptedWebServerAddress")
    if v:
        return "https://" + v
    v = subapp_metadata.get("offlineFrontendAddress")
    if v:
        return v

    return ""


# simple wrapper to get JSON response from a URL (passing no data)
def call_endpoint(baseurl, endpoint, method="GET"):
    # some sonar endpoints that might be useful to someone
    # docs: https://github.com/wex/sonar-rev/tree/main/initializing
    # docs: https://github.com/wex/sonar-rev/tree/main/volumeSettings
    # /volumeSettings/classic
    # /volumeSettings/streamer

    # this is the same as clicking "automatically set defaults" in sonar tab if devices aren't set right
    # curl -v -X PUT http://127.0.0.1:sonarport/onboarding/configure

    if endpoint[0] != "/":
        endpoint = "/" + endpoint
    url = baseurl + endpoint
    # print(f"{timestamp()} Calling URL: {method} {url}")
    r = requests.request(method=method, url=url, timeout=10)
    try:
        return r.json()
    except json.decoder.JSONDecodeError:
        return {}


# check sonar status and reset if needed
def reset_sonar():
    # have we found all the sonar devices?
    found_sonar_multimedia = False
    found_sonar_communications = False
    found_sonar_mic = False
    # have we found all the actual devices?
    found_headphones = False
    found_mic = False

    baseurl = get_gg_subapps("sonar")

    # can't load sonar URL
    if not baseurl:
        return

    for device in call_endpoint(baseurl, "/audioDevices"):
        # check to see if the 3 sonar devices exist and are correct
        # { 'channels': 8, 'dataFlow': 'render', 'defaultRole': 'multimedia', 'fwUpdateRequired': False,
        #   'id': '{0.0.0.00000000}.{80dbbe15-b2eb-4691-bd43-12bdd1880854}', 'role': 'game', 'state': 'active',
        #   'friendlyName': 'SteelSeries Sonar - Gaming (SteelSeries Sonar Virtual Audio Device)'},
        # { 'channels': 2, 'dataFlow': 'render', 'defaultRole': 'communications', 'fwUpdateRequired': False,
        #   'id': '{0.0.0.00000000}.{c4e360c1-438f-441c-a6e4-096c72aa4404}', 'role': 'chatRender', 'state': 'active',
        #   'friendlyName': 'SteelSeries Sonar - Chat (SteelSeries Sonar Virtual Audio Device)'},
        # { 'channels': 2, 'dataFlow': 'capture', 'defaultRole': 'all', 'fwUpdateRequired': False,
        #   'id': '{0.0.1.00000000}.{6340657d-f6e3-4792-9a27-ba2964e92bbe}', 'role': 'chatCapture', 'state': 'active',
        #   'friendlyName': 'SteelSeries Sonar - Microphone (SteelSeries Sonar Virtual Audio Device)'}
        if (
            device.get("defaultRole", "") == "multimedia"
            and device.get("dataFlow", "") == "render"
            and device.get("friendlyName", "").startswith("SteelSeries Sonar - Gaming")
        ):
            found_sonar_multimedia = True
        elif (
            device.get("defaultRole", "") == "communications"
            and device.get("dataFlow", "") == "render"
            and device.get("friendlyName", "").startswith("SteelSeries Sonar - Chat")
        ):
            found_sonar_communications = True
        elif (
            device.get("defaultRole", "") == "all"
            and device.get("dataFlow", "") == "capture"
            and device.get("friendlyName", "").startswith(
                "SteelSeries Sonar - Microphone"
            )
        ):
            found_sonar_mic = True

        # check to see if the actual headset devices exist
        # { 'channels': 2, 'dataFlow': 'render', 'defaultRole': 'console', 'fwUpdateRequired': False,
        #   'id': '{0.0.0.00000000}.{41c2c31b-a17f-4366-83b6-11d5989a8556}', 'role': 'none', 'state': 'active',
        #   'friendlyName': 'SteelSeries Arctis Nova 7 (Arctis Nova 7)'},
        # { 'channels': 1, 'dataFlow': 'capture', 'defaultRole': 'console', 'fwUpdateRequired': False,
        #   'id': '{0.0.1.00000000}.{49c6b3f8-3e66-48aa-a89f-f87d6434587a}', 'role': 'none', 'state': 'active',
        #   'friendlyName': 'SteelSeries Arctis Nova 7 (Arctis Nova 7)'},
        elif (
            device.get("defaultRole", "") == "console"
            and device.get("dataFlow", "") == "render"
            and device.get("friendlyName", "").endswith(HEADSET_DEVICE_NAME)
        ):
            found_headphones = True
        elif (
            device.get("defaultRole", "") == "console"
            and device.get("dataFlow", "") == "capture"
            and device.get("friendlyName", "").endswith(HEADSET_DEVICE_NAME)
        ):
            found_mic = True

    # if actual devices weren't found, don't do anything. might need to re-plug dongle or
    # Windows Audio service crashed (which the service checker in the main loop will handle)
    if not found_mic or not found_headphones:
        print(f"{timestamp()} Missing at least 1 headphone device.")
        print(
            f"{timestamp()} Active devices: Headphones/Output({found_headphones}) Mic/Input({found_mic})"
        )
        return

    # if one of the sonar devices isn't set up, reset sonar
    if (
        not found_sonar_multimedia
        or not found_sonar_communications
        or not found_sonar_mic
    ):
        print(f"{timestamp()} At least 1 inactive Sonar device found.")
        print(
            f"{timestamp()} Active Sonar devices: "
            f"Game({found_sonar_multimedia}) Chat({found_sonar_communications}) Mic({found_sonar_mic})"
        )
        print(f"{timestamp()} Resetting sonar")
        call_endpoint(baseurl, "/onboarding/configure", method="put")
        return

    # everything should have been taken care of above, but if not, and one of the
    # "classic" (?) redirections is not enabled, reset sonar
    for redir in call_endpoint(baseurl, "/classicRedirections"):
        # { 'deviceId': '{0.0.0.00000000}.{41c2c31b-a17f-4366-83b6-11d5989a8556}', 'id': 'chat', 'isRunning': True},
        if not redir.get("isRunning"):
            print(
                f"{timestamp()} Inactive classic redirection found: {redir.get('deviceId', '?')}"
            )
            print(f"{timestamp()} Resetting sonar")
            call_endpoint(baseurl, "/onboarding/configure", method="put")
            return

    # don't worry about these for now
    # call_endpoint(baseurl, '/streamRedirections')


# get Windows service info
def get_service(name):
    try:
        return psutil.win_service_get(name)
    except psutil.Error:
        return None


# if script isn't run as admin, then this will do nothing.
# the service IS set to automatically restart on its own, but it takes 1 minute
def restart_service(name):
    os.system(f'net start "{name}"')


# main loop
def main():
    print(f"{timestamp()} Startup")
    print(f'{timestamp()} Headset name: "{HEADSET_DEVICE_NAME}"')
    print(f"{timestamp()} Check frequency: {SLEEP_DURATION} seconds")
    print(f'{timestamp()} coreProps.json location: "{COREPROPS_FILE}"')
    while True:
        # wait
        time.sleep(SLEEP_DURATION)

        # check audio service status
        audiosrv = get_service("audiosrv")
        if not audiosrv:  # shouldn't happen. this means service doesn't exist. fail?
            print(f"{timestamp()} AudioSrv service not found, exiting")
            sys.exit(1)
        # if service isn't running, restart it and wait again
        if audiosrv.status() not in ["running"]:
            print(f"{timestamp()} AudioSrv service not running, restarting")
            restart_service("audiosrv")
            restart_service("RtkAudioUniversalService")
            time.sleep(1)

        # if audio service is running, check the sonar configuration
        reset_sonar()


if __name__ == "__main__":
    sys.exit(main())
