import logging
import json
import os
import platform
import re
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

    enviro_attr = None
    for item in reversed(task['link']):
        entity = session.get(item['type'], item['id'])
        # check if the attribute is empty, if not use it
        if bool(entity['custom_attributes']['environment'].rstrip()):
            enviro_attr = entity['custom_attributes']['environment']
            # Stop the hierarchy traversal when an environmnent is found.
            break

    if not enviro_attr:
        logger.info('No additional environment found.')
        return

    logger.debug('ENVIRO Attr:{}'.format(enviro_attr))

    # Construct base file names from platform, application identifier and item.
    basenames = []
    basenames.append(platform.system().lower())
    for item in enviro_attr.split(','):
        name = platform.system().lower()
        # Joining and splitting by "_" to account for "_" in application
        # identifier and item.
        for split in "_".join([app["identifier"], item]).split("_"):
            name += "_" + split
            if name not in basenames:
                basenames.append(name)

    # Construct environment files from environment paths and basenames.
    env_files = []
    for env_path in env_paths:
        for name in basenames:
            env_files.append(os.path.join(env_path, name + ".json"))

    # loop through config files and check for existence. We traverse the files
    # in reverse to make sure that higher levels of environment variables do
    # not prepend lower level environment variables. For example
    # "windows_maya_2017.json" should come before "windows_maya.json".
    for env_file in reversed(env_files):
        try:
            env_add = load_env(env_file)
            logger.debug('Adding {} to the environment'.format(env_file))
        except IOError:
            logger.debug(
                'Unable to find the environment file: "{}"'.format(env_file)
            )
            env_add = []
        except ValueError as e:
            logger.debug(
                'Unable to read the environment file: "{0}", due to:'
                '\n{1}'.format(env_file, e)
            )
            env_add = []

        # Add each path in config file to the environment
        for variable in env_add:
            for path in env_add[variable]:
                keys = re.findall(r'{.*?}', path)
                for key in keys:
                    found_key = os.path.abspath(os.environ.get(key[1:-1]))
                    path = path.replace(key, found_key)
                appendPath(path, str(variable), data['options']['env'])


def register(session):

    # Validate that session is an instance of ftrack_api.Session. If not,assume
    # that register is being called from an old or incompatible API and return
    # without doing anything.
    if not isinstance(session, ftrack_api.Session):
        return

    session.event_hub.subscribe(
        "topic=ftrack.connect.application.launch",
        dynamic_environment
    )
