import logging
import os
import imp

import ftrack

logging.basicConfig()
logger = logging.getLogger()


def appendPath(path, key, environment):
    """Append *path* to *key* in *environment*."""
    try:
        environment[key] = (
            os.pathsep.join([
                environment[key], path.replace("\\", "/")
            ])
        )
    except KeyError:
        environment[key] = path.replace("\\", "/")

    return environment


def get_module_path(module_name):
    try:
        return imp.find_module(module_name)[1]
    except:
        logger.error("Could not find module \"%s\"" % module_name)
        return ""


def modify_application_launch(event):
    """Modify the application environment and start timer for the task."""

    environment = {}

    app_id = event["data"]["application"]["label"].lower()
    #app_version = event["data"]["application"]["version"]

    # Got Nukex = Nuke
    if app_id == "nukex":
        app_id = "nuke"

    # Special formatting for After Effects
    if app_id.startswith("custom after effects"):
        app_id = "aftereffects"

    # setup PYTHONPATH
    paths = []

    if app_id.startswith("celaction"):
        paths.append(os.path.join(tools_path, "pyblish", "python-qt5"))

    environment["PYTHONPATH"] = paths

    # setup PYBLISHPLUGINPATH
    paths = []

    repo_path = os.path.dirname(get_module_path("pyblish_bumpybox"))
    paths.append(os.path.join(repo_path, "plugins"))
    paths.append(os.path.join(repo_path, "plugins", app_id.split("_")[0]))
    paths.append(os.path.join(repo_path, "plugins", app_id.split("_")[0],
                              "pipeline_specific"))

    # not all apps are task based
    task = None
    try:
        task_id = event["data"]["context"]["selection"][0]["entityId"]
        task = ftrack.Task(task_id)
        paths.append(
            os.path.join(
                repo_path,
                "plugins",
                app_id.split("_")[0],
                task.getType().getName().lower()
            )
        )
    except:
        pass

    repo_path = os.path.dirname(get_module_path("pyblish_ftrack"))
    paths.append(os.path.join(repo_path, "plugins"))

    repo_path = os.path.dirname(get_module_path("pyblish_deadline"))
    paths.append(os.path.join(repo_path, "plugins"))

    environment["PYBLISHPLUGINPATH"] = paths

    # FTRACK_TASKID
    if task and "FTRACK_TASKID" not in event["data"]["options"]["env"]:
        environment["FTRACK_TASKID"] = [task.getId()]

    # HIERO_PLUGIN_PATH environment
    paths = []

    repo_path = os.path.dirname(get_module_path("pyblish_hiero"))
    paths.append(os.path.join(repo_path, "hiero_plugin_path"))

    repo_path = os.path.dirname(get_module_path("pyblish_bumpybox"))
    paths.append(
        os.path.join(
            repo_path, "environment_variables", "hiero_plugin_path"
        )
    )

    environment["HIERO_PLUGIN_PATH"] = paths

    # NUKE_PATH environment
    paths = []

    repo_path = os.path.dirname(get_module_path("pyblish_nuke"))
    paths.append(os.path.join(repo_path, "nuke_path"))

    repo_path = os.path.dirname(get_module_path("pyblish_bumpybox"))
    paths.append(
        os.path.join(
            repo_path, "environment_variables", "nuke_path"
        )
    )

    environment["NUKE_PATH"] = paths

    # HOUDINI_PATH environment
    paths = []

    repo_path = os.path.dirname(get_module_path("pyblish_houdini"))
    paths.append(os.path.join(repo_path, "pyblish_houdini", "houdini_path"))

    repo_path = os.path.dirname(get_module_path("pyblish_bumpybox"))
    paths.append(os.path.join(repo_path, "pyblish_bumpybox",
                              "environment_variables", "houdini_path"))

    paths.append("&")

    environment["HOUDINI_PATH"] = paths

    # adding variables
    data = event["data"]
    for variable in environment:
        for path in environment[variable]:
            appendPath(path, variable, data["options"]["env"])

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


if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)

    ftrack.setup()

    ftrack.EVENT_HUB.subscribe(
        "topic=ftrack.connect.application.launch",
        modify_application_launch
    )
    ftrack.EVENT_HUB.wait()
