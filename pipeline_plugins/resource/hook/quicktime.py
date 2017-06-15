import logging
import sys
import pprint
import getpass

import subprocess
import os
import ftrack
import ftrack_connect.application
from hook_utils import get_components


class QuickTimeAction(object):
    """Launch QuickTime action."""

    identifier = "quicktime-launch-action"

    def __init__(self, applicationStore, launcher):

        super(QuickTimeAction, self).__init__()

        self.logger = logging.getLogger(
            __name__ + "." + self.__class__.__name__
        )

        self.applicationStore = applicationStore
        self.launcher = launcher

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

    def is_valid_selection(self, event):
        selection = event["data"].get("selection", [])

        if not selection:
            return

        entityType = selection[0]["entityType"]

        if entityType not in ["assetversion", "task"]:
            return False

        if entityType == "assetversion":
            version = ftrack.AssetVersion(selection[0]["entityId"])

            # filter to image sequences and movies only
            if version.getAsset().getType().getShort() != "mov":
                return False

        if entityType == "task":
            task = ftrack.Task(selection[0]["entityId"])

            # filter to tasks
            if task.getObjectType() != "Task":
                return False

        return True

    def discover(self, event):

        if not self.is_valid_selection(event):
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

    def launch_subprocess(self, event):

        applicationIdentifier = event["data"]["applicationIdentifier"]
        application = self.applicationStore.getApplication(
            applicationIdentifier
        )
        context = event["data"].copy()
        context["source"] = event["source"]
        command = self.launcher._getApplicationLaunchCommand(
            application, context
        )

        success = True
        message = '{0} application started.'.format(application['label'])

        command.append(event["data"]["values"]["component"])

        try:
            options = dict(
                close_fds=True
            )

            # Ensure subprocess is detached so closing connect will not
            # also close launched applications.
            if sys.platform == 'win32':
                options['creationflags'] = subprocess.CREATE_NEW_CONSOLE
            else:
                options['preexec_fn'] = os.setsid

            self.logger.debug(
                'Launching {0} with options {1}'.format(command, options)
            )
            process = subprocess.Popen(command, **options)

        except (OSError, TypeError):
            self.logger.exception(
                '{0} application could not be started with command "{1}".'
                    .format(applicationIdentifier, command)
            )

            success = False
            message = '{0} application could not be started.'.format(
                application['label']
            )

        else:
            self.logger.debug(
                '{0} application started. (pid={1})'.format(
                    applicationIdentifier, process.pid
                )
            )

        return {
            'success': success,
            'message': message
        }

    def launch(self, event):
        """Callback method for QuickTime action."""

        # launching application
        if "values" in event["data"]:
            return self.launch_subprocess(event)

        return {
            "items": [
                {
                    "label": "Component to view",
                    "type": "enumerator",
                    "name": "component",
                    "data": get_components(event, asset_types=['mov'])
                }
            ]
        }


class ApplicationStore(ftrack_connect.application.ApplicationStore):
    """Store used to find and keep track of available applications."""

    def _discoverApplications(self):
        """Return a list of applications that can be launched from this host.
        """
        applications = []
        icon = "https://upload.wikimedia.org/wikipedia/fr/b/b6/"
        icon += "Logo_quicktime.png"

        if sys.platform == "darwin":
            pass

        elif sys.platform == "win32":
            applications.extend(self._searchFilesystem(
                expression=["C:\\", "Program Files*", "QuickTime",
                            "QuickTimePlayer.exe"],
                label="QuickTime",
                applicationIdentifier="quicktime",
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
    action = QuickTimeAction(applicationStore, launcher)
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
    action = QuickTimeAction(applicationStore, launcher)
    action.register()

    # dependent event listeners
    import app_launch_open_file
    reload(app_launch_open_file)

    ftrack.EVENT_HUB.subscribe(
        "topic=ftrack.connect.application.launch",
        app_launch_open_file.modify_application_launch)

    ftrack.EVENT_HUB.wait()
