# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

import getpass
import sys
import pprint
import logging
import json
import re
import os
import argparse

tools_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

if __name__ == '__main__':
    sys.path.append(os.path.join(tools_path, 'ftrack', 'ftrack-api'))

    ftrack_connect_path = os.path.join(tools_path, 'ftrack',
                                'ftrack-connect-package', 'windows', 'v0.2.0')
    sys.path.append(os.path.join(ftrack_connect_path, 'common.zip'))

import ftrack
import ftrack_connect.application


class LaunchApplicationAction(object):
    '''Discover and launch action.'''

    identifier = 'ftrack-connect-launch-rv'

    def __init__(self, applicationStore, launcher):
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

        self.applicationStore = applicationStore
        self.launcher = launcher

    def _createPlaylistFromSelection(self, selection):
        '''Return new selection with temporary playlist from *selection*.'''

        # If selection is only one entity we don't need to create
        # a playlist.
        if len(selection) == 1:
            return selection

        playlist = []
        for entity in selection:
            playlist.append({
                'id': entity['entityId'],
                'type': entity['entityType']
            })

        playlist = ftrack.createTempData(json.dumps(playlist))

        selection = [{
            'entityType': 'tempdata',
            'entityId': playlist.getId()
        }]

        return selection

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
                'icon': application.get('icon', 'default'),
                'applicationIdentifier': applicationIdentifier
            })

        return {
            'items': items
        }

    def launch(self, event):
        '''Handle *event*.

        event['data'] should contain:

            *applicationIdentifier* to identify which application to start.

        '''

        applicationIdentifier = (
            event['data']['applicationIdentifier']
        )

        context = event['data'].copy()

        # Rewrite original selection to a playlist.
        context['selection'] = self._createPlaylistFromSelection(
            context['selection']
        )

        self.launcher.launch(applicationIdentifier, context)

        return {
            'success': True,
            'message': 'RV Launched'
        }


class ApplicationStore(ftrack_connect.application.ApplicationStore):

    def _discoverApplications(self):
        '''Return a list of applications that can be launched from this host.

        An application should be of the form:

            dict(
                'identifier': 'name_version',
                'label': 'Name version',
                'path': 'Absolute path to the file',
                'version': 'Version of the application',
                'icon': 'URL or name of predefined icon'
            )

        '''
        applications = []

        if sys.platform == 'win32':

            path = tools_path.split(os.sep) + ['rv', 'RV.\d.+', 'bin', 'rv.exe']
            applications.extend(self._searchFilesystem(
                expression=path,
                versionExpression=re.compile(r'(?P<version>\d+.\d+.\d+)'),
                label='Review with RV {version}',
                applicationIdentifier='rv_{version}_with_review',
                icon='https://www.shotgunsoftware.com/img/home/icon_RV.png',
                launchArguments=[
                    '-flags', 'ModeManagerPreload=ftrack'
                ]
            ))

        self.logger.info(
            'Discovered applications:\n{0}'.format(
                pprint.pformat(applications)
            )
        )

        return applications


def register(registry, **kw):
    '''Register hooks.'''

    # Create store containing applications.
    applicationStore = ApplicationStore()

    # Create a launcher with the store containing applications.
    launcher = ftrack_connect.application.ApplicationLauncher(
        applicationStore
    )

    # Create action and register to respond to discover and launch actions.
    action = LaunchApplicationAction(applicationStore, launcher)
    action.register()


def main(arguments=None):
    '''Set up logging and register action.'''
    if arguments is None:
        arguments = []

    parser = argparse.ArgumentParser()
    # Allow setting of logging level from arguments.
    loggingLevels = {}
    for level in (
        logging.NOTSET, logging.DEBUG, logging.INFO, logging.WARNING,
        logging.ERROR, logging.CRITICAL
    ):
        loggingLevels[logging.getLevelName(level).lower()] = level

    parser.add_argument(
        '-v', '--verbosity',
        help='Set the logging output verbosity.',
        choices=loggingLevels.keys(),
        default='info'
    )
    namespace = parser.parse_args(arguments)

    '''Register action and listen for events.'''
    logging.basicConfig(level=loggingLevels[namespace.verbosity])
    log = logging.getLogger()

    ftrack.setup()

    # Create store containing applications.
    applicationStore = ApplicationStore()

    # Create a launcher with the store containing applications.
    launcher = ftrack_connect.application.ApplicationLauncher(
        applicationStore
    )

    # Create action and register to respond to discover and launch actions.
    action = LaunchApplicationAction(applicationStore, launcher)
    action.register()

    ftrack.EVENT_HUB.wait()


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
