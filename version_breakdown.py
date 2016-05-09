import sys
import argparse
import logging
import os
import getpass
import tempfile
import traceback

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

        selection = event['data']['selection']
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, 'ftrack_version_breakdown.txt')
        with open(file_path, 'w') as f:
            output = ''
            v = ftrack.AssetVersion(selection[0]['entityId'])
            versions = v.getAsset().getVersions()
            ids = []

            data = {'None': {'name': 'Uncategorized', 'notes': [],
                    'versions': []}}
            for cate in ftrack.getNoteCategories():
                data[cate.get('entityId')] = {'name': cate.get('name'),
                                              'notes': [], 'versions': []}

            for v in versions:
                ids.append(v.getId())
                for note in v.getNotes():
                    if note.get('categoryid'):
                        data[note.get('categoryid')]['notes'].append(note)
                        data[note.get('categoryid')]['versions'].append(v)
                    else:
                        data['None']['versions'].append(v)
                        data['None']['notes'].append(note)

            output += '/'.join([v.getParent().getParent().getName(),
                                v.getParent().getName()])
            output += ':\n'
            count = 0
            sessions = []
            project_id = v.getParents()[-1].getId()
            for session in ftrack.getReviewSessions(project_id):
                for obj in session.getObjects():
                    if obj.get('version_id') in ids:
                        count += 1
                        sessions.append(session.get('name'))

            output += '\tReview Session Usage:\t{0}\n'.format(count)
            output += '\tReview Sessions:\t{0}\n'.format(list(set(sessions)))

            output += '\tNotes:\n'

            for entry in data:
                output += '\t\t' + data[entry]['name'] + ':\n'
                amount = len(data[entry]['notes'])
                output += '\t\t\tNotes Amount:{0}\n'.format(amount)
                output += '\t\t\tVersions '
                amount = len(set(data[entry]['versions']))
                output += 'Amount:{0}\n'.format(amount)

                for note in data[entry]['notes']:
                    index = data[entry]['notes'].index(note)
                    version_string = data[entry]['versions'][index]
                    version_string = version_string.getVersion()
                    version_string = 'v' + str(version_string).zfill(3)
                    output += '\t\t\t{0}:\n'.format(version_string)
                    text = note.getText().replace('\n', ' ')
                    output += '\t\t\t\t{0}\n'.format(text)

            f.write(output)

        user = ftrack.User(id=event['source']['user']['id'])
        job = ftrack.createJob('Breakdown', 'done', user)
        try:
            job.createAttachment(file_path)
        except:
            self.logger.info(traceback.format_exc())


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
"""
temp_dir = tempfile.gettempdir()
file_path = os.path.join(temp_dir, 'ftrack_version_breakdown.txt')
with open(file_path, 'w') as f:
    output = ''
    v = ftrack.AssetVersion('65a1878a-9db2-11e5-a083-42010af00048')
    versions = v.getAsset().getVersions()
    ids = []

    data = {'None': {'name': 'Uncategorized', 'notes': [], 'versions': []}}
    for cate in ftrack.getNoteCategories():
        data[cate.get('entityId')] = {'name': cate.get('name'), 'notes': [],
                                      'versions': []}

    for v in versions:
        ids.append(v.getId())
        for note in v.getNotes():
            if note.get('categoryid'):
                data[note.get('categoryid')]['notes'].append(note)
                data[note.get('categoryid')]['versions'].append(v)
            else:
                data['None']['versions'].append(v)
                data['None']['notes'].append(note)

    output += '/'.join([v.getParent().getParent().getName(),
                        v.getParent().getName()])
    output += ':\n'
    count = 0
    sessions = []
    project_id = v.getParents()[-1].getId()
    for session in ftrack.getReviewSessions(project_id):
        for obj in session.getObjects():
            if obj.get('version_id') in ids:
                count += 1
                sessions.append(session.get('name'))

    output += '\tReview Session Usage:\t{0}\n'.format(count)
    output += '\tReview Sessions:\t{0}\n'.format(list(set(sessions)))

    output += '\tNotes:\n'

    for entry in data:
        output += '\t\t' + data[entry]['name'] + ':\n'
        output += '\t\t\tNotes Amount:{0}\n'.format(len(data[entry]['notes']))
        output += '\t\t\tVersions '
        output += 'Amount:{0}\n'.format(len(set(data[entry]['versions'])))

        for note in data[entry]['notes']:
            index = data[entry]['notes'].index(note)
            version_string = str(data[entry]['versions'][index].getVersion())
            version_string = 'v' + version_string.zfill(3)
            output += '\t\t\t{0}:\n'.format(version_string)
            text = note.getText().replace('\n', ' ')
            output += '\t\t\t\t{0}\n'.format(text)

    f.write(output)
"""
