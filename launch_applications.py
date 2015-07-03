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

sys.path.append(r'K:\tools\FTrack\ftrack-api')
sys.path.append(r'K:\tools\FTrack\ftrack-connect-package\Windows\v0.2.0\common.zip')
sys.path.append(r'K:\tools\FTrack\ftrack-connect-package\Windows\v0.2.0\library.zip')

import ftrack
import ftrack_connect.application


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

        context = event['data'].copy()
        context['source'] = event['source']

        applicationIdentifier = event['data']['applicationIdentifier']
        context = event['data'].copy()
        context['source'] = event['source']

        # getting path to file
        path = ''
        try:
            task = ftrack.Task(event['data']['selection'][0]['entityId'])
            type_name = task.getType().getName()
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

        launcher = LegacyApplicationLauncher(applicationStore,
            legacyPluginsPath=r'K:\tools\FTrack\ftrack-connect-package\Windows\v0.1.7\resource\legacy_plugins')

        return launcher.launch(applicationIdentifier, context)


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

        if sys.platform == 'darwin':
            prefix = ['/', 'Applications']

            applications.extend(self._searchFilesystem(
                expression=prefix + ['Autodesk', 'maya.+', 'Maya.app'],
                label='Maya {version}',
                applicationIdentifier='maya_{version}',
                icon='maya'
            ))

            applications.extend(self._searchFilesystem(
                expression=prefix + ['Nuke.*', 'Nuke\d[\w.]+.app'],
                label='Nuke {version}',
                applicationIdentifier='nuke_{version}',
                icon='nuke'
            ))

            applications.extend(self._searchFilesystem(
                expression=prefix + ['Nuke.*', 'NukeX\d.+.app'],
                label='NukeX {version}',
                applicationIdentifier='nukex_{version}',
                icon='nukex'
            ))

            applications.extend(self._searchFilesystem(
                expression=prefix + ['Hiero\d.+', 'Hiero\d.+.app'],
                label='Hiero {version}',
                applicationIdentifier='hiero_{version}',
                icon='hiero'
            ))

        elif sys.platform == 'win32':
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

            applications.extend(self._searchFilesystem(
                expression=prefix + ['Nuke.*', 'Nuke\d.+.exe'],
                versionExpression=nukeVersionExpression,
                label='Nuke {version}',
                applicationIdentifier='nuke_{version}',
                icon='nuke',
                launchArguments=launchArguments
            ))

            # Add NukeX as a separate application
            applications.extend(self._searchFilesystem(
                expression=prefix + ['Nuke.*', 'Nuke\d.+.exe'],
                versionExpression=nukeVersionExpression,
                label='NukeX {version}',
                applicationIdentifier='nukex_{version}',
                icon='nukex',
                launchArguments=['--nukex'].extend(launchArguments)
            ))

            applications.extend(self._searchFilesystem(
                expression=prefix + ['Hiero\d.+', 'hiero.exe'],
                label='Hiero {version}',
                applicationIdentifier='hiero_{version}',
                icon='hiero',
                launchArguments=launchArguments
            ))

            # Somewhere along the way The Foundry changed the default install directory.
            # Add the old directory as expression to find old installations of Hiero
            # as well.
            #
            # TODO: Refactor this once ``_searchFilesystem`` is more sophisticated.
            applications.extend(self._searchFilesystem(
                expression=prefix + ['The Foundry', 'Hiero\d.+', 'hiero.exe'],
                label='Hiero {version}',
                applicationIdentifier='hiero_{version}',
                icon='hiero',
                launchArguments=[path]
            ))

        self.logger.debug(
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

    def _getApplicationEnvironment(self, application, context):
        '''Modify and return environment with legacy plugins added.'''
        environment = super(
            LegacyApplicationLauncher, self
        )._getApplicationEnvironment(
            application, context
        )

        applicationIdentifier = application['identifier']

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
    applicationStore = LegacyApplicationStore()

    launcher = LegacyApplicationLauncher(
        applicationStore,
        legacyPluginsPath=os.environ.get(
            'FTRACK_PYTHON_LEGACY_PLUGINS_PATH',
            os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__), '..', 'legacy_plugins'
                )
            )
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

    launcher = LegacyApplicationLauncher(
        applicationStore,
        legacyPluginsPath=os.environ.get(
            'FTRACK_PYTHON_LEGACY_PLUGINS_PATH',
            os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__), '..', 'legacy_plugins'
                )
            )
        )
    )

    # Create action and register to respond to discover and launch events.
    action = LaunchAction(applicationStore, launcher)
    action.register()

    ftrack.EVENT_HUB.wait()


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
