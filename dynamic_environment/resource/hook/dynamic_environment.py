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
        # Return early if path already exists.
        if path in environment[key]:
            return environment
        else:
            environment[key] = (
                os.pathsep.join([
                    environment[key], str(path)
                ])
            )
    except KeyError:
        environment[key] = str(path)

    return environment


def modify_launch(event):
    '''Modify the application environment.'''
    data = event['data']
    app = data['application']

    logger.info('APP INFO:{}'.format(app))

    taskid = data['context']['selection'][0].get('entityId')
    session = ftrack_api.Session()
    task = session.query('Task where id is {0}'.format(taskid)).one()

    environment = get_dynamic_environment(session, task, app["identifier"])
    for key, value in environment.iteritems():
        appendPath(value, key, data['options']['env'])


def get_dynamic_environment(session, entity, application_identifier):

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
    for item in reversed(entity['link']):
        entity = session.get(item['type'], item['id'])
        # check if the attribute is empty, if not use it
        if bool(entity['custom_attributes']['environment'].rstrip()):
            enviro_attr = entity['custom_attributes']['environment']
            # Stop the hierarchy traversal when an environmnent is found.
            break
    logger.debug('Environment attribute: {}'.format(enviro_attr))

    # Construct file names from platform, application identifier and item.
    names = []
    # Always search for platform and application identifier environment files.
    name = platform.system().lower()
    names.append(name)
    name += "_" + application_identifier
    names.append(name)
    # Loop through environment attributes and add names.
    if enviro_attr:
        for item in enviro_attr.split(','):
            names.append(name + "_" + item)

    # Construct base file names from names split by "_".
    basenames = []
    for name in names:
        split = name.split("_")
        iteration = []
        for item in split:
            iteration.append(item)
            if "_".join(iteration) not in basenames:
                basenames.append("_".join(iteration))

    # Construct environment files from environment paths and basenames.
    # Reversing the order of the environment paths to make sure they are added
    # in the correct order later.
    env_files = []
    for env_path in reversed(env_paths):
        for name in basenames:
            env_files.append(os.path.join(env_path, name + ".json"))

    # loop through config files and check for existence. We traverse the files
    # in reverse to make sure that higher levels of environment variables do
    # not prepend lower level environment variables. For example
    # "windows_maya_2017.json" should come before "windows_maya.json".
    environment = {}
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
                appendPath(path, str(variable), environment)

    return environment


def register(session):

    # Validate that session is an instance of ftrack_api.Session. If not,assume
    # that register is being called from an old or incompatible API and return
    # without doing anything.
    if not isinstance(session, ftrack_api.Session):
        return

    session.event_hub.subscribe(
        "topic=ftrack.connect.application.launch",
        modify_launch
    )
