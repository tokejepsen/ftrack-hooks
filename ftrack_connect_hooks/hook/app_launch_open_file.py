import os
import re
import shutil
import tempfile

import ftrack
import ftrack_api
import ftrack_template


def version_get(string, prefix, suffix=None):
    """ Extract version information from filenames.
    Code from Foundry"s nukescripts.version_get()
    """

    if string is None:
        raise ValueError("Empty version string - no match")

    regex = "." + prefix + "\d+"
    matches = re.findall(regex, string, re.IGNORECASE)
    if not len(matches):
        msg = "No " + prefix + " found in \"" + string + "\""
        raise ValueError(msg)
    return (matches[-1:][0][1], re.search("\d+", matches[-1:][0]).group())


def get_task_data(event):

    data = event["data"]
    app_id = event["data"]["application"]["identifier"].split("_")[0]

    session = ftrack_api.Session()
    task = session.get("Task", data["context"]["selection"][0]["entityId"])

    if app_id == "nukex":
        app_id = "nuke"

    templates = ftrack_template.discover_templates()
    work_file, template = ftrack_template.format(
        {app_id: app_id, "padded_version": "001"}, templates, entity=task
    )
    work_area = os.path.dirname(work_file)

    # DJV View
    if app_id == "djvview":
        return get_djv_data(event)

    # Check to see if the expected work file is a file template.
    if not template.isfile:
        raise ValueError("Could not find an expected work file.")

    # Finding existing work files
    if os.path.exists(work_area):
        max_version = 0
        for f in os.listdir(work_area):
            try:
                version = version_get(f, "v")[1]
                if version > max_version:
                    max_version = version
                    work_file = os.path.join(work_area, f)
            except:
                pass

    # Searching old Bait structure for work files
    if not os.path.exists(work_file) and os.path.exists(work_area):
        max_version = 0
        for f in os.listdir(os.path.dirname(work_area)):
            try:
                version = version_get(f, "v")[1]
                if version > max_version:
                    max_version = version
                    work_file = os.path.join(os.path.dirname(work_area), f)
            except:
                pass

    # If no work file exists, copy a default work file
    if not os.path.exists(work_file):

        if not os.path.exists(os.path.dirname(work_file)):
            os.makedirs(os.path.dirname(work_file))

        shutil.copy(template.source, work_file)
    else:  # If work file exists check to see if it needs to be versioned up
        old_api_task = ftrack.Task(data["context"]["selection"][0]["entityId"])
        asset = old_api_task.getParent().createAsset(
            old_api_task.getName(),
            "scene",
            task=old_api_task
        )

        version = 1
        versions = asset.getVersions()
        if versions:
            version = versions[-1].getVersion()

        if version > int(version_get(work_file, "v")[1]):

            new_work_file = ftrack_template.format(
                {app_id: app_id, "padded_version": str(version).zfill(3)},
                templates,
                entity=task
            )[0]

            shutil.copy(work_file, new_work_file)
            work_file = new_work_file

    data["command"].append(work_file)
    return data


def get_djv_data(event):

    # Collect all files to be viewed
    files = []
    component_ids = event["data"]["context"]["values"]["components"].split(",")
    for component_id in component_ids:
        component = ftrack.Component(component_id)
        file_path = component.getFilesystemPath()

        if component.isSequence():
            for member in component.getMembers():
                files.append(file_path % int(member.getName()))
        else:
            files.append(file_path)

    files.sort()

    # Append launch file to command
    file_path = ""
    if len(files) == 1:
        file_path = files[0]
    else:
        data = ""
        for f in files:
            data += f + "\n"

        file_path = os.path.join(tempfile.gettempdir(), "djvview.ifl")
        with open(file_path, "w") as f:
            f.write(data)

    data = event["data"]
    data["command"].append(file_path)

    # Get playback speed from last component in list
    fps = component.getVersion().getAsset().getParent().get("fps")
    valid_fps = [
        "1", "3", "6", "12", "15", "16", "18", "23.976", "24", "25", "29.97",
        "30", "50", "59.94", "60", "120"
    ]
    if str(fps) in valid_fps:
        data["command"].extend(["-playback_speed", str(fps)])
    if str(int(fps)) in valid_fps:
        data["command"].extend(["-playback_speed", str(int(fps))])

    return data


def get_assetversion_data(event):

    app_id = event["data"]["application"]["identifier"].split("_")[0]
    data = event["data"]

    if app_id == "djvview":
        data = get_djv_data(event)

    return data


def modify_application_launch(event):
    """Modify the application launch command with potential files to open"""

    data = event["data"]
    selection = event["data"]["context"]["selection"]

    if not selection:
        return

    entityType = selection[0]["entityType"]

    # task based actions
    if entityType == "task":
        data = get_task_data(event)

    # assetversion based actions
    if entityType == "assetversion":
        data = get_assetversion_data(event)

    return data


def register(registry, **kw):
    """Register location plugin."""

    # Validate that registry is the correct ftrack.Registry. If not,
    # assume that register is being called with another purpose or from a
    # new or incompatible API and return without doing anything.
    if registry is not ftrack.EVENT_HANDLERS:
        # Exit to avoid registering this plugin again.
        return

    ftrack.EVENT_HUB.subscribe(
        "topic=ftrack.connect.application.launch",
        modify_application_launch
    )
