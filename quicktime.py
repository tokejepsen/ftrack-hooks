import sys
import argparse
import logging
import os
import getpass
import pprint
import subprocess

if __name__ == '__main__':
    tools_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.append(os.path.join(tools_path, 'ftrack', 'ftrack-api'))

import ftrack


class Action(ftrack.Action):
    '''Custom action.'''

    #: Action identifier.
    identifier = 'quicktime'

    #: Action label.
    label = 'Quicktime'


    def __init__(self):
        '''Initialise action handler.'''
        self.log = logging.getLogger(
            __name__ + '.' + self.__class__.__name__
        )

    def register(self):
        '''Register action.'''
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

    def is_valid_selection(self, selection):
        '''Return true if the selection is valid.'''

        if selection[0]['entityType'] not in ['task', 'assetversion']:
            return False

        entity = selection[0]

        if entity['entityType'] == 'task':
            task = ftrack.Task(entity['entityId'])

            if task.getObjectType() != 'Task':
                return False

        if entity['entityType'] == 'assetversion':
            asset_version = ftrack.AssetVersion(entity['entityId'])

            if asset_version.getAsset().getType().getShort() != 'mov':
                return False

        return True

    def discover(self, event):

        if not self.is_valid_selection(event['data'].get('selection', [])):
            return

        return {
            'items': [{
                'label': self.label,
                'actionIdentifier': self.identifier,
                'icon': "https://upload.wikimedia.org/wikipedia/fr/b/b6/Logo_quicktime.png"
            }]
        }


    def launch(self, event):
        data = event['data']
        selection = data.get('selection', [])

        if 'values' in event['data']:
            # Do something with the values or return a new form.
            values = event['data']['values']

            component = ftrack.Component(values['component'])

            f = component.getFilesystemPath()


            path = os.path.join(r'C:\Program Files (x86)\QuickTime',
                                                'QuickTimePlayer.exe')
            args = [path, f]
            subprocess.Popen(args)

            return {
                'success': True,
                'message': 'Quicktime launched.'
            }

        # finding components on version
        components = {}
        for item in selection:
            asset = None
            version = None

            try:
                task = ftrack.Task(item['entityId'])
                asset = task.getAssets(assetTypes=['mov'])[0]
            except:
                version = ftrack.AssetVersion(item['entityId'])

            if asset:
                for v in reversed(asset.getVersions()):
                    for c in v.getComponents():
                        if c.getName() not in components:
                            components[c.getName()] = c.getId()

            if version:
                for c in version.getComponents():
                    components[c.getName()] = c.getId()

                if not version.get('ispublished'):
                    version.publish()

        data = []
        for c in components:
            data.append({'label': c, 'value': components[c]})

        return {
            'items': [
                {
                    'label': 'Component to view',
                    'type': 'enumerator',
                    'name': 'component',
                    'data': data
                }
            ]
        }


def register(registry, **kw):
    '''Register action. Called when used as an event plugin.'''
    logging.basicConfig(level=logging.INFO)
    action = Action()
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

    ftrack.setup()
    action = Action()
    action.register()

    ftrack.EVENT_HUB.wait()


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
