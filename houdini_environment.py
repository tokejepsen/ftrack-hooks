import logging
import os
import sys

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

    app_id = event['data']['application']['identifier']

    # skipping all applications except for houdini
    if not app_id.startswith('houdini'):
        return

    environment = {}
    tools_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    pyblish_path = os.path.join(tools_path, 'pyblish')

    # setup PYTHONPATH
    environment['PYTHONPATH'] = [os.path.join(pyblish_path, 'pyblish-houdini')]

    # adding pyblish application and task environment
    env_vars = []
    app_plugins = os.path.join(pyblish_path, 'pyblish-kredenc',
                               'pyblish_kredenc', 'plugins',
                               app_id.split('_')[0])
    env_vars.append(app_plugins)

    path = os.path.join(pyblish_path, 'pyblish-bumpybox', 'pyblish_bumpybox',
                        'plugins', 'houdini', 'pipeline_specific')
    env_vars.append(path)

    environment['PYBLISHPLUGINPATH'] = env_vars

    # setup pyblish
    environment['HOUDINI_PATH'] = [os.path.join(pyblish_path,
                                                'pyblish-houdini',
                                                'pyblish_houdini',
                                                'houdini_path'),
                                   os.path.join(pyblish_path,
                                                'pyblish-bumpybox',
                                                'pyblish_bumpybox',
                                                'environment_variables',
                                                'houdini_path'),
                                   '&']

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
    logger.setLevel(logging.INFO)

    ftrack.setup()

    ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.connect.application.launch',
        modify_application_launch)
    ftrack.EVENT_HUB.wait()
