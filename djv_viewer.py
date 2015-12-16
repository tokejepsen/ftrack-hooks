import sys
import argparse
import logging
import os
import getpass
import subprocess
import re
import threading
import time

tools_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

if __name__ == '__main__':
    sys.path.append(os.path.join(tools_path, 'ftrack', 'ftrack-api'))

import ftrack


class ApplicationThread(threading.Thread):
    def __init__(self, path, task):
        self.stdout = None
        self.stderr = None
        threading.Thread.__init__(self)
        self.task = task
        self.path = path

        self.logger = logging.getLogger(
            __name__ + '.' + self.__class__.__name__
        )

    def run(self):

        self.logger.info('start time log')

        timelog = ftrack.createTimelog(1, contextId=self.task.getId())
        start_time = time.time()

        ext = os.path.splitext(self.path)[1]

        files = []
        if '%' in self.path:
            head = os.path.basename(self.path).split('%')[0]
            padding = int(os.path.basename(self.path).split('%')[1][0:2])
            tail = os.path.basename(self.path).split('%')[1][3:]
            pattern = r'%s[0-9]{%s}%s' % (head, padding, tail)

            for f in os.listdir(os.path.dirname(self.path)):
                if re.findall(pattern, f):
                    dir_path = os.path.dirname(self.path)
                    files.append(os.path.join(dir_path, f))
        else:
            for f in os.listdir(os.path.dirname(self.path)):
                if f.endswith(ext):
                    dir_path = os.path.dirname(self.path)
                    files.append(os.path.join(dir_path, f))

        path = os.path.join(tools_path, 'djv-viewer',
                'djv-1.1.0-Windows-64', 'bin', 'djv_view.exe')
        args = [path, files[0]]
        process = subprocess.Popen(args)
        process.wait()

        duration = time.time() - start_time
        timelog.set('duration', value=duration)

        self.logger.info('end time log')


class DJVViewer(ftrack.Action):
    ''' Finds the last 3 versions of image sequences and movies,
     to present to the user for review '''

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

            name = asset_version.getAsset().getType().getShort()
            if name not in ['img', 'mov']:
                return False

        return True

    def discover(self, event):

        if not self.is_valid_selection(event['data'].get('selection', [])):
            return

        return {
            'items': [{
                'label': self.label,
                'actionIdentifier': self.identifier,
                'icon': "http://a.fsdn.com/allura/p/djv/icon"
            }]
        }

    def launch(self, event):
        data = event['data']
        selection = data.get('selection', [])

        if 'values' in event['data']:
            # Do something with the values or return a new form.
            values = event['data']['values']

            # opening image component
            if values['image_component']:
                component = ftrack.Component(values['image_component'])

                task = component.getVersion().getParent().getParent()
                myclass = ApplicationThread(component.getFilesystemPath(), task)
                myclass.start()

            # opening image component
            if values['movie_component']:
                component = ftrack.Component(values['movie_component'])

                task = component.getVersion().getParent().getParent()
                myclass = ApplicationThread(component.getFilesystemPath(), task)
                myclass.start()

            return {
                'success': True,
                'message': 'DJV Viewer launched.'
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

        # finding movie components on versions
        components = {}
        for item in selection:
            asset = None
            version = None

            try:
                task = ftrack.Task(item['entityId'])
                asset = task.getAssets(assetTypes=['mov'])[0]
            except:
                try:
                    version = ftrack.AssetVersion(item['entityId'])
                except:
                    continue

            if asset:
                for c in asset.getVersions()[-1].getComponents():
                    if c.getName() not in components:
                        components[c.getName()] = c.getId()

            if version:
                for c in version.getComponents():
                    components[c.getName()] = c.getId()

                if not version.get('ispublished'):
                    version.publish()

        movie_data = []
        for c in components:
            movie_data.append({'label': c, 'value': components[c]})

        return {
            'items': [
                {
                    'label': 'Images Component to view',
                    'type': 'enumerator',
                    'name': 'image_component',
                    'data': image_data
                },
                {
                    'label': 'Movie Component to view',
                    'type': 'enumerator',
                    'name': 'movie_component',
                    'data': movie_data
                }
            ]
        }


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
