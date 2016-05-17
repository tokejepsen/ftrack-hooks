# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

import getpass
import sys
import pprint
import logging
import re
import os
import argparse
import traceback
import _winreg
import threading
import subprocess
import time
import shutil
import platform

tools_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
ftrack_connect_path = os.path.join(tools_path, 'ftrack',
                                   'ftrack-connect_package', 'windows',
                                   'current')

if __name__ == '__main__':
    sys.path.append(os.path.join(tools_path, 'ftrack', 'ftrack-api'))
    sys.path.append(os.path.join(r'C:\Users\toke.jepsen\Desktop\library'))

    path = os.path.join(tools_path, 'pyblish', 'pyblish')
    path += os.pathsep + os.path.join(tools_path, 'pyblish',
                                      'pyblish-bumpybox')
    path += os.pathsep + os.path.join(tools_path, 'pyblish',
                                      'pyblish-ftrack')
    path += os.pathsep + os.path.join(tools_path, 'pyblish',
                                      'pyblish-deadline')
    path += os.pathsep + os.path.join(tools_path, 'pyblish',
                                      'pyblish-integration')
    path += os.pathsep + os.path.join(tools_path, 'pyblish',
                                      'pyblish-qml')
    path += os.pathsep + os.path.join(tools_path, 'pyblish',
                                      'pyblish-rpc')
    path += os.pathsep + os.path.join(tools_path, 'pyblish',
                                      'python-qt5')
    path += os.pathsep + os.path.join(tools_path, 'ftrack',
                                      'ftrack-hooks')
    os.environ['PYTHONPATH'] = path

import ftrack
import ftrack_api
import ftrack_connect.application


class ApplicationThread(threading.Thread):
    def __init__(self, launcher, applicationIdentifier, context, task):
        self.stdout = None
        self.stderr = None
        threading.Thread.__init__(self)
        self.launcher = launcher
        self.applicationIdentifier = applicationIdentifier
        self.context = context
        self.task = task

        self.logger = logging.getLogger(
            __name__ + '.' + self.__class__.__name__
        )

    def run(self):

        self.logger.info('start time log')

        timelog = ftrack.createTimelog(1, contextId=self.task.getId())
        start_time = time.time()

        self.launcher.launch(self.applicationIdentifier, self.context)

        duration = time.time() - start_time
        timelog.set('duration', value=duration)

        self.logger.info('end time log')


