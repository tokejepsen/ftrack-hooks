# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

import logging
import sys
import pprint
import os
import getpass
import re
from operator import itemgetter

if __name__ == '__main__':
    tools_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.append(os.path.join(tools_path, 'ftrack', 'ftrack-api'))

    import zipimport
    ftrack_connect_path = os.path.join(tools_path, 'ftrack',
                                       'ftrack-connect-package', 'windows',
                                       'current')
    path = os.path.join(ftrack_connect_path, 'common.zip')
    importer = zipimport.zipimporter(path)
    ftrack_connect = importer.load_module('ftrack_connect')

import ftrack
import ftrack_connect.application


class QuickTimeAction(object):
    '''Launch QuickTime action.'''

    # Unique action identifier.
    identifier = 'quicktime-launch-action'

    def __init__(self, applicationStore, launcher):
        '''Initialise action with *applicationStore* and *launcher*.

        *applicationStore* should be an instance of
        :class:`ftrack_connect.application.ApplicationStore`.

        *launcher* should be an instance of
        :class:`ftrack_connect.application.ApplicationLauncher`.

        '''
        super(QuickTimeAction, self).__init__()

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

    def is_valid_selection(self, event):
        selection = event['data'].get('selection', [])

        # If selection contains more than one item return early since
        # this action will only handle a single version.
        entityType = selection[0]['entityType']
        if len(selection) != 1 or entityType not in ['assetversion', 'task']:
            return False

        if entityType == 'assetversion':
            version = ftrack.AssetVersion(selection[0]['entityId'])

            # filter to image sequences and movies only
            if version.getAsset().getType().getShort() != 'mov':
                return False

        if entityType == 'task':
            task = ftrack.Task(selection[0]['entityId'])

            # filter to tasks
            if task.getObjectType() != 'Task':
                return False

        return True

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
        if not self.is_valid_selection(event):
            return

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
        '''Callback method for QuickTime action.'''

        # launching application
        if 'values' in event['data']:
            context = event['data'].copy()
            applicationIdentifier = event['data']['applicationIdentifier']

            return self.launcher.launch(applicationIdentifier, context)

        # finding components
        data = []
        for item in event['data'].get('selection', []):
            selection = event['data']['selection']
            entityType = selection[0]['entityType']

            # get all components on version
            if entityType == 'assetversion':
                version = ftrack.AssetVersion(item['entityId'])

                if not version.get('ispublished'):
                    version.publish()

                for c in version.getComponents():
                    data.append({'label': c.getName(), 'value': c.getId()})

            # get all components on all valid versions
            if entityType == 'task':
                task = ftrack.Task(selection[0]['entityId'])

                for asset in task.getAssets(assetTypes=['mov']):
                    for version in asset.getVersions():
                        for component in version.getComponents():
                            label = 'v' + str(version.getVersion()).zfill(3)
                            label += ' - ' + asset.getType().getName()
                            label += ' - ' + component.getName()
                            data.append({'label': label,
                                         'value': component.getId()})

                data = sorted(data, key=itemgetter('label'), reverse=True)

        return {'items': [{'label': 'Component to view',
                           'type': 'enumerator',
                           'name': 'component',
                           'data': data}]}


class ApplicationStore(ftrack_connect.application.ApplicationStore):
    '''Store used to find and keep track of available applications.'''

    def _discoverApplications(self):
        '''Return a list of applications that can be launched from this host.
        '''
        applications = []
        icon = 'https://upload.wikimedia.org/wikipedia/fr/b/b6/'
        icon += 'Logo_quicktime.png'

        if sys.platform == 'darwin':
            pass

        elif sys.platform == 'win32':
            applications.extend(self._searchFilesystem(
                expression=['C:\\', 'Program Files*', 'QuickTime',
                            'QuickTimePlayer.exe'],
                label='QuickTime',
                applicationIdentifier='quicktime',
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
    action = QuickTimeAction(applicationStore, launcher)
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
    action = QuickTimeAction(applicationStore, launcher)
    action.register()

    # dependent event listeners
    import app_launch_open_file
    reload(app_launch_open_file)

    ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.connect.application.launch',
        app_launch_open_file.modify_application_launch)

    ftrack.EVENT_HUB.wait()
