import os
import sys
import argparse
import logging
import getpass

tools_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

if __name__ == '__main__':
    sys.path.append(os.path.join(tools_path, 'ftrack', 'ftrack-api'))

import ftrack


class Action(ftrack.Action):
    ''' Finds the last 3 versions of image sequences and movies,
     to present to the user for review '''

    #: Action identifier.
    identifier = 'thumbnail-updater'

    label = 'Thumbnail Updater'

    def __init__(self):
        '''Initialise action with *applicationStore* and *launcher*.

        *applicationStore* should be an instance of
        :class:`ftrack_connect.application.ApplicationStore`.

        *launcher* should be an instance of
        :class:`ftrack_connect.application.ApplicationLauncher`.

        '''
        super(Action, self).__init__()

        self.logger = logging.getLogger(
            __name__ + '.' + self.__class__.__name__
        )

    def isValidSelection(self, selection):
        '''Return true if the selection is valid.

        Legacy plugins can only be started from a single Task.

        '''
        if selection[0]['entityType'] != 'task':
            return False

        entity = selection[0]
        task = ftrack.Task(entity['entityId'])

        if task.getObjectType() != 'Task':
            return False

        return True

    def register(self):
        '''Override register to filter discover actions on logged in user.'''
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
        if not self.isValidSelection(
            event['data'].get('selection', [])
        ):
            return

        return {
            'items': [{
                'label': self.label,
                'actionIdentifier': self.identifier
            }]
        }

    def launch(self, event):

        # Prevent further processing by other listeners.
        event.stop()

        if not self.isValidSelection(
            event['data'].get('selection', [])
        ):
            return

        for entity in event['data']['selection']:
            task = ftrack.Task(entity['entityId'])

            parent = task.getParent()
            if parent.get('thumbid') and not task.get('thumbid'):
                task.set('thumbid', value=parent.get('thumbid'))

        return {
            'success': True,
            'message': 'Thumbnails updated!'
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
