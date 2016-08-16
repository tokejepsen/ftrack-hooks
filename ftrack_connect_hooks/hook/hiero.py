# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

import getpass
import sys
import pprint
import logging
import re
import os

func = os.path.dirname
tools_path = func(func(func(func(func(__file__)))))
ftrack_connect_path = os.path.join(tools_path, "ftrack",
                                   "ftrack-connect-package", "windows",
                                   "current")

if __name__ == "__main__":
    sys.path.append(os.path.join(tools_path, "ftrack", "ftrack-api"))
    path = os.path.join(ftrack_connect_path, "common.zip")
    import zipimport
    importer = zipimport.zipimporter(path)
    ftrack_connect = importer.load_module("ftrack_connect")

    path = ""
    path += os.pathsep + os.path.join(tools_path, "pyblish", "pyblish-base")
    path += os.pathsep + os.path.join(tools_path, "pyblish", "pyblish-hiero")
    path += os.pathsep + os.path.join(tools_path, "pyblish", "pyblish-nuke")
    path += os.pathsep + os.path.join(tools_path, "pyblish", "pyblish-qml")
    path += os.pathsep + os.path.join(tools_path, "pyblish", "python-qt5")
    path += os.pathsep + os.path.join(tools_path, "pipeline-schema")
    os.environ["PYTHONPATH"] = path

    path = ""
    path += os.pathsep + os.path.join(tools_path, "pyblish", "pyblish-nuke",
                                      "pyblish_nuke", "nuke_path")
    path += os.pathsep + os.path.join(tools_path, "ftrack", "ftrack-tools")
    os.environ["NUKE_PATH"] = path

    os.environ["HIERO_PLUGIN_PATH"] = os.path.join(tools_path, "pyblish",
                                                   "pyblish-hiero",
                                                   "pyblish_hiero",
                                                   "hiero_plugin_path")

    os.environ["PYBLISHPLUGINPATH"] = ""
    sys.path.append(r"C:\Users\toke.jepsen\Desktop\library")

import ftrack
import ftrack_connect.application


class LaunchApplicationAction(object):
    '''Discover and launch hiero.'''

    identifier = 'hiero'

    def __init__(self, application_store, launcher):
        '''Initialise action with *applicationStore* and *launcher*.

        *applicationStore* should be an instance of
        :class:`ftrack_connect.application.ApplicationStore`.

        *launcher* should be an instance of
        :class:`ftrack_connect.application.ApplicationLauncher`.

        '''
        super(LaunchApplicationAction, self).__init__()

        self.logger = logging.getLogger(
            __name__ + '.' + self.__class__.__name__
        )

        self.application_store = application_store
        self.launcher = launcher

    def is_valid_selection(self, selection):
        '''Return true if the selection is valid.'''
        if (
            len(selection) != 1 or
            selection[0]['entityType'] != 'task'
        ):
            return False

        entity = selection[0]
        task = ftrack.Task(entity['entityId'])

        if task.getObjectType() != 'Task':
            return False

        return True

    def register(self):
        '''Register discover actions on logged in user.'''
        ftrack.EVENT_HUB.subscribe(
            'topic=ftrack.action.discover and source.user.username={0}'.format(
                getpass.getuser()
            ),
            self.discover
        )

        ftrack.EVENT_HUB.subscribe(
            'topic=ftrack.action.launch and source.user.username={0} '
            'and data.actionIdentifier={1}'.format(
                getpass.getuser(), self.identifier
            ),
            self.launch
        )

    def discover(self, event):
        '''Return discovered applications.'''

        if not self.is_valid_selection(
            event['data'].get('selection', [])
        ):
            return

        items = []
        applications = self.application_store.applications
        applications = sorted(
            applications, key=lambda application: application['label']
        )

        for application in applications:
            application_identifier = application['identifier']
            label = application['label']
            items.append({
                'actionIdentifier': self.identifier,
                'label': label,
                'variant': application.get('variant', None),
                'description': application.get('description', None),
                'icon': application.get('icon', 'default'),
                'applicationIdentifier': application_identifier
            })

        return {
            'items': items
        }

    def launch(self, event):
        '''Handle *event*.

        event['data'] should contain:

            *applicationIdentifier* to identify which application to start.

        '''
        # Prevent further processing by other listeners.
        event.stop()

        if not self.is_valid_selection(
            event['data'].get('selection', [])
        ):
            return

        application_identifier = (
            event['data']['applicationIdentifier']
        )

        context = event['data'].copy()
        context['source'] = event['source']

        application_identifier = event['data']['applicationIdentifier']
        context = event['data'].copy()
        context['source'] = event['source']

        return self.launcher.launch(
            application_identifier, context
        )


