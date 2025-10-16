## SteelSeriesGG Helper

I run into an issue with SteelSeries GG (specifically the Sonar app) every so often where the Chat, Gaming, and Mic devices aren't set correctly. I can only assume it is due to the headset dongle not being loaded yet when the computer wakes from sleep, and Sonar refreshes upon wake and can't find the devices.

When this happens, the fix is to manually select the devices, or usually a "Automatically select defaults" button appears which sets them to the sane default of the Arctic Nova 7 headset.

This script will just run continuously monitoring for a situation where Sonar doesn't appear to have the devices correct.

It also monitors the Windows Audio service (which occasionally crashes when Sonar is in the above-mentioned broken state), and will restart it. This is built into Windows, but it will take a minute. This script will restart within a max of `SLEEP_DURATION` seconds.

### Configuration

Open the script and edit the variables near the top:

* `HEADSET_DEVICE_NAME` (default: `"(Arctis Nova 7)"`) - This should match the end of the non-Sonar device names for the [headset](output.png) and [mic](input.png)

* `SLEEP_DURATION` (default: `10`) - This is how often you want to query Sonar and the Windows Audio service

* `COREPROPS_FILE` (default: `"C:/ProgramData/SteelSeries/SteelSeries Engine 3/coreProps.json"`) - location of SteelSeries GG's coreprops.json file (you likely won't need to change this except for maybe the drive letter)

### Run
```
pip install -r requirements.txt
python main.py
```

It will continue to run indefinitely.

### Future

At some point, this will likely either be made into a legitimate Python module, or I might just write it in another language and have it be invisible/minimize to the notification area ("systray").