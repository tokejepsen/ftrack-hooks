import sys
import argparse
import logging
import os
import getpass
import subprocess
import threading
import traceback

tools_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

if __name__ == '__main__':
    sys.path.append(os.path.join(tools_path, 'ftrack', 'ftrack-api'))

import ftrack


class FFMPEG_thread(threading.Thread):
    def __init__(self, args, user):
        self.stdout = None
        self.stderr = None
        threading.Thread.__init__(self)
        self.args = args
        self.user = user

        self.logger = logging.getLogger(
            __name__ + '.' + self.__class__.__name__
        )

    def run(self):

        job = ftrack.createJob('Syncing with HobSoft', 'running', self.user)

        try:
            subprocess.call(self.args)
        except:
            job.setStatus('failed')

            self.logger.error(traceback.format_exc())
        else:
            job.setStatus('done')


class Action(ftrack.Action):

    #: Action identifier.
    identifier = 'hobsoft_sync'

    #: Action label.
    label = 'Hobsoft Sync'

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
        data = event['data']
        selection = data.get('selection', [])

        if 'values' in event['data']:
            # Do something with the values or return a new form.
            values = event['data']['values']

            if not values['image_component'] or not values['cg_pass']:
                return {'success': False,
                        'message': 'Missing information.'}

            component = ftrack.Component(values['image_component'])

            exe = os.path.join(tools_path, 'ffmpeg', 'bin', 'ffmpeg.exe')

            shot = component.getVersion().getParent().getParent()
            sequence_name = shot.getParent().getName()
            shot_name = 'c' + shot.getName().split('c')[1]
            filename = '{0}{1}.{2}.%04d.jpg'.format(sequence_name, shot_name,
                                                    values['cg_pass'])
            dst = os.path.join('B:\\', 'film', sequence_name, shot_name,
                               'current', values['cg_pass'], filename)

            if not os.path.exists(os.path.dirname(dst)):
                os.makedirs(os.path.dirname(dst))

            args = [exe, '-i', component.getFilesystemPath(), '-qscale:v',
                    '31', dst]

            user = ftrack.User(id=event['source']['user']['id'])
            thread = FFMPEG_thread(args, user)
            thread.start()

            return {
                'success': True,
                'message': 'HobSoft sync launched.'
            }

        # finding image components on versions
        components = {}
        for item in selection:
            asset = None
            version = None

            try:
                task = ftrack.Task(item['entityId'])
                asset = task.getAssets(assetTypes=['img'])[0]
            except:
                version = ftrack.AssetVersion(item['entityId'])

            if asset:
                for c in asset.getVersions()[-1].getComponents():
                    if c.getName() not in components:
                        components[c.getName()] = c.getId()

            if version:
                for c in version.getComponents():
                    components[c.getName()] = c.getId()

                if not version.get('ispublished'):
                    version.publish()

        image_data = []
        for c in components:
            image_data.append({'label': c, 'value': components[c]})

        return {
            'items': [
                {
                    'label': 'Images Component to sync',
                    'type': 'enumerator',
                    'name': 'image_component',
                    'data': image_data
                },
                {
                    'label': 'CG Pass',
                    'type': 'enumerator',
                    'name': 'cg_pass',
                    'data': [{'label': 'CG1', 'value': 'cg1'},
                             {'label': 'CG2', 'value': 'cg2'}]
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
