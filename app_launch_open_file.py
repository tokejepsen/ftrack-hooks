import logging
import os
import sys
import re
import traceback
import uuid
import shutil

logging.basicConfig()
logger = logging.getLogger()

if __name__ == '__main__':
    tools_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.append(os.path.join(tools_path, 'ftrack', 'ftrack-api'))

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


def get_task_data(event):

    data = event['data']
    app_id = event['data']['application']['identifier']

    # finding work files to open
    path = None
    try:
        asset = None
        component = None

        # search for asset with same name as task
        task = ftrack.Task(data['context']['selection'][0]['entityId'])
        for a in task.getAssets(assetTypes=['scene']):
            if a.getName().lower() == task.getName().lower():
                asset = a

        component_name = '%s_work' % app_id

        for v in reversed(asset.getVersions()):
            if not v.get('ispublished'):
                v.publish()

            for c in v.getComponents():
                if c.getName() == component_name:
                    component = c

            if component:
                break

        current_path = component.getFilesystemPath()
        logger.info('Component path: %s' % current_path)

        # get current file data
        current_dir = os.path.dirname(current_path)
        prefix = os.path.basename(current_path).split('v')[0]
        extension = os.path.splitext(current_path)[1]
        max_version = int(version_get(current_path, 'v')[1])

        # comparing against files in the same directory
        new_version = False
        new_basename = None
        for f in os.listdir(current_dir):
            basename = os.path.basename(f)
            f_prefix = os.path.basename(basename).split('v')[0]
            if f_prefix == prefix and basename.endswith(extension):
                if int(version_get(f, 'v')[1]) > max_version:
                    new_version = True
                    max_version = int(version_get(f, 'v')[1])
                    new_basename = f

        if new_version:
            path = os.path.join(current_dir, new_basename)
        else:
            path = current_path
    except:
        msg = "Couldn't find any scene to launch:"
        msg += " %s" % traceback.format_exc()
        logger.info(msg)

    # find latest non-published work file
    if path:
        version_string = 'v' + str(max_version).zfill(3)
        ext = os.path.splitext(current_path)[1]
        path_dir = os.path.dirname(path)
        files = []
        for f in os.listdir(path_dir):
            if version_string in f and f.endswith(ext):
                files.append(os.path.join(path_dir, f))

        file_path = max([f for f in files], key=os.path.getctime)
        logger.info('Found path: %s' % file_path)

        data['command'].append(file_path)

    # creating inital scene for celaction
    if not path and app_id == 'celaction':
        dst = os.path.join(os.path.expanduser("~"), str(uuid.uuid4()) + '.scn')
        src = os.path.join(os.path.dirname(__file__), 'celaction.scn')

        shutil.copy(src, dst)
        data['command'].append(dst)

    # opening component for djv view
    if not path and app_id in ['djvview', 'quicktime']:
        data = get_assetversion_data(event)

    return data


def get_assetversion_data(event):
    data = event['data']

    if 'values' in event['data']['context']:
        component_id = event['data']['context']['values']['component']
        component = ftrack.Component(component_id)
        file_path = component.getFilesystemPath()

        # if its an image sequence,
        # pick out a random file in the folder to begin with
        version_type = component.getVersion().getAsset().getType()
        if version_type.getShort() == 'img':
            extension = os.path.splitext(file_path)[1]

            random_file = None
            for f in os.listdir(os.path.dirname(file_path)):
                if f.endswith(extension):
                    dir_path = os.path.dirname(file_path)
                    random_file = os.path.join(dir_path, f)

            if random_file:
                file_path = random_file

        data['command'].append(file_path)

    return data


def modify_application_launch(event):
    '''Modify the application launch command with potential files to open'''

    data = event['data']
    entityType = event['data']['context']['selection'][0]['entityType']

    # task based actions
    if entityType == 'task':
        data = get_task_data(event)

    # assetversion based actions
    if entityType == 'assetversion':
        data = get_assetversion_data(event)

    return data


def register(registry, **kw):
    '''Register location plugin.'''

    # Validate that registry is the correct ftrack.Registry. If not,
    # assume that register is being called with another purpose or from a
    # new or incompatible API and return without doing anything.
    if registry is not ftrack.EVENT_HANDLERS:
        # Exit to avoid registering this plugin again.
        return

    ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.connect.application.launch',
        modify_application_launch
    )

if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)

    ftrack.setup()

    ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.connect.application.launch',
        modify_application_launch)
    ftrack.EVENT_HUB.wait()
