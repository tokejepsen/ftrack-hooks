# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

import logging
import sys
import pprint
import os
import getpass
import re

if __name__ == '__main__':
    import zipimport

    tools_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.append(os.path.join(tools_path, 'ftrack', 'ftrack-api'))
    ftrack_connect_path = os.path.join(tools_path, 'ftrack',
                                       'ftrack-connect-package', 'windows',
                                       'current')
    path = os.path.join(ftrack_connect_path, 'common.zip')
    importer = zipimport.zipimporter(path)
    ftrack_connect = importer.load_module('ftrack_connect')

import ftrack
import ftrack_connect.application


class AtomAction(object):
    '''Launch Atom action.'''

    # Unique action identifier.
    identifier = 'atom-launch-action'

    def __init__(self, applicationStore, launcher):
        '''Initialise action with *applicationStore* and *launcher*.

        *applicationStore* should be an instance of
        :class:`ftrack_connect.application.ApplicationStore`.

        *launcher* should be an instance of
        :class:`ftrack_connect.application.ApplicationLauncher`.

        '''
        super(AtomAction, self).__init__()

        self.logger = logging.getLogger(
            __name__ + '.' + self.__class__.__name__
        )

        self.applicationStore = applicationStore
        self.launcher = launcher

        if self.identifier is None:
            raise ValueError('The action must be given an identifier.')

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
        '''Callback method for Atom action.'''
        applicationIdentifier = (
            event['data']['applicationIdentifier']
        )

        context = event['data'].copy()
        context['source'] = event['source']

        return self.launcher.launch(applicationIdentifier, context)


class ApplicationStore(ftrack_connect.application.ApplicationStore):
    '''Store used to find and keep track of available applications.'''

    def _discoverApplications(self):
        '''Return a list of applications that can be launched from this host.
        '''
        applications = []
        icon = 'https://raw.githubusercontent.com/atom/atom/master/resources/'
        icon += 'app-icons/stable/png/1024.png'

        if sys.platform == 'darwin':
            pass

        elif sys.platform == 'win32':
            path = os.getenv('LOCALAPPDATA').split('\\')
            path[0] = path[0] + '\\'
            path.extend(['atom', 'bin*', 'atom.cmd'])

            applications.extend(self._searchFilesystem(
                expression=path,
                label='Atom',
                versionExpression=re.compile(r'(?P<version>)'),
                applicationIdentifier='atom',
                icon=icon
            ))

        self.logger.debug(
            'Discovered applications:\n{0}'.format(
                pprint.pformat(applications)
            )
        )

        return applications


def register(registry, **kw):
    '''Register hooks.'''

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
    action = AtomAction(applicationStore, launcher)
    action.register()


if __name__ == '__main__':
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
    action = AtomAction(applicationStore, launcher)
    action.register()

    # dependent event listeners
    import app_launch_open_file
    import app_launch_environment

    ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.connect.application.launch',
        app_launch_open_file.modify_application_launch)

    ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.connect.application.launch',
        app_launch_environment.modify_application_launch)

    ftrack.EVENT_HUB.wait()