class LaunchApplicationAction(object):
    '''Discover and launch nuke.'''

    identifier = 'ftrack-connect-launch-celaction'

    def __init__(self, application_store, launcher):
        '''Initialise action with *applicationStore* and *launcher*.

        *applicationStore* should be an instance of
        :class:`ftrack_connect.application.ApplicationStore`.

        *launcher* should be an instance of
        :class:`ftrack_connect.application.ApplicationLauncher`.

        '''
        super(LaunchApplicationAction, self).__init__()

        self.logger = logging.getLogger(
            __name__ + '.' + self.__class__.__name__
        )

        self.application_store = application_store
        self.launcher = launcher

    def GetTaskFilename(self, task_id, ext):

        session = ftrack_api.Session()
        task = session.query('Task where id is "%s"' % task_id).one()
        path = []
        parents = task['link']
        project = session.query('Project where id is "%s"' % parents[0]['id'])

        disk = project.one()['disk']['windows']
        if platform.system().lower() != 'windows':
            disk = project.one()['disk']['unix']
        path.append(disk)

        path.append(project.one()['root'])

        root_folder = []
        for p in parents[1:]:
            tc = session.query('TypedContext where id is "%s"' % p['id']).one()
            path.append(tc['name'].lower())

            if tc['object_type']['name'] == 'Episode':
                root_folder.append('episodes')
            if tc['object_type']['name'] == 'Sequence':
                root_folder.append('sequences')
            if tc['object_type']['name'] == 'Shot':
                root_folder.append('shots')
        root_folder.append('tasks')
        path.insert(2, root_folder[0])

        filename = [parents[-2]['name'], parents[-1]['name'], 'v001', ext]
        path.append('.'.join(filename))

        return os.path.join(*path).replace('\\', '/')

    # newer version pop-up
    def version_get(self, string, prefix, suffix = None):
        """Extract version information from filenames.  Code from Foundry's nukescripts.version_get()"""

        if string is None:
            raise ValueError, "Empty version string - no match"

        regex = "[/_.]"+prefix+"\d+"
        matches = re.findall(regex, string, re.IGNORECASE)
        if not len(matches):
            msg = "No \"_"+prefix+"#\" found in \""+string+"\""
            raise ValueError, msg
        return (matches[-1:][0][1], re.search("\d+", matches[-1:][0]).group())

    def is_valid_selection(self, selection):
        '''Return true if the selection is valid.'''
        if (
            len(selection) != 1 or
            selection[0]['entityType'] != 'task'
        ):
            return False

        entity = selection[0]
        task = ftrack.Task(entity['entityId'])

        if task.getObjectType() != 'Task':
            return False

        return True

    def register(self):
        '''Register discover actions on logged in user.'''
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
        '''Return discovered applications.'''

        if not self.is_valid_selection(
            event['data'].get('selection', [])
        ):
            return

        items = []
        applications = self.application_store.applications
        applications = sorted(
            applications, key=lambda application: application['label']
        )

        for application in applications:
            application_identifier = application['identifier']
            label = application['label']
            items.append({
                'actionIdentifier': self.identifier,
                'label': label,
                'icon': application.get('icon', 'default'),
                'applicationIdentifier': application_identifier
            })

        return {
            'items': items
        }

    def launch(self, event):
        '''Handle *event*.

        event['data'] should contain:

            *applicationIdentifier* to identify which application to start.

        '''
        # Prevent further processing by other listeners.
        event.stop()

        if not self.is_valid_selection(
            event['data'].get('selection', [])
        ):
            return

        applicationIdentifier = event['data']['applicationIdentifier']
        context = event['data'].copy()
        context['source'] = event['source']

        task = ftrack.Task(event['data']['selection'][0]['entityId'])

        # getting path to file
        path = ''
        try:
            asset = None
            component = None

            # search for asset with same name as task
            for a in task.getAssets(assetTypes=['scene']):
                if a.getName().lower() == task.getName().lower():
                    asset = a

            component_name = 'celaction_work'

            for v in reversed(asset.getVersions()):
                if not v.get('ispublished'):
                    v.publish()

                for c in v.getComponents():
                    if c.getName() == component_name:
                        component = c

                if component:
                    break

            current_path = component.getFilesystemPath()
            self.logger.info('Component path: %s' % current_path)

            # get current file data
            current_dir = os.path.dirname(current_path)
            prefix = os.path.basename(current_path).split('v')[0]
            extension = os.path.splitext(current_path)[1]
            max_version = int(self.version_get(current_path, 'v')[1])

            # comparing against files in the same directory
            new_version = False
            new_basename = None
            for f in os.listdir(current_dir):
                basename = os.path.basename(f)
                f_prefix = os.path.basename(basename).split('v')[0]
                if f_prefix == prefix and basename.endswith(extension):
                    if int(self.version_get(f, 'v')[1]) > max_version:
                        new_version = True
                        max_version = int(self.version_get(f, 'v')[1])
                        new_basename = f

            if new_version:
                path = os.path.join(current_dir, new_basename)
            else:
                path = current_path
        except:
            msg = "Couldn't find any file to launch:"
            msg += " %s" % traceback.format_exc()
            self.logger.info(msg)

        if path:
            version_string = 'v' + str(max_version).zfill(3)
            ext = os.path.splitext(current_path)[1]
            path_dir = os.path.dirname(path)
            files = []
            for f in os.listdir(path_dir):
                if version_string in f and f.endswith(ext):
                    files.append(os.path.join(path_dir, f))

            path = max([f for f in files], key=os.path.getctime)
            self.logger.info('Found path: %s' % path)
        else:
            self.logger.info('Copy default celaction file.')
            src = os.path.join(os.path.dirname(__file__), 'celaction.scn')
            dst = self.GetTaskFilename(task.getId(), 'scn')

            # create folder if they don't exists
            if not os.path.exists(os.path.dirname(dst)):
                os.makedirs(os.path.dirname(dst))

            # copy default celaction file if it doesn't exists
            if not os.path.exists(dst):
                shutil.copy(src, dst)

            path = dst

        # adding application and task environment
        environment = {}

        tools_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        pyblish_path = os.path.join(tools_path, 'pyblish')

        app_plugins = os.path.join(pyblish_path, 'pyblish-bumpybox',
                                   'pyblish_bumpybox', 'plugins',
                                   applicationIdentifier.split('_')[0])

        task_plugins = os.path.join(app_plugins,
                                    task.getType().getName().lower())

        data = [os.path.join(pyblish_path, 'pyblish-ftrack',
                             'pyblish_ftrack', 'plugins')]
        data.append(os.path.join(pyblish_path, 'pyblish-deadline',
                                 'pyblish_deadline', 'plugins'))
        data.append(os.path.join(pyblish_path, 'pyblish-bumpybox',
                                 'pyblish_bumpybox', 'plugins'))
        data.append(app_plugins)
        data.append(task_plugins)

        environment['PYBLISHPLUGINPATH'] = data

        context['environment'] = environment

        # launching the app
        applicationStore = ApplicationStore()
        applicationStore._modifyApplications(path)

        path = os.path.join(ftrack_connect_path, 'resource',
                            'ftrack_connect_nuke')
        launcher = ApplicationLauncher(applicationStore,
                                    plugin_path=os.environ.get(
                                    'FTRACK_CONNECT_NUKE_PLUGINS_PATH', path))

        # modify registry settings
        hKey = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER,
                               r'Software\CelAction\CelAction2D\User Settings',
                               0, _winreg.KEY_ALL_ACCESS)

        pyblish_path = os.path.join(pyblish_path, 'pyblish_standalone.bat')
        _winreg.SetValueEx(hKey, 'SubmitAppTitle', 0, _winreg.REG_SZ,
                           pyblish_path)

        parameters = ' --path *SCENE* -d chunk *CHUNK* -d start *START*'
        parameters += ' -d end *END* -d x *X* -d y *Y*'
        _winreg.SetValueEx(hKey, 'SubmitParametersTitle', 0,
                           _winreg.REG_SZ, parameters)

        myclass = ApplicationThread(launcher, applicationIdentifier, context,
                                    task)
        myclass.start()

        msg = 'Launched %s!' % applicationIdentifier
        ftrack.EVENT_HUB.publishReply(event,
                                      data={'success': True,
                                            'message': msg})


