import logging
import json
import os
import platform
import re
import ftrack
import ftrack_api

logging.basicConfig()
logger = logging.getLogger()


def load_env(path):
    """Load options json from path"""

    with open(path, "r") as f:
        return json.load(f)


def appendPath(path, key, environment):
    '''Append *path* to *key* in *environment*.'''
    try:
        environment[key] = (
            os.pathsep.join([
                environment[key], str(path)
            ])
        )
    except KeyError:
        environment[key] = str(path)

    return environment


def dynamic_environment(event):
    '''Modify the application environment.'''
    data = event['data']
    app = data['application']

    logger.info('APP INFO:{}'.format(app))

    taskid = data['context']['selection'][0].get('entityId')
    session = ftrack_api.Session()
    task = session.query('Task where id is {0}'.format(taskid)).one()

    # get location of json environmnets from env var
    try:
        env_paths = os.environ['FTRACK_APP_ENVIRONMENTS'].split(os.pathsep)
    except KeyError:
        raise KeyError(
                '"FTRACK_APP_ENVIRONMENTS" environment variable not found. '
                'Please create it and point it to a folder with your .json '
                'config files.'
             )

    env_files = []
    for env_path in env_paths:

        # Adding platform and application environment files.
        env_files.append(
            os.path.join(env_path, platform.system().lower() + ".json")
        )
        env_files.append(
            os.path.join(
                env_path,
                "{0}_{1}.json".format(
                    platform.system().lower(), app["identifier"]
                )
            )
        )

        # Collect the first valid "environment" attribute from the selected
        # entity up to the project.
        enviro_attr = None
        for item in reversed(task['link']):
            entity = session.get(item['type'], item['id'])
            # check if the attribute is empty, if not use it
            if bool(entity['custom_attributes']['environment'].rstrip()):
                enviro_attr = entity['custom_attributes']['environment']
                # Stop the hierarchy traversal when an environmnent is found.
                break

        if enviro_attr:
            logger.debug('ENVIRO Attr:{}'.format(enviro_attr))

            # Construct the path to corresponding json files by adding
            # platform, application and item.
            environment_string = "_".join([
                platform.system().lower(), app["identifier"]
            ])
            for item in enviro_attr.split(','):
                env_files.append(
                    os.path.join(
                        env_path,
                        "{0}_{1}.json".format(environment_string, item)
                    )
                )
        else:
            logger.info('No additional environment found.')

    # loop through config files
    for env_file in env_files:
        try:
            logger.debug('Adding {} to the environment'.format(env_file))
            env_add = load_env(env_file)
        except IOError:
            logger.debug('Unable to find the environment file.')
            logger.debug('Make sure that {} exists.'.format(env_file))
            env_add = []

        # Add each path in config file to the environment
        for variable in env_add:
            for path in env_add[variable]:
                keys = re.findall(r'{.*?}', path)
                for key in keys:
                    found_key = os.path.abspath(os.environ.get(key[1:-1]))
                    path = path.replace(key, found_key)
                appendPath(path, str(variable), data['options']['env'])


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
        dynamic_environment
    )