class ApplicationStore(ftrack_connect.application.ApplicationStore):

    def _discoverApplications(self):
        '''Return a list of applications that can be launched from this host.

        An application should be of the form:

            dict(
                'identifier': 'name_version',
                'label': 'Name',
                'variant': 'version',
                'description': 'description',
                'path': 'Absolute path to the file',
                'version': 'Version of the application',
                'icon': 'URL or name of predefined icon'
            )

        '''
        applications = []

        if sys.platform == 'win32':
            prefix = ['C:\\', 'Program Files.*']

            # Specify custom expression for Nuke to ensure the complete version
            # number (e.g. 9.0v3) is picked up.
            nuke_version_expression = re.compile(
                r'(?P<version>[\d.]+[vabc]+[\dvabc.]*)'
            )

            # Add NukeX as a separate application
            applications.extend(self._searchFilesystem(
                expression=prefix + ['Nuke.*', 'Nuke\d.+.exe'],
                versionExpression=nuke_version_expression,
                launchArguments=['--hiero'],
                label='Hiero',
                variant='{version}',
                applicationIdentifier='hiero_{version}',
                icon='hiero'
            ))

        self.logger.debug(
            'Discovered applications:\n{0}'.format(
                pprint.pformat(applications)
            )
        )

        return applications


class ApplicationLauncher(ftrack_connect.application.ApplicationLauncher):
    '''Custom launcher to modify environment before launch.'''

    def __init__(self, application_store):
        '''.'''
        super(ApplicationLauncher, self).__init__(application_store)

    def _getApplicationEnvironment(
        self, application, context=None
    ):
        '''Override to modify environment before launch.'''

        # Make sure to call super to retrieve original environment
        # which contains the selection and ftrack API.
        environment = super(
            ApplicationLauncher, self
        )._getApplicationEnvironment(application, context)

        entity = context['selection'][0]
        task = ftrack.Task(entity['entityId'])
        taskParent = task.getParent()

        try:
            environment['FS'] = str(int(taskParent.getFrameStart()))
        except Exception:
            environment['FS'] = '1'

        try:
            environment['FE'] = str(int(taskParent.getFrameEnd()))
        except Exception:
            environment['FE'] = '1'

        environment['FTRACK_TASKID'] = task.getId()
        environment['FTRACK_SHOTID'] = task.get('parent_id')

        return environment


def register(registry, **kw):
    '''Register hooks.'''

    # Validate that registry is the event handler registry. If not,
    # assume that register is being called to regiter Locations or from a new
    # or incompatible API, and return without doing anything.
    if registry is not ftrack.EVENT_HANDLERS:
        return

    # Create store containing applications.
    application_store = ApplicationStore()

    # Create a launcher with the store containing applications.
    launcher = ApplicationLauncher(application_store)

    # Create action and register to respond to discover and launch actions.
    action = LaunchApplicationAction(application_store, launcher)
    action.register()


def main(arguments=None):
    """Register action and listen for events."""
    logging.basicConfig(level=logging.INFO)

    ftrack.setup()

    # Create store containing applications.
    application_store = ApplicationStore()

    launcher = ApplicationLauncher(application_store)

    # Create action and register to respond to discover and launch actions.
    action = LaunchApplicationAction(application_store, launcher)
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


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
