# :coding: utf-8
# :copyright: Copyright (c) 2014 ftrack

import os
import getpass
import sys
import pprint
import logging
import re
import argparse
import traceback
import threading
import subprocess
import time


tools_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
ftrack_connect_path = os.path.join(tools_path, 'ftrack',
                                'ftrack-connect_package', 'windows', 'current')

if __name__ == '__main__':
    sys.path.append(os.path.join(tools_path, 'ftrack', 'ftrack-api'))
    sys.path.append(os.path.join(ftrack_connect_path, 'common.zip'))
    sys.path.append(os.path.join(ftrack_connect_path, 'library.zip'))
    os.environ['PYTHONPATH'] = os.path.join(ftrack_connect_path, 'common.zip')

import ftrack
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


class LaunchAction(object):
    '''ftrack connect legacy plugins discover and launch action.'''

    identifier = 'launch-application'

    def __init__(self, applicationStore, launcher):
        '''Initialise action with *applicationStore* and *launcher*.

        *applicationStore* should be an instance of
        :class:`ftrack_connect.application.ApplicationStore`.

        *launcher* should be an instance of
        :class:`ftrack_connect.application.ApplicationLauncher`.

        '''
        super(LaunchAction, self).__init__()

        self.logger = logging.getLogger(
            __name__ + '.' + self.__class__.__name__
        )

        self.applicationStore = applicationStore
        self.launcher = launcher

    def isValidSelection(self, selection):
        '''Return true if the selection is valid.

        Legacy plugins can only be started from a single Task.

        '''
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
        '''Override register to filter discover actions on logged in user.'''
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
        if not self.isValidSelection(
            event['data'].get('selection', [])
        ):
            return

        items = []
        applications = self.applicationStore.applications
        applications = sorted(
            applications, key=lambda application: application['label']
        )

        for application in applications:
            applicationIdentifier = application['identifier']
            label = application['label']
            items.append({
                'actionIdentifier': self.identifier,
                'label': label,
                'icon': application.get('icon', 'default'),
                'applicationIdentifier': applicationIdentifier
            })

        return {
            'items': items
        }

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

    def launch(self, event):
        '''Handle *event*.

        event['data'] should contain:

            *applicationIdentifier* to identify which application to start.

        '''
        # Prevent further processing by other listeners.
        event.stop()

        if not self.isValidSelection(
            event['data'].get('selection', [])
        ):
            return

        applicationIdentifier = (
            event['data']['applicationIdentifier']
        )

        applicationIdentifier = event['data']['applicationIdentifier']
        context = event['data'].copy()
        context['source'] = event['source']

        task = ftrack.Task(event['data']['selection'][0]['entityId'])
        type_name = task.getType().getName()

        # getting path to file
        path = ''
        try:
            asset = None
            component = None

            if task.getAssets(assetTypes=['scene']):

                # search for asset with same name as task
                for a in task.getAssets(assetTypes=['scene']):
                    if a.getName().lower() == task.getName().lower():
                        asset = a

                component_name = applicationIdentifier.split('_')[0] + '_work'

                for v in reversed(asset.getVersions()):
                    if not v.get('ispublished'):
                        v.publish()

                    for c in v.getComponents():
                        if c.getName() == component_name:
                            component = c

                    if component:
                        break
            else:

                assets = task.getAssets(assetTypes=[type_name])

                # if only one asset present, use that asset
                if len(assets) == 1:
                    asset = assets[0]

                # search for asset with same name as task
                for a in task.getAssets(assetTypes=[type_name]):
                    if a.getName().lower() == task.getName().lower():
                        asset = a

                version = asset.getVersions()[-1]
                if not version.get('ispublished'):
                    version.publish()

                if 'nuke' in applicationIdentifier:
                    component = version.getComponent('nukescript')
                if 'maya' in applicationIdentifier:
                    component = version.getComponent('work_file')

            current_path = component.getFilesystemPath()
            self.logger.info('Component path: %s' % current_path)

            # get current file data
            current_dir = os.path.dirname(current_path)
            prefix = os.path.basename(current_path).split('v')[0]
            extension = os.path.splitext(current_path)[1]
            max_version = int(self.version_get(current_path, 'v')[1])
            current_version = max_version

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

        self.logger.info('Found path: %s' % path)

        applicationStore = LegacyApplicationStore()
        applicationStore._modifyApplications(path)

        # adding application and task environment
        environment = {}

        data = []

        tools_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        pyblish_path = os.path.join(tools_path, 'pyblish')

        if 'PYBLISHPLUGINPATH' in os.environ:
            for path in os.environ['PYBLISHPLUGINPATH'].split(os.pathsep):
                data.append(path)
        else:
            data.append(os.path.join(pyblish_path, 'pyblish-ftrack',
                    'pyblish_ftrack','plugins'))
            data.append(os.path.join(pyblish_path, 'pyblish-deadline',
                    'pyblish_deadline','plugins'))
            data.append(os.path.join(pyblish_path, 'pyblish-bumpybox',
                    'pyblish_bumpybox','plugins'))

        app_plugins = os.path.join(pyblish_path, 'pyblish-bumpybox',
                                    'pyblish_bumpybox', 'plugins',
                                    applicationIdentifier.split('_')[0])

        task_plugins = os.path.join(app_plugins,
                                    task.getType().getName().lower())

        data.append(app_plugins)
        data.append(task_plugins)

        environment['PYBLISHPLUGINPATH'] = data

        context['environment'] = environment

        # launching the app
        launcher = LegacyApplicationLauncher(applicationStore,
            legacyPluginsPath=os.path.join(ftrack_connect_path, 'resource',
                                            'legacy_plugins'))

        myclass = ApplicationThread(launcher, applicationIdentifier, context,
                                                                        task)
        myclass.start()

        ftrack.EVENT_HUB.publishReply(event,
            data={
                'success': True,
                'message': 'Launched %s!' % applicationIdentifier
            }
        )


