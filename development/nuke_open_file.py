# :coding: utf-8
# :copyright: Copyright (c) 2014 ftrack

import getpass
import logging

import ftrack
import ftrack_connect.application

ACTION_IDENTIFIER = 'ftrack-connect-launch-applications-action'


class DiscoverApplicationsHook(object):
    '''Default action.discover hook.

    The class is callable and return an object with a list of actions that can
    be launched on this computer.

    Example:

        dict(
            items=[
                dict(
                    actionIdentifier='ftrack-connect-launch-applications-action',
                    label='Maya 2014',
                    actionData=dict(
                        applicationIdentifier='maya_2014'
                    )
                ),
                dict(
                    actionIdentifier='ftrack-connect-launch-applications-action',
                    label='Premiere Pro CC 2014',
                    actionData=dict(
                        applicationIdentifier='pp_cc_2014'
                    )
                ),
                dict(
                    actionIdentifier='ftrack-connect-launch-applications-action',
                    label='Premiere Pro CC 2014 with latest publish',
                    actionData=dict(
                        latest=True,
                        applicationIdentifier='pp_cc_2014'
                    )
                )
            ]
        )

    '''

    identifier = ACTION_IDENTIFIER

    def __init__(self, applicationStore):
        '''Instantiate hook with *applicationStore*.

        *applicationStore* should be an instance of
        :class:`ftrack_connect.application.ApplicationStore`

        '''
        super(DiscoverApplicationsHook, self).__init__()
        self.logger = logging.getLogger(
            __name__ + '.' + self.__class__.__name__
        )
        self.applicationStore = applicationStore

    def __call__(self, event):
        '''Handle *event*.

        event['data'] should contain:

            selection
                Selected task to discover applications for.
        '''
        data = event['data']

        # If selection contains more than one item return early since
        # applications cannot be started for multiple items or if the
        # selected item is not a "task".
        selection = data.get('selection', [])
        if len(selection) != 1 or selection[0].get('entityType') != 'task':
            return

        items = []
        applications = self.applicationStore.applications
        applications = sorted(
            applications, key=lambda application: application['label']
        )

        for application in applications:
            applicationIdentifier = application['identifier']

            if applicationIdentifier.startswith('nuke'):
                items.append({
                    'actionIdentifier': self.identifier,
                    'label': 'custom'
                    ),
                    'icon': application.get('icon', 'default'),
                    'launchWithLatest': True,
                    'applicationIdentifier': applicationIdentifier
                })

        return {
            'items': items
        }


class LaunchApplicationHook(object):

    def __init__(self, launcher):
        '''Initialise hook with *launcher*.

        *launcher* should be an instance of
        :class:`ftrack_connect.application.ApplicationLauncher`.

        '''
        super(LaunchApplicationHook, self).__init__()
        self.logger = logging.getLogger(
            'ftrack.hook.' + self.__class__.__name__
        )
        self.launcher = launcher

    def __call__(self, event):
        '''Handle *event*.

        event['data'] should contain:

            applicationIdentifier
                Identifier for the application to be launched.
            selection
                A list of selected entities for which to launch the application
                for.
        '''
        applicationIdentifier = event['data']['applicationIdentifier']
        context = event['data'].copy()
        context['source'] = event['source']

        return self.launcher.launch(
            applicationIdentifier, context
        )


def register(registry, **kw):
    '''Register hooks.'''
    applicationStore = ftrack_connect.application.ApplicationStore()

    ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.action.discover and source.user.username={0}'.format(
            getpass.getuser()
        ),
        DiscoverApplicationsHook(applicationStore)
    )

    ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.action.launch and source.user.username={0} '
        'and data.actionIdentifier={1}'.format(
            getpass.getuser(), ACTION_IDENTIFIER
        ),
        LaunchApplicationHook(
            ftrack_connect.application.ApplicationLauncher(
                applicationStore
            )
        )
    )
