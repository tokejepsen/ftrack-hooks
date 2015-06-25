import sys
import argparse
import logging
import os
import getpass
import pprint
import subprocess

sys.path.append(r'K:\tools\FTrack\ftrack-api')

import ftrack


class DJVViewer(ftrack.Action):
    '''Custom action.'''

    #: Action identifier.
    identifier = 'djvviewer'

    #: Action label.
    label = 'DJV Viewer'


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

    def discover(self, event):
        task = ftrack.Task(event['data']['selection'][0]['entityId'])
        type_name = task.getType().getName()
        asset = None
        for a in task.getAssets(assetTypes=[type_name]):
            if a.getName().lower() == task.getName().lower():
                asset = a

        component = asset.getVersions()[-1].getComponent('nukescript')
        path = component.getFilesystemPath()

        self.log.info(path)

    def launch(self, event):
        return

def register(registry, **kw):
    '''Register action. Called when used as an event plugin.'''
    logging.basicConfig(level=logging.INFO)
    action = DJVViewer()
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
    action = DJVViewer()
    action.register()

    ftrack.EVENT_HUB.wait()


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
