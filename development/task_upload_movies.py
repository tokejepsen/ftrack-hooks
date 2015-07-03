import os
import logging
import operator
import getpass

import ftrack

log = logging.getLogger(__name__)

identifier = 'upload_movies'


def discover(event):
    '''Return action config if triggered on a single asset version.'''
    data = event['data']

    # If selection contains more than one item return early since
    # this action can only handle a single version.
    selection = data.get('selection', [])

    # Filter non-tasks
    if selection[0].get('entityType') != 'task':
        return

    return {
        'items': [{
            'label': 'Upload Movie',
            'actionIdentifier': identifier
        }]
    }

def launch(event):

    selection = event['data'].get('selection', [])

    msg = 'Movie uploaded!'
    success = True

    for entity in selection:
        for item in selection:

            # Filter non-tasks
            if entity.get('entityType') == 'task':

                # Find task if it exists
                task = None
                try:
                    task = ftrack.Task(id=entity.get('entityId'))
                except:
                    return

                # filter out shots and sequences
                if task and task.get('objecttypename') == 'Task':
                    versions = {}
                    for version in task.getAssetVersions():
                        if version.getAsset().getType().getShort() == 'mov':
                            versions[version] = version.getVersion()

                    version = None
                    if versions:
                        version = max(versions.iteritems(),
                                      key=operator.itemgetter(1))[0]
                    else:
                        msg = 'Couldnt find any movie components '
                        msg += '%!' % task.getName()
                        log.error(msg)
                        success = False

                    mov_paths = {}
                    for comp in version.getComponents():
                        path = comp.getFilesystemPath()
                        if os.path.exists(path):
                            mov_paths[path] = os.path.getsize(path)

                    mov = None
                    if mov_paths:
                        mov = min(mov_paths.iteritems(),
                                  key=operator.itemgetter(1))[0]
                    else:
                        msg = 'Couldnt find any movies to upload for '
                        msg += '%!' % task.getName()
                        log.error(msg)
                        success = False

                    if mov:
                        ftrack.Review.makeReviewable(version, mov)
                        version.publish()
    return {
        'success': success,
        'message': msg
    }


def register(registry, **kw):
    ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.action.discover and source.user.username={0}'.format(
            getpass.getuser()
        ),
        discover
    )

    ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.action.launch and source.user.username={0} '
        'and data.actionIdentifier={1}'.format(
            getpass.getuser(), identifier
        ),
        launch
    )
