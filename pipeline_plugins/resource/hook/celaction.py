# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

import logging
import sys
import pprint
import os
import getpass
import _winreg

if __name__ == "__main__":
    tools_path = os.getenv("NETWORK_TOOLS_PATH", os.path.dirname(__file__))
    sys.path.append(os.path.join(tools_path, "ftrack", "ftrack-api"))

    ftrack_connect_path = os.path.join(tools_path, "ftrack",
                                       "ftrack-connect-package", "windows",
                                       "current")
    path = os.path.join(ftrack_connect_path, "common.zip")
    import zipimport
    importer = zipimport.zipimporter(path)
    ftrack_connect = importer.load_module("ftrack_connect")

import ftrack
import ftrack_connect.application


class CelActionAction(object):
    """Launch CelAction action."""

    # Unique action identifier.
    identifier = "celaction-launch-action"

    def __init__(self, applicationStore, launcher):
        """Initialise action with *applicationStore* and *launcher*.

        *applicationStore* should be an instance of
        :class:`ftrack_connect.application.ApplicationStore`.

        *launcher* should be an instance of
        :class:`ftrack_connect.application.ApplicationLauncher`.

        """
        super(CelActionAction, self).__init__()

        self.logger = logging.getLogger(
            __name__ + "." + self.__class__.__name__
        )

        self.applicationStore = applicationStore
        self.launcher = launcher

        if self.identifier is None:
            raise ValueError("The action must be given an identifier.")

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

    def discover(self, event):
        """Return available actions based on *event*.

        Each action should contain

            actionIdentifier - Unique identifier for the action
            label - Nice name to display in ftrack
            variant - Variant or version of the application.
            icon(optional) - predefined icon or URL to an image
            applicationIdentifier - Unique identifier to identify application
                                    in store.

        """
        if not self.is_valid_selection(
            event["data"].get("selection", [])
        ):
            return

        items = []
        applications = self.applicationStore.applications
        applications = sorted(
            applications, key=lambda application: application["label"]
        )

        for application in applications:
            applicationIdentifier = application["identifier"]
            label = application["label"]
            items.append({
                "actionIdentifier": self.identifier,
                "label": label,
                "variant": application.get("variant", None),
                "description": application.get("description", None),
                "icon": application.get("icon", "default"),
                "applicationIdentifier": applicationIdentifier
            })

        return {
            "items": items
        }

    def launch(self, event):
        """Callback method for CelAction action."""
        applicationIdentifier = (
            event["data"]["applicationIdentifier"]
        )

        context = event["data"].copy()

        tools_path = os.getenv("NETWORK_TOOLS_PATH", os.path.dirname(__file__))

        # setting output parameters
        path = r"Software\CelAction\CelAction2D\User Settings"
        _winreg.CreateKey(_winreg.HKEY_CURRENT_USER, path)
        hKey = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER,
                               r"Software\CelAction\CelAction2D\User Settings",
                               0, _winreg.KEY_ALL_ACCESS)

        path = os.path.join(tools_path, "pyblish", "pyblish_standalone.bat")
        _winreg.SetValueEx(hKey, "SubmitAppTitle", 0, _winreg.REG_SZ, path)

        parameters = " --path \"*SCENE*\" -d chunk *CHUNK* -d start *START*"
        parameters += " -d end *END* -d x *X* -d y *Y* -rh celaction"
        parameters += " -d progpath \"*PROGPATH*\""
        _winreg.SetValueEx(hKey, "SubmitParametersTitle", 0, _winreg.REG_SZ,
                           parameters)

        # setting resolution parameters
        path = r"Software\CelAction\CelAction2D\User Settings\Dialogs"
        path += r"\SubmitOutput"
        _winreg.CreateKey(_winreg.HKEY_CURRENT_USER, path)
        hKey = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, path, 0,
                               _winreg.KEY_ALL_ACCESS)
        _winreg.SetValueEx(hKey, "SaveScene", 0, _winreg.REG_DWORD, 1)
        _winreg.SetValueEx(hKey, "CustomX", 0, _winreg.REG_DWORD, 1920)
        _winreg.SetValueEx(hKey, "CustomY", 0, _winreg.REG_DWORD, 1080)

        # making sure message dialogs don't appear when overwriting
        path = r"Software\CelAction\CelAction2D\User Settings\Messages"
        path += r"\OverwriteScene"
        _winreg.CreateKey(_winreg.HKEY_CURRENT_USER, path)
        hKey = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, path, 0,
                               _winreg.KEY_ALL_ACCESS)
        _winreg.SetValueEx(hKey, "Result", 0, _winreg.REG_DWORD, 6)
        _winreg.SetValueEx(hKey, "Valid", 0, _winreg.REG_DWORD, 1)

        path = r"Software\CelAction\CelAction2D\User Settings\Messages"
        path += r"\SceneSaved"
        _winreg.CreateKey(_winreg.HKEY_CURRENT_USER, path)
        hKey = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, path, 0,
                               _winreg.KEY_ALL_ACCESS)
        _winreg.SetValueEx(hKey, "Result", 0, _winreg.REG_DWORD, 1)
        _winreg.SetValueEx(hKey, "Valid", 0, _winreg.REG_DWORD, 1)

        return self.launcher.launch(applicationIdentifier, context)


class ApplicationStore(ftrack_connect.application.ApplicationStore):
    """Store used to find and keep track of available applications."""

    def _discoverApplications(self):
        """Return a list of applications that can be launched from this host.
        """
        applications = []
        icon = "https://pbs.twimg.com/profile_images/3741062735/"
        icon += "e0b8fce362e6b3ff7414f4cdfa1a4a75_400x400.png"

        if sys.platform == "darwin":
            pass

        elif sys.platform == "win32":
            applications.extend(self._searchFilesystem(
                expression=["C:\\", "Program Files*", "CelAction",
                            "CelAction2D.exe"],
                label="CelAction",
                applicationIdentifier="celaction",
                icon=icon
            ))

        self.logger.debug(
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
    action = CelActionAction(applicationStore, launcher)
    action.register()


if __name__ == "__main__":
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)

    # Create store containing applications.
    applicationStore = ApplicationStore()

    # Create a launcher with the store containing applications.
    launcher = ftrack_connect.application.ApplicationLauncher(
        applicationStore
    )

    # Create action and register to respond to discover and launch actions.
    ftrack.setup()
    action = CelActionAction(applicationStore, launcher)
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