class LegacyApplicationStore(ftrack_connect.application.ApplicationStore):
    '''Discover and store available applications on this host.'''

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
            launchArguments = [path]

        if sys.platform == 'win32':
            prefix = ['C:\\', 'Program Files.*']

            # Specify custom expression for Nuke to ensure the complete version
            # number (e.g. 9.0v3) is picked up.
            nukeVersionExpression = re.compile(
                r'(?P<version>[\d.]+[vabc]+[\dvabc.]*)'
            )

            applications.extend(self._searchFilesystem(
                expression=prefix + ['Autodesk', 'Maya.+', 'bin', 'maya.exe'],
                label='Maya {version}',
                applicationIdentifier='maya_{version}',
                icon='maya',
                launchArguments=launchArguments
            ))

        self.logger.info(
            'Discovered applications:\n{0}'.format(
                pprint.pformat(applications)
            )
        )

        return applications


class LegacyApplicationLauncher(
    ftrack_connect.application.ApplicationLauncher
):
    '''Launch applications with legacy plugin support.'''

    def __init__(self, applicationStore, legacyPluginsPath):
        '''Instantiate launcher with *applicationStore* of applications.

        *applicationStore* should be an instance of :class:`ApplicationStore`
        holding information about applications that can be launched.

        *legacyPluginsPath* should be the path where the legacy plugins are
        located.

        '''
        super(LegacyApplicationLauncher, self).__init__(applicationStore)
        self.legacyPluginsPath = legacyPluginsPath
        self.logger.debug('Legacy plugin path: {0}'.format(
            self.legacyPluginsPath
        ))

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

            self.logger.debug(
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

    def _getApplicationEnvironment(self, application, context):
        '''Modify and return environment with legacy plugins added.'''
        environment = super(
            LegacyApplicationLauncher, self
        )._getApplicationEnvironment(
            application, context
        )

        applicationIdentifier = application['identifier']

        for k in context['environment']:
            path = ''
            for p in context['environment'][k]:
                path += os.pathsep + p

            environment[k] = path[1:]

        isNuke = applicationIdentifier.startswith('nuke')
        isMaya = applicationIdentifier.startswith('maya')
        isHiero = (
            applicationIdentifier.startswith('hiero') and
            'player' not in applicationIdentifier
        )

        if (
            os.path.isdir(self.legacyPluginsPath) and
            (isNuke or isMaya or isHiero)
        ):
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

            includeFoundryAssetManager = False

            # Append legacy plugin base to PYTHONPATH.
            environment = ftrack_connect.application.appendPath(
                self.legacyPluginsPath, 'PYTHONPATH', environment
            )

            # Load Nuke specific environment such as legacy plugins.
            if isNuke:
                nukePluginPath = os.path.join(
                    self.legacyPluginsPath, 'ftrackNukePlugin'
                )

                environment = ftrack_connect.application.appendPath(
                    nukePluginPath, 'NUKE_PATH', environment
                )

                includeFoundryAssetManager = True

            # Load Hiero plugins if application is Hiero.
            if isHiero:
                hieroPluginPath = os.path.join(
                    self.legacyPluginsPath, 'ftrackHieroPlugin'
                )

                environment = ftrack_connect.application.appendPath(
                    hieroPluginPath, 'HIERO_PLUGIN_PATH', environment
                )

                includeFoundryAssetManager = True

            # Load Maya specific environment such as legacy plugins.
            if isMaya:
                mayaPluginPath = os.path.join(
                    self.legacyPluginsPath, 'ftrackMayaPlugin'
                )

                environment = ftrack_connect.application.appendPath(
                    mayaPluginPath, 'MAYA_PLUG_IN_PATH', environment
                )
                environment = ftrack_connect.application.appendPath(
                    mayaPluginPath, 'MAYA_SCRIPT_PATH', environment
                )
                environment = ftrack_connect.application.appendPath(
                    mayaPluginPath, 'PYTHONPATH', environment
                )

            # Add the foundry asset manager packages if application is
            # Nuke, NukeStudio or Hiero.
            if includeFoundryAssetManager:
                foundryAssetManagerPluginPath = os.path.join(
                    self.legacyPluginsPath, 'ftrackProvider'
                )

                environment = ftrack_connect.application.appendPath(
                    foundryAssetManagerPluginPath,
                    'FOUNDRY_ASSET_PLUGIN_PATH',
                    environment
                )

                foundryAssetManagerPath = os.path.join(
                    self.legacyPluginsPath,
                    'theFoundry'
                )

                environment = ftrack_connect.application.prependPath(
                    foundryAssetManagerPath, 'PYTHONPATH', environment
                )

        return environment


def register(registry, **kw):
    '''Register hooks for ftrack connect legacy plugins.'''
    # Validate that registry is the correct ftrack.Registry. If not,
    # assume that register is being called with another purpose or from a
    # new or incompatible API and return without doing anything.
    if registry is not ftrack.EVENT_HANDLERS:
        # Exit to avoid registering this plugin again.
        return

    applicationStore = LegacyApplicationStore()

    path = os.path.join(ftrack_connect_path, 'resource',
                        'legacy_plugins')
    launcher = LegacyApplicationLauncher(
        applicationStore,
        legacyPluginsPath=os.environ.get(
            'FTRACK_PYTHON_LEGACY_PLUGINS_PATH', path
        )
    )

    # Create action and register to respond to discover and launch events.
    action = LaunchAction(applicationStore, launcher)
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

    applicationStore = LegacyApplicationStore()

    path = os.path.join(ftrack_connect_path, 'resource',
                        'legacy_plugins')
    launcher = LegacyApplicationLauncher(
        applicationStore,
        legacyPluginsPath=os.environ.get(
            'FTRACK_PYTHON_LEGACY_PLUGINS_PATH', path
        )
    )

    # Create action and register to respond to discover and launch events.
    action = LaunchAction(applicationStore, launcher)
    action.register()

    ftrack.EVENT_HUB.wait()


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
