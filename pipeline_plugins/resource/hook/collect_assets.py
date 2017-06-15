import logging
import os
import sys
import getpass
import re
import shutil
import traceback
import threading
from hook_utils import get_components

logging.basicConfig()
logger = logging.getLogger()

if __name__ == "__main__":
    tools_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.append(os.path.join(tools_path, "ftrack", "ftrack-api"))

import ftrack


def version_get(string, prefix, suffix=None):
    """Extract version information from filenames.
        Code from Foundry"s nukescripts.version_get()
    """

    if string is None:
        raise ValueError("Empty version string - no match")

    regex = "[/_.]"+prefix+"\d+"
    matches = re.findall(regex, string, re.IGNORECASE)
    if not len(matches):
        msg = "No \"_"+prefix+"#\" found in \""+string+"\""
        raise ValueError(msg)
    return matches[-1:][0][1], re.search("\d+", matches[-1:][0]).group()


def async(fn):
    """Run *fn* asynchronously."""
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()
    return wrapper


def format_basename(src_file, formatting):
    basename = os.path.basename(src_file)

    if formatting == "strip_version":
        version_string = ".v" + version_get(src_file, "v")[1]
        basename = basename.replace(version_string, "")
    elif formatting == "strip_filename":
        _, basename = os.path.splitext(src_file)
        basename = basename[1:]

    return basename

@async
def create_job(event):
    user_id = event["source"]["user"]["id"]
    ftrack_user = ftrack.User(id=user_id)

    job = ftrack.createJob("Collecting Assets", "queued", ftrack_user)
    job.setStatus("running")
    values = event["data"]["values"]
    errors = ""

    # collecting sources and destinations
    for item in event["data"]["selection"]:
        try:
            entity = ftrack.AssetVersion(item["entityId"])

            # adding path to errors
            parent_path = ""
            parents = entity.getParents()
            parents.reverse()
            for p in parents:
                parent_path += p.getName() + "/"

            parent_number = int(values["parent_number"])
            parent_prefix = ""
            for p in reversed(list(reversed(parents))[:parent_number]):
                parent_prefix += p.getName() + "."

            src = values["component"]

            # copying sources to destinations
            if entity.getAsset().getType().getShort() == "img":
                dir_name = entity.getParent().getParent().getName()
                if parent_prefix:
                    dir_name = parent_prefix

                asset_dir = os.path.join(values["collection_directory"], dir_name)

                if os.path.exists(asset_dir):
                    # delete existing files
                    shutil.rmtree(asset_dir)

                os.makedirs(asset_dir)

                for f in os.listdir(os.path.dirname(src)):
                    path = os.path.join(os.path.dirname(src), f)

                    basename = format_basename(src, values["file_formatting"])

                    basename = parent_prefix + re.sub(r".%04d", "", basename)
                    dst = os.path.join(asset_dir, basename)

                    shutil.copy(path, dst)
            else:
                basename = format_basename(src, values['file_formatting'])
                basename = parent_prefix + basename

                dst = os.path.join(values["collection_directory"], basename)

                shutil.copy(src, dst)
        except:
            errors += parent_path + "\n"
            errors += traceback.format_exc() + "\n"

    # generate error report
    if errors:
        temp_txt = os.path.join(values["collection_directory"], "errors.txt")
        f = open(temp_txt, "w")
        f.write(errors)
        f.close()

    job.setStatus("done")


def launch(event):

    if "values" in event["data"]:
        values = event["data"]["values"]

        # failures
        if "collection_directory" not in values or "file_formatting" not in values:
            return {
                "success": False,
                "message": "Missing submit information."
            }

        if not os.path.exists(values["collection_directory"]):
            return {
                "success": False,
                "message": "Collection Directory does not exist."
            }

        create_job(event)

        msg = "Collecting assets job created."
        return {
            "success": True,
            "message": msg
        }

    return {
        "items": [
            {
                "label": "Component to collect",
                "type": "enumerator",
                "name": "component",
                "data": get_components(event, asset_types=['img', 'mov'])
            },
            {
                "label": "Output Directory",
                "type": "text",
                "value": "",
                "name": "collection_directory"
            },
            {
                "label": "Filename Formatting",
                "type": "enumerator",
                "name": "file_formatting",
                "data": [
                    {
                        "label": "Original Filename",
                        "value": "original_filename"
                    },
                    {
                        "label": "Strip Version",
                        "value": "strip_version"
                    },
                    {
                        "label": "Strip Filename",
                        "value": "strip_filename"
                    }
                ],
                "value": "original_filename"
            },
            {
                "label": "Parents (-1 = all parents)",
                "type": "number",
                "name": "parent_number",
                "value": 0
            }
        ]
    }


def discover(event):

    data = event["data"]

    for item in data["selection"]:
        if item["entityType"] != "assetversion":
            return

    return {
        "items": [{
            "label": "Collect Assets",
            "actionIdentifier": "collect_assets"
        }]
    }


def register(registry, **kw):
    """Register location plugin."""

    # Validate that registry is the correct ftrack.Registry. If not,
    # assume that register is being called with another purpose or from a
    # new or incompatible API and return without doing anything.
    if registry is not ftrack.EVENT_HANDLERS:
        # Exit to avoid registering this plugin again.
        return

    """Register action."""
    ftrack.EVENT_HUB.subscribe(
        "topic=ftrack.action.discover and source.user.username={0}".format(
            getpass.getuser()
        ),
        discover
    )

    ftrack.EVENT_HUB.subscribe(
        "topic=ftrack.action.launch and source.user.username={0} "
        "and data.actionIdentifier={1}".format(
            getpass.getuser(), "collect_assets"),
        launch
        )

if __name__ == "__main__":
    logger.setLevel(logging.INFO)

    ftrack.setup()

    """Register action."""
    ftrack.EVENT_HUB.subscribe(
        "topic=ftrack.action.discover and source.user.username={0}".format(
            getpass.getuser()
        ),
        discover
    )

    ftrack.EVENT_HUB.subscribe(
        "topic=ftrack.action.launch and source.user.username={0} "
        "and data.actionIdentifier={1}".format(
            getpass.getuser(), "collect_assets"),
        launch
        )

    ftrack.EVENT_HUB.wait()