class ApplicationStore(ftrack_connect.application.ApplicationStore):

    def _modifyApplications(self, path=''):
        self.applications = self._discoverApplications(path=path)

    def _discoverApplications(self, path=''):
        '''Return a list of applications that can be launched from this host.

        An application should be of the form:

            dict(
                'identifier': 'name_version',
                'label': 'Name version',
                'path': 'Absolute path to the file',
                'version': 'Version of the application',
                'icon': 'URL or name of predefined icon'
            )

        '''
        applications = []

        launchArguments = []
        if path:
            launchArguments.append(path)

        if sys.platform == 'win32':

            applications.extend(self._searchFilesystem(
                expression=['C:\\', 'Program Files*', 'CelAction',
                'CelAction2D.exe'],
                label='CelAction',
                applicationIdentifier='celaction',
                icon='https://pbs.twimg.com/profile_images/3741062735/e0b8fce362e6b3ff7414f4cdfa1a4a75_400x400.png',
                launchArguments=launchArguments
            ))

        self.logger.debug(
            'Discovered applications:\n{0}'.format(
                pprint.pformat(applications)
            )
        )

        return applications


class ApplicationLauncher(ftrack_connect.application.ApplicationLauncher):
    '''Custom launcher to modify environment before launch.'''

    def __init__(self, application_store, plugin_path):
        '''.'''
        super(ApplicationLauncher, self).__init__(application_store)

        self.plugin_path = plugin_path

    def launch(self, applicationIdentifier, context=None):
        '''Launch application matching *applicationIdentifier*.

        *context* should provide information that can guide how to launch the
        application.

        Return a dictionary of information containing:

            success - A boolean value indicating whether application launched
                      successfully or not.
            message - Any additional information (such as a failure message).

        '''
        # Look up application.
        applicationIdentifierPattern = applicationIdentifier
        if applicationIdentifierPattern == 'hieroplayer':
            applicationIdentifierPattern += '*'

        application = self.applicationStore.getApplication(
            applicationIdentifierPattern
        )

        if application is None:
            return {
                'success': False,
                'message': (
                    '{0} application not found.'
                    .format(applicationIdentifier)
                )
            }

        # Construct command and environment.
        command = self._getApplicationLaunchCommand(application, context)
        environment = self._getApplicationEnvironment(application, context)

        # Environment must contain only strings.
        self._conformEnvironment(environment)

        success = True
        message = '{0} application started.'.format(application['label'])

        try:
            options = dict(
                env=environment,
                close_fds=True
            )

            # Ensure that current working directory is set to the root of the
            # application being launched to avoid issues with applications
            # locating shared libraries etc.
            applicationRootPath = os.path.dirname(application['path'])
            options['cwd'] = applicationRootPath

            # Ensure subprocess is detached so closing connect will not also
            # close launched applications.
            if sys.platform == 'win32':
                options['creationflags'] = subprocess.CREATE_NEW_CONSOLE
            else:
                options['preexec_fn'] = os.setsid

            self.logger.info(
                'Launching {0} with options {1}'.format(command, options)
            )
            process = subprocess.Popen(command, **options)
            process.wait()

        except (OSError, TypeError):
            self.logger.exception(
                '{0} application could not be started with command "{1}".'
                .format(applicationIdentifier, command)
            )

            success = False
            message = '{0} application could not be started.'.format(
                application['label']
            )

        else:
            self.logger.debug(
                '{0} application started. (pid={1})'.format(
                    applicationIdentifier, process.pid
                )
            )

        return {
            'success': success,
            'message': message
        }

    def _getApplicationEnvironment(
        self, application, context=None
    ):
        '''Override to modify environment before launch.'''

        # Make sure to call super to retrieve original environment
        # which contains the selection and ftrack API.
        environment = super(
            ApplicationLauncher, self
        )._getApplicationEnvironment(application, context)

        for k in context['environment']:
            path = ''
            for p in context['environment'][k]:
                path += os.pathsep + p

            environment[k] = path[1:]

        entity = context['selection'][0]
        task = ftrack.Task(entity['entityId'])
        taskParent = task.getParent()

        try:
            environment['FS'] = str(int(taskParent.getFrameStart()))
        except Exception:
            environment['FS'] = '1'

        try:
            environment['FE'] = str(int(taskParent.getFrameEnd()))
        except Exception:
            environment['FE'] = '1'

        environment['FTRACK_TASKID'] = task.getId()
        environment['FTRACK_SHOTID'] = task.get('parent_id')

        nuke_plugin_path = os.path.abspath(
            os.path.join(
                self.plugin_path, 'nuke_path'
            )
        )
        environment = ftrack_connect.application.appendPath(
            nuke_plugin_path, 'NUKE_PATH', environment
        )

        nuke_plugin_path = os.path.abspath(
            os.path.join(
                self.plugin_path, 'ftrack_connect_nuke'
            )
        )
        environment = ftrack_connect.application.appendPath(
            self.plugin_path, 'FOUNDRY_ASSET_PLUGIN_PATH', environment
        )

        environment['NUKE_USE_FNASSETAPI'] = '1'

        return environment

"""
def register(registry, **kw):
    '''Register hooks.'''

    # Create store containing applications.
    application_store = ApplicationStore()

    path = os.path.join(ftrack_connect_path, 'resource',
                        'ftrack_connect_nuke')
    launcher = ApplicationLauncher(application_store,
                                plugin_path=os.environ.get(
                                'FTRACK_CONNECT_NUKE_PLUGINS_PATH', path))

    # Create action and register to respond to discover and launch actions.
    action = LaunchApplicationAction(application_store, launcher)
    action.register()
"""

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
    log = logging.getLogger()

    ftrack.setup()

    # Create store containing applications.
    application_store = ApplicationStore()

    path = os.path.join(ftrack_connect_path, 'resource',
                        'ftrack_connect_nuke')
    launcher = ApplicationLauncher(application_store,
                                plugin_path=os.environ.get(
                                'FTRACK_CONNECT_NUKE_PLUGINS_PATH', path))

    # Create action and register to respond to discover and launch actions.
    action = LaunchApplicationAction(application_store, launcher)
    action.register()

    ftrack.EVENT_HUB.wait()


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
