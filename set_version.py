import sys
import argparse
import logging
import os
import getpass
import pprint

if __name__ == '__main__':
    tools_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.append(os.path.join(tools_path, 'ftrack', 'ftrack-api'))

import ftrack


class SetVersion(ftrack.Action):
    '''Custom action.'''

    #: Action identifier.
    identifier = 'version.set'

    #: Action label.
    label = 'SetVersion'


    def __init__(self):
        '''Initialise action handler.'''
        self.logger = logging.getLogger(
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

    def validateSelection(self, selection):
        '''Return true if the selection is valid.

        '''

        if selection:
            return False

        return False


    def discover(self, event):
        '''Return action config if triggered on a single selection.'''
        data = event['data']

        # If selection contains more than one item return early since
        # this action will only handle a single version.
        selection = data.get('selection', [])
        entityType = selection[0]['entityType']
        if len(selection) != 1 or entityType != 'assetversion':
            return

        return {
            'items': [{
                'label': self.label,
                'actionIdentifier': self.identifier,
            }]
        }


    def launch(self, event):
        if 'values' in event['data']:
            # Do something with the values or return a new form.
            values = event['data']['values']

            data = event['data']
            selection = data.get('selection', [])
            version = ftrack.AssetVersion(selection[0]['entityId'])

            success = True
            msg = 'Increased version number.'

            if not values['version_number']:
                success = False
                msg = 'No number was submitted.'
            else:
                if int(values['version_number']) <= 0:
                    success = False
                    msg = 'Negative or zero is not valid.'
                else:
                    version.set('version', int(values['version_number']))

            return {
                'success': success,
                'message': msg
            }

        return {
            'items': [
                {
                    'label': 'Version number',
                    'type': 'number',
                    'name': 'version_number'
                }
            ]
        }


def register(registry, **kw):
    '''Register action. Called when used as an event plugin.'''
    # Validate that registry is the correct ftrack.Registry. If not,
    # assume that register is being called with another purpose or from a
    # new or incompatible API and return without doing anything.
    if registry is not ftrack.EVENT_HANDLERS:
        # Exit to avoid registering this plugin again.
        return

    logging.basicConfig(level=logging.INFO)
    action = SetVersion()
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
    action = SetVersion()
    action.register()

    ftrack.EVENT_HUB.wait()


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
