import logging
import sys
import pprint
import os
import getpass
import re
from operator import itemgetter

import ftrack
import ftrack_connect.application


class DJVViewAction(object):
    """Launch DJVView action."""

    identifier = "djvview-launch-action"

    def __init__(self, applicationStore, launcher):

        super(DJVViewAction, self).__init__()

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

    def is_valid_selection(self, event):
        selection = event["data"].get("selection", [])

        if not selection:
            return

        entityType = selection[0]["entityType"]

        if entityType not in ["assetversion", "task"]:
            return False

        if entityType == "task":
            task = ftrack.Task(selection[0]["entityId"])

            # filter to tasks
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

    def launch(self, event):
        """Callback method for DJVView action."""

        # Launching application
        if "values" in event["data"]:
            context = event["data"].copy()
            applicationIdentifier = event["data"]["applicationIdentifier"]

            return self.launcher.launch(applicationIdentifier, context)

        # Collect all
        data = {}
        for item in event["data"].get("selection", []):

            versions = []

            if item["entityType"] == "assetversion":
                version = ftrack.AssetVersion(item["entityId"])
                if version.getAsset().getType().getShort() in ["img", "mov"]:
                    versions.append(version)

            # Add all "img" and "mov" type versions from tasks
            if item["entityType"] == "task":
                task = ftrack.Task(item["entityId"])

                for asset in task.getAssets(assetTypes=["img", "mov"]):
                    for version in asset.getVersions():
                        versions.append(version)

            for version in versions:
                for component in version.getComponents():
                    component_list = data.get(component.getName(), [])
                    component_list.append(component)
                    data[component.getName()] = component_list

        data_list = []
        for key, value in data.iteritems():

            if len(value) == 1:
                label = "v{0} - {1} - {2}"
                label = label.format(
                    str(value[0].getVersion().getVersion()).zfill(3),
                    value[0].getVersion().getAsset().getType().getName(),
                    key
                )
                data_list.append({"label": label, "value": component.getId()})
            else:
                label = "multiple - " + key
                ids = ""
                for component in value:
                    ids += component.getId() + ","

                data_list.append({"label": label, "value": ids[:-1]})

        data_list = sorted(data_list, key=itemgetter("label"), reverse=True)

        return {"items": [{"label": "Components to view",
                           "type": "enumerator",
                           "name": "components",
                           "data": data_list}]}


class ApplicationStore(ftrack_connect.application.ApplicationStore):
    """Store used to find and keep track of available applications."""

    def _discoverApplications(self):
        """Return a list of applications that can be launched from this host.
        """
        applications = []

        if sys.platform == "darwin":
            pass

        elif sys.platform == "win32":
            applications.extend(self._searchFilesystem(
                expression=["C:\\", "Program Files", "djv-\d.+",
                            "bin", "djv_view.exe"],
                label="DJVView {version}",
                versionExpression=re.compile(r"(?P<version>\d+.\d+.\d+)"),
                applicationIdentifier="djvview",
                icon="http://a.fsdn.com/allura/p/djv/icon"
            ))

        if not applications:
            func = os.path.dirname
            tools_path = func(func(func(func(func(__file__)))))
            path = os.path.join(tools_path, "djv-viewer",
                                "djv-1.1.0-Windows-64", "bin", "djv_view.exe")

            applications = [{"description": None,
                             "icon": "http://a.fsdn.com/allura/p/djv/icon",
                             "identifier": "djvview",
                             "label": "DJVView Network",
                             "path": path}]

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
    action = DJVViewAction(applicationStore, launcher)
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
    action = DJVViewAction(applicationStore, launcher)
    action.register()

    # dependent event listeners
    import app_launch_open_file
    reload(app_launch_open_file)

    ftrack.EVENT_HUB.subscribe(
        "topic=ftrack.connect.application.launch",
        app_launch_open_file.modify_application_launch)

    ftrack.EVENT_HUB.wait()
