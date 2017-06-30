import logging
import os
import sys
import getpass
import re
import ntpath
import traceback
import uuid
import subprocess
import tempfile
import threading

logging.basicConfig()
logger = logging.getLogger()

import ftrack


def version_get(string, prefix, suffix=None):
    """Extract version information from filenames.
        Code from Foundry's nukescripts.version_get()
    """

    if string is None:
        raise ValueError("Empty version string - no match")

    regex = "[/_.]"+prefix+"\d+"
    matches = re.findall(regex, string, re.IGNORECASE)
    if not len(matches):
        msg = "No \"_"+prefix+"#\" found in \""+string+"\""
        raise ValueError(msg)
    return (matches[-1:][0][1], re.search("\d+", matches[-1:][0]).group())


def async(fn):
    '''Run *fn* asynchronously.'''
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()
    return wrapper


def generate_title(image_magick_dir, output_file, input_file, size,
                   south_west_text, south_east_text, north_west_text):

    CREATE_NO_WINDOW = 0x08000000
    temp_txt = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()) + '.txt')
    temp_png = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()) + '.png')

    # get width of file
    cmd = os.path.join(image_magick_dir, 'identify.exe')
    cmd += ' -format %wx%h'
    cmd += ' %s[1] > %s' % (input_file, temp_txt)

    # for some reason getting stdout from subprocess.call/Popen doesn't work
    f = open(temp_txt, 'w')
    f.close()
    os.popen(cmd)
    f = open(temp_txt, 'r')
    resolution = f.read()
    f.close()

    # generate empty title image
    args = [os.path.join(image_magick_dir, 'convert.exe'), '-size', resolution,
            'xc:rgba(0,0,0,0)', temp_png]

    subprocess.call(args, creationflags=CREATE_NO_WINDOW)

    args = [os.path.join(image_magick_dir, 'convert.exe'), temp_png,
            '-fill', 'white', '-undercolor', '#00000080', '-gravity',
            'SouthWest', '-pointsize', size, '-annotate', '+0+5',
            ' %s ' % south_west_text,
            '-fill', 'white', '-undercolor', '#00000080', '-gravity',
            'SouthEast', '-pointsize', size, '-annotate', '+0+5',
            ' %s ' % south_east_text,
            '-fill', 'white', '-undercolor', '#00000080', '-gravity',
            'NorthWest', '-pointsize', size, '-annotate', '+0+5',
            ' %s ' % north_west_text,
            output_file]

    subprocess.call(args, creationflags=CREATE_NO_WINDOW)

    # clean up temp files
    os.remove(temp_png)
    os.remove(temp_txt)


@async
def create_job(event):
    values = event['data']['values']
    job = ftrack.createJob('Generating Titles', 'queued',
                           ftrack.User(id=event['source']['user']['id']))
    job.setStatus('running')

    image_magick_dir = r'K:\development\tools\image-magick'
    errors = ''

    # Generateting sources and destinations
    for item in event['data']['selection']:
        try:
            entity = ftrack.AssetVersion(item['entityId'])

            # adding path to errors
            path = ''
            parents = entity.getParents()
            parents.reverse()
            for p in parents:
                path += p.getName() + '/'

            path += 'v' + str(entity.getVersion()).zfill(3)

            input_file = entity.getComponent().getFilesystemPath()
            output_file = ntpath.basename(input_file)

            # get version string
            version_string = '.v' + version_get(input_file, 'v')[1]
            if values['strip_version'] == 'True':
                output_file = output_file.replace(version_string, '')

            # get titles text
            south_west_text = 'Task: "%s"' % path[:-5]
            south_east_text = 'Version: "%s"' % version_string[1:]
            north_west_text = 'Status: "%s"' % entity.getStatus().getName()

            if entity.getAsset().getType().getShort() == 'img':
                src = os.listdir(os.path.dirname(input_file))[0]
                input_file = os.path.join(os.path.dirname(input_file), src)
                output_file = re.sub(r'.%04d', '', output_file)

            output_file = os.path.splitext(output_file)[0] + '.png'
            output_file = os.path.join(values['output_directory'], output_file)

            generate_title(image_magick_dir, output_file, input_file, '25',
                           south_west_text, south_east_text, north_west_text)
        except:
            errors += path + '\n'
            errors += traceback.format_exc() + '\n'

    # generate error report
    if errors:
        temp_txt = os.path.join(values['output_directory'], 'errors.txt')
        f = open(temp_txt, 'w')
        f.write(errors)
        f.close()

    job.setStatus('done')


def launch(event):

    if 'values' in event['data']:
        values = event['data']['values']

        # failures
        if ('output_directory' not in values or
           'strip_version' not in values):
            return {'success': False,
                    'message': 'Missing submit information.'}

        if not os.path.exists(values['output_directory']):
            return {'success': False,
                    'message': "Output Directory doesn't exist."}

        create_job(event)

        msg = 'Generating titles job created.'
        return {'success': True, 'message': msg}

    return {'items': [{'label': 'Output Directory',
                       'type': 'text',
                       'value': '',
                       'name': 'output_directory'},
                      {'label': 'Strip Version',
                       'type': 'enumerator',
                       'name': 'strip_version',
                       'data': [{'label': 'Yes',
                                 'value': 'True'},
                                {'label': 'No',
                                 'value': 'False'}
                                ]}]}


def discover(event):

    data = event['data']

    for item in data['selection']:
        try:
            asset = ftrack.AssetVersion(item['entityId']).getAsset()
            if asset.getType().getShort() not in ['img', 'mov']:
                return
        except:
            return

    return {
        'items': [{
            'label': 'Generate Titles',
            'actionIdentifier': 'generate_titles'
        }]
    }


def register(registry, **kw):
    '''Register location plugin.'''

    # Validate that registry is the correct ftrack.Registry. If not,
    # assume that register is being called with another purpose or from a
    # new or incompatible API and return without doing anything.
    if registry is not ftrack.EVENT_HANDLERS:
        # Exit to avoid registering this plugin again.
        return

    '''Register action.'''
    ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.action.discover and source.user.username={0}'.format(
            getpass.getuser()
        ),
        discover
    )

    ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.action.launch and source.user.username={0} '
        'and data.actionIdentifier={1}'.format(
            getpass.getuser(), 'generate_titles'),
        launch
        )

if __name__ == '__main__':
    logger.setLevel(logging.INFO)

    ftrack.setup()

    '''Register action.'''
    ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.action.discover and source.user.username={0}'.format(
            getpass.getuser()
        ),
        discover
    )

    ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.action.launch and source.user.username={0} '
        'and data.actionIdentifier={1}'.format(
            getpass.getuser(), 'generate_titles'),
        launch
        )

    ftrack.EVENT_HUB.wait()
