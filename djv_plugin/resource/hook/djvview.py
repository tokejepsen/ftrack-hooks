import logging
import subprocess
import sys
import pprint
import os
import getpass
import re
from operator import itemgetter

import ftrack
import ftrack_api
from ftrack_connect.session import get_shared_session
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

            command.append(event["data"]["values"]["path"])

            try:
                options = dict(
                    env={},
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

        data = event["data"]
        data["items"] = []

        # Starting a job to show user the progress of scanning for files.
        job = ftrack.createJob("DJV: Scanning for files.", "queued",
                               ftrack.User(id=event["source"]["user"]["id"]))
        job.setStatus("running")

        try:
            ftrack.EVENT_HUB.publish(
                ftrack.Event(
                    topic='djvview.launch',
                    data=data
                ),
                synchronous=True
            )
            session = get_shared_session()
            session.event_hub.publish(
                ftrack_api.event.base.Event(
                    topic='djvview.launch',
                    data=data
                ),
                synchronous=True
            )
        except:
            job.setStatus("failed")
        else:
            job.setStatus("done")

        return {
            "items": [
                {
                    "label": "Items to view",
                    "type": "enumerator",
                    "name": "path",
                    "data": sorted(
                        data["items"],
                        key=itemgetter("label"),
                        reverse=True
                    )
                }
            ]
        }


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
