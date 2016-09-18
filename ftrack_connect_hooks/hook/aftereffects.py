# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

import getpass
import sys
import pprint
import logging
import os

import ftrack
import ftrack_connect.application


class AfterEffectsAction(object):
    """Discover and launch nuke."""

    identifier = "ftrack-connect-launch-aftereffects"

    def __init__(self, application_store, launcher):
        """Initialise action with *applicationStore* and *launcher*.

        *applicationStore* should be an instance of
        :class:`ftrack_connect.application.ApplicationStore`.

        *launcher* should be an instance of
        :class:`ftrack_connect.application.ApplicationLauncher`.

        """
        super(AfterEffectsAction, self).__init__()

        self.logger = logging.getLogger(
            __name__ + "." + self.__class__.__name__
        )

        self.application_store = application_store
        self.launcher = launcher

    def is_valid_selection(self, selection):
        """Return true if the selection is valid."""
        if (
            len(selection) != 1 or
            selection[0]["entityType"] != "task"
        ):
            return False

        entity = selection[0]
        task = ftrack.Task(entity["entityId"])

        if task.getObjectType() != "Task":
            return False

        return True

    def register(self):
        """Register discover actions on logged in user."""
        ftrack.EVENT_HUB.subscribe(
            "topic=ftrack.action.discover and source.user.username={0}".format(
                getpass.getuser()
            ),
            self.discover
        )

        ftrack.EVENT_HUB.subscribe(
            "topic=ftrack.action.launch and source.user.username={0} "
            "and data.actionIdentifier={1}".format(
                getpass.getuser(), self.identifier
            ),
            self.launch
        )

    def discover(self, event):
        """Return discovered applications."""
        """
        if not self.is_valid_selection(
            event["data"].get("selection", [])
        ):
            return
        """
        items = []
        applications = self.application_store.applications
        applications = sorted(
            applications, key=lambda application: application["label"]
        )

        for application in applications:
            application_identifier = application["identifier"]
            label = application["label"]
            items.append({
                "actionIdentifier": self.identifier,
                "label": label,
                "icon": application.get("icon", "default"),
                "applicationIdentifier": application_identifier
            })

        return {
            "items": items
        }

    def launch(self, event):
        """Callback method for After Effects action."""
        applicationIdentifier = (
            event["data"]["applicationIdentifier"]
        )

        context = event["data"].copy()

        applicationIdentifier = event["data"]["applicationIdentifier"]
        context = event["data"].copy()
        context["source"] = event["source"]

        # update publishing script
        script_paths = []
        root = os.path.join(os.path.expanduser("~"), "AppData",
                            "Roaming", "Adobe", "After Effects")
        for version in os.listdir(root):
            path = os.path.join(root, version, "Scripts")

            if not os.path.exists(path):
                os.makedirs(path)

            script_paths.append(os.path.join(path, "Publish.jsx"))

        src = os.path.join(os.path.dirname(__file__), "Publish.jsx")

        func = os.path.dirname
        tools_path = func(func(func(func(func(__file__)))))

        data = ""
        with open(src, "r") as f:
            for line in f.readlines():
                if "pyblish_path" in line:
                    pyblish_path = os.path.join(tools_path, "pyblish"
                                                "pyblish-standalone.bat")
                    pyblish_path = pyblish_path.replace("\\", "/")
                    data += line.format(pyblish_path=pyblish_path)
                else:
                    data += line

        for dst in script_paths:
            with open(dst, "w") as f:
                f.write(data)

        return self.launcher.launch(applicationIdentifier, context)


class ApplicationStore(ftrack_connect.application.ApplicationStore):

    def _modifyApplications(self, path=""):
        self.applications = self._discoverApplications(path=path)

    def _discoverApplications(self, path=""):
        """Return a list of applications that can be launched from this host.

        An application should be of the form:

            dict(
                "identifier": "name_version",
                "label": "Name version",
                "path": "Absolute path to the file",
                "version": "Version of the application",
                "icon": "URL or name of predefined icon"
            )

        """
        applications = []
        launchArguments = ["-m"]
        if path:
            launchArguments.append(path)

        if sys.platform == "win32":
            prefix = ["C:\\", "Program Files.*"]
            icon = "https://i1.ytimg.com/sh/SyDMRF-sTyE/showposter.jpg?"
            icon += "v=52091ea7"

            # Add After Effects as a separate application
            applications.extend(self._searchFilesystem(
                expression=prefix + ["Adobe", "Adobe After Effects *",
                                     "Support Files", "AfterFX.exe"],
                label="Custom After Effects {version}",
                applicationIdentifier="aftereffects_{version}",
                icon=icon,
                launchArguments=launchArguments
            ))

        self.logger.info(
            "Discovered applications:\n{0}".format(
                pprint.pformat(applications)
            )
        )

        return applications


def register(registry, **kw):
    """Register hooks."""

    # Validate that registry is the correct ftrack.Registry. If not,
    # assume that register is being called with another purpose or from a
    # new or incompatible API and return without doing anything.
    if registry is not ftrack.EVENT_HANDLERS:
        # Exit to avoid registering this plugin again.
        return

    # Create store containing applications.
    applicationStore = ApplicationStore()

    # Create a launcher with the store containing applications.
    launcher = ftrack_connect.application.ApplicationLauncher(
        applicationStore
    )

    # Create action and register to respond to discover and launch actions.
    action = AfterEffectsAction(applicationStore, launcher)
    action.register()


if __name__ == "__main__":
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)

    os.environ["LOGNAME"] = "toke.jepsen"

    # Create store containing applications.
    applicationStore = ApplicationStore()

    # Create a launcher with the store containing applications.
    launcher = ftrack_connect.application.ApplicationLauncher(
        applicationStore
    )

    # Create action and register to respond to discover and launch actions.
    ftrack.setup()
    action = AfterEffectsAction(applicationStore, launcher)
    action.register()

    # dependent event listeners
    import app_launch_open_file
    import app_launch_environment

    ftrack.EVENT_HUB.subscribe(
        "topic=ftrack.connect.application.launch",
        app_launch_open_file.modify_application_launch)

    ftrack.EVENT_HUB.subscribe(
        "topic=ftrack.connect.application.launch",
        app_launch_environment.modify_application_launch)

    ftrack.EVENT_HUB.wait()
