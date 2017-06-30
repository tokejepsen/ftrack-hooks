import getpass
import sys
import pprint
import logging
import json
import re
import os

import ftrack
import ftrack_connect.application


class LaunchApplicationAction(object):
    """Discover and launch action."""

    identifier = "network-rv"

    def __init__(self, applicationStore, launcher):
        """Initialise action with *applicationStore* and *launcher*.

        *applicationStore* should be an instance of
        :class:`ftrack_connect.application.ApplicationStore`.

        *launcher* should be an instance of
        :class:`ftrack_connect.application.ApplicationLauncher`.

        """
        super(LaunchApplicationAction, self).__init__()

        self.logger = logging.getLogger(
            __name__ + "." + self.__class__.__name__
        )

        self.applicationStore = applicationStore
        self.launcher = launcher

    def _createPlaylistFromSelection(self, selection):
        """Return new selection with temporary playlist from *selection*."""

        # If selection is only one entity we don"t need to create
        # a playlist.
        if len(selection) == 1:
            return selection

        playlist = []
        for entity in selection:
            playlist.append({
                "id": entity["entityId"],
                "type": entity["entityType"]
            })

        playlist = ftrack.createTempData(json.dumps(playlist))

        selection = [{
            "entityType": "tempdata",
            "entityId": playlist.getId()
        }]

        return selection

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
        '''Return available actions based on *event*.

        Each action should contain

            actionIdentifier - Unique identifier for the action
            label - Nice name to display in ftrack
            variant - Variant or version of the application.
            icon(optional) - predefined icon or URL to an image
            applicationIdentifier - Unique identifier to identify application
                                    in store.

        '''

        items = []
        applications = self.applicationStore.applications
        applications = sorted(
            applications, key=lambda application: application['label']
        )

        for application in applications:
            applicationIdentifier = application['identifier']
            label = application['label']
            items.append({
                'actionIdentifier': self.identifier,
                'label': label,
                'variant': application.get('variant', None),
                'description': application.get('description', None),
                'icon': application.get('icon', 'default'),
                'applicationIdentifier': applicationIdentifier
            })

        return {
            'items': items
        }

    def launch(self, event):
        '''Callback method for Houdini action.'''
        applicationIdentifier = (
            event['data']['applicationIdentifier']
        )

        context = event['data'].copy()

        # Rewrite original selection to a playlist.
        context['selection'] = self._createPlaylistFromSelection(
            context['selection']
        )

        return self.launcher.launch(applicationIdentifier, context)


class ApplicationStore(ftrack_connect.application.ApplicationStore):

    def _discoverApplications(self):
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

        if sys.platform == "win32":

            tools_path = os.getenv("NETWORK_TOOLS_PATH", os.path.dirname(__file__))
            path = tools_path.split(os.sep) + ["rv", "RV.\d.+", "bin",
                                               "rv.exe"]
            applications.extend(self._searchFilesystem(
                expression=path,
                versionExpression=re.compile(r"(?P<version>\d+.\d+.\d+)"),
                label="RV",
                variant='{version}',
                applicationIdentifier="rv_{version}",
                icon="https://www.shotgunsoftware.com/img/home/icon_RV.png",
                launchArguments=["-flags", "ModeManagerPreload=ftrack"]
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
    action = LaunchApplicationAction(applicationStore, launcher)
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
    action = LaunchApplicationAction(applicationStore, launcher)
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
