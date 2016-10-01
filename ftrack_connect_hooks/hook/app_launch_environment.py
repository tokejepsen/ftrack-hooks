import logging
import os
import ftrack

logging.basicConfig()
logger = logging.getLogger()


def appendPath(path, key, environment):
    """Append *path* to *key* in *environment*."""
    try:
        environment[key] = (
            os.pathsep.join([
                environment[key], path
            ])
        )
    except KeyError:
        environment[key] = path

    return environment


def modify_application_launch(event):
    """Modify the application environment and start timer for the task."""

    environment = {}

    func = os.path.dirname
    tools_path = func(func(func(func(func(__file__)))))
    maya_path = os.path.join(tools_path, "maya")
    nuke_path = os.path.join(tools_path, "nuke")
    pyblish_path = os.path.join(tools_path, "pyblish")
    app_id = event["data"]["application"]["label"].lower()
    app_version = event["data"]["application"]["version"]

    # got no special nukex plugins, so nukex = nuke
    if app_id == "nukex":
        app_id = "nuke"

    # special formatting for After Effects
    if app_id.startswith("custom after effects"):
        app_id = "aftereffects"

    # get arnold version
    arnold_version = ""
    try:
        dirs = os.listdir(os.path.join(maya_path, "arnold"))
        dirs.sort()
        arnold_version = dirs[-1]
    except:
        pass

    # setup PYTHONPATH
    paths = []
    paths.append(os.path.join(tools_path, "ftrack", "ftrack-api"))
    paths.append(os.path.join(tools_path, "ftrack", "ftrack-tools"))

    paths.append(os.path.join(tools_path, "pyblish", "pyblish-base"))
    paths.append(os.path.join(tools_path, "pyblish", "pyblish-hiero"))
    paths.append(os.path.join(tools_path, "pyblish", "pyblish-houdini"))
    paths.append(os.path.join(tools_path, "pyblish", "pyblish-maya"))
    paths.append(os.path.join(tools_path, "pyblish", "pyblish-nuke"))
    paths.append(os.path.join(tools_path, "pyblish", "pyblish-lite"))
    paths.append(os.path.join(tools_path, "pyblish", "pyblish-standalone"))
    paths.append(os.path.join(tools_path, "pyblish", "pyblish-maya",
                              "pyblish_maya", "pythonpath"))
    paths.append(os.path.join(tools_path, "pyblish", "pyblish-bumpybox"))
    paths.append(os.path.join(tools_path, "pyblish", "pyblish-deadline"))
    paths.append(os.path.join(tools_path, "pyblish", "pyblish-bumpybox",
                              "pyblish_bumpybox", "environment_variables",
                              "pythonpath"))

    paths.append(os.path.join(tools_path, "lucidity", "source"))
    paths.append(os.path.join(tools_path, "pipeline-schema"))

    paths.append(os.path.join(maya_path, "scripts"))
    paths.append(maya_path)
    paths.append(os.path.join(maya_path, "Tapp", "System"))

    if app_id.startswith("celaction"):
        paths.append(os.path.join(tools_path, "pyblish", "python-qt5"))

    environment["PYTHONPATH"] = paths

    # setup MAYA_SCRIPT_PATH
    environment["MAYA_SCRIPT_PATH"] = [os.path.join(maya_path, "scripts")]

    # setup XBMLANGPATH
    environment["XBMLANGPATH"] = [os.path.join(maya_path, "icons")]

    # setup MAYA_PRESET_PATH
    environment["MAYA_PRESET_PATH"] = [os.path.join(maya_path, "presets")]

    # setup PYBLISHPLUGINPATH
    paths = []
    paths.append(os.path.join(tools_path, "pyblish", "pyblish-ftrack",
                              "pyblish_ftrack", "plugins"))
    paths.append(os.path.join(pyblish_path, "pyblish-deadline",
                              "pyblish_deadline", "plugins"))

    paths.append(os.path.join(tools_path, "pyblish", "pyblish-bumpybox",
                              "pyblish_bumpybox", "plugins"))
    paths.append(os.path.join(pyblish_path, "pyblish-bumpybox",
                              "pyblish_bumpybox", "plugins",
                              app_id.split("_")[0]))
    paths.append(os.path.join(pyblish_path, "pyblish-bumpybox",
                              "pyblish_bumpybox", "plugins",
                              app_id.split("_")[0], "pipeline_specific"))

    import pyblish_bumpybox
    repo_path = os.path.dirname(pyblish_bumpybox.__file__)
    paths.append(os.path.join(repo_path, "plugins"))
    paths.append(os.path.join(repo_path, "plugins", app_id.split("_")[0]))
    paths.append(os.path.join(repo_path, "plugins", app_id.split("_")[0],
                              "pipeline_specific"))

    import pyblish_ftrack
    repo_path = os.path.dirname(pyblish_ftrack.__file__)
    paths.append(os.path.join(repo_path, "plugins"))

    import pyblish_deadline
    repo_path = os.path.dirname(pyblish_deadline.__file__)
    paths.append(os.path.join(repo_path, "plugins"))

    # not all apps are task based
    try:
        task_id = event["data"]["context"]["selection"][0]["entityId"]
        task = ftrack.Task(task_id)
        paths.append(os.path.join(pyblish_path, "pyblish-bumpybox",
                                  "pyblish_bumpybox", "plugins",
                                  app_id.split("_")[0],
                                  task.getType().getName().lower()))
    except:
        pass

    environment["PYBLISHPLUGINPATH"] = paths

    # setup PATH
    paths = [os.path.join(tools_path, "ffmpeg", "bin")]
    paths.append(os.path.join(maya_path, "arnold", arnold_version, app_version,
                              "bin"))

    environment["PATH"] = paths

    # MAYA_MODULE_PATH
    paths = [os.path.join(maya_path, "arnold", arnold_version, app_version)]

    environment["MAYA_MODULE_PATH"] = paths

    # MAYA_RENDER_DESC_PATH
    paths = [os.path.join(maya_path, "arnold", arnold_version, app_version)]

    environment["MAYA_RENDER_DESC_PATH"] = paths

    # MAYA_PLUG_IN_PATH
    paths = [os.path.join(maya_path, "plugins", app_version)]

    environment["MAYA_PLUG_IN_PATH"] = paths

    # HIERO_PLUGIN_PATH environment
    paths = []

    paths.append(os.path.join(tools_path, "ftrack", "ftrack-tools", "hiero"))

    paths.append(os.path.join(tools_path, "pyblish", "pyblish-hiero",
                              "pyblish_hiero", "hiero_plugin_path"))
    paths.append(os.path.join(tools_path, "pyblish", "pyblish-bumpybox",
                              "pyblish_bumpybox", "environment_variables",
                              "hiero_plugin_path"))

    paths.append(os.path.join(tools_path, "hiero"))

    environment["HIERO_PLUGIN_PATH"] = paths

    # NUKE_PATH environment
    paths = []

    paths.append(os.path.join(tools_path, "ftrack", "ftrack-tools"))

    paths.append(os.path.join(tools_path, "pyblish", "pyblish-nuke",
                              "pyblish_nuke", "nuke_path"))

    paths.append(os.path.join(tools_path, "pyblish", "pyblish-bumpybox",
                              "pyblish_bumpybox", "environment_variables",
                              "nuke_path"))

    paths.append(nuke_path)
    paths.append(os.path.join(nuke_path, "gizmos"))

    environment["NUKE_PATH"] = paths

    # HOUDINI_PATH environment
    paths = [os.path.join(pyblish_path, "pyblish-houdini", "pyblish_houdini",
                          "houdini_path")]
    paths.append(os.path.join(pyblish_path, "pyblish-bumpybox",
                              "pyblish_bumpybox", "environment_variables",
                              "houdini_path"))
    paths.append("&")

    environment["HOUDINI_PATH"] = paths

    # RV_SUPPORT_PATH environment
    paths = [os.path.join(tools_path, "rv", "custom")]

    environment["RV_SUPPORT_PATH"] = paths

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
        modify_application_launch)
    ftrack.EVENT_HUB.wait()
