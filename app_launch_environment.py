import logging
import os
import sys
import re
import traceback

logging.basicConfig()
logger = logging.getLogger()

if __name__ == '__main__':
    tools_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.append(os.path.join(tools_path, 'ftrack', 'ftrack-api'))

import ftrack


def appendPath(path, key, environment):
    '''Append *path* to *key* in *environment*.'''
    try:
        environment[key] = (
            os.pathsep.join([
                environment[key], path
            ])
        )
    except KeyError:
        environment[key] = path

    return environment


def modify_application_launch(event):
    '''Modify the application environment and start timer for the task.'''

    data = event['data']

    # adding pyblish application and task environment
    environment = {}

    tools_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    pyblish_path = os.path.join(tools_path, 'pyblish')

    app_id = event['data']['application']['identifier']
    app_plugins = os.path.join(pyblish_path, 'pyblish-bumpybox',
                               'pyblish_bumpybox', 'plugins',
                               app_id.split('_')[0])

    task = ftrack.Task(data['context']['selection'][0]['entityId'])
    task_plugins = os.path.join(app_plugins, task.getType().getName().lower())

    data = [os.path.join(pyblish_path, 'pyblish-ftrack', 'pyblish_ftrack',
                         'plugins')]
    data.append(os.path.join(pyblish_path, 'pyblish-deadline',
                             'pyblish_deadline', 'plugins'))
    data.append(os.path.join(pyblish_path, 'pyblish-bumpybox',
                             'pyblish_bumpybox', 'plugins'))
    data.append(app_plugins)
    data.append(task_plugins)

    environment['PYBLISHPLUGINPATH'] = data

    data = event['data']
    for variable in environment:
        for path in environment[variable]:
            appendPath(path, variable, data['options']['env'])

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
