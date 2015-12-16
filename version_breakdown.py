import sys
import argparse
import logging
import os
import getpass
import tempfile

tools_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

if __name__ == '__main__':
    sys.path.append(os.path.join(tools_path, 'ftrack', 'ftrack-api'))

import ftrack


class Action(ftrack.Action):

    #: Action identifier.
    identifier = 'version_breakdown'

    #: Action label.
    label = 'Version Breakdown'

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

    def discover(self, event):

        selection = event['data'].get('selection', [])

        if selection[0]['entityType'] != 'assetversion':
            return

        return {
            'items': [{
                'label': self.label,
                'actionIdentifier': self.identifier,
            }]
        }

    def launch(self, event):

        msg = 'Breakdown successfull. Click Job for details.'
        ftrack.EVENT_HUB.publishReply(event, data={'success': True,
                                                   'message': msg})

        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, 'ftrack_version_breakdown.txt')
        with open(file_path, 'w') as f:
            output = ''
            v = ftrack.AssetVersion('6dec6756-8f94-11e5-929c-42010af00048')
            output += '/'.join([v.getParent().getParent().getName(),
                                v.getParent().getName(),
                                str(v.getVersion()).zfill(3)])
            output += ':\n'
            count = 0
            sessions = []
            project_id = v.getParents()[-1].getId()
            for session in ftrack.getReviewSessions(project_id):
                for obj in session.getObjects():
                    if obj.get('version_id') == v.getId():
                        count += 1
                        sessions.append(session.get('name'))

            output += '\tSession Usage:\t{0}\n'.format(count)
            output += '\tSessions:\t\t{0}\n'.format(list(set(sessions)))

            f.write(output)

        user = ftrack.User(id=event['source']['user']['id'])
        job = ftrack.createJob('Breakdown', 'done', user)
        job.createAttachment(file_path)


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
