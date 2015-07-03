import sys
import os
import logging
import getpass

sys.path.append(os.path.dirname(__file__))

import ftrack
import utils

log = logging.getLogger(__name__)

identifier = 'toot.update_tasks_thumbnail'

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
            'label': 'Update Tasks Thumbnail',
            'actionIdentifier': identifier
        }]
    }


def launch(event):

    selection = event['data'].get('selection', [])

    msg = 'Thumbnails updated!'
    success = True

    for entity in selection:
        try:
            log.info('***********************************************************')
            log.info('Updating thumbnail for tasks:')
            for item in selection:
                ID = item['entityId']
                entity = ftrack.Task(id=ID)
                for task in utils.getTasksRecursive(entity):
                    if not task.get('thumbid'):
                        thumbnail = utils.getThumbnailRecursive(task)
                        task.setThumbnail(thumbnail)

                        taskName = task.getName()
                        parentName = task.getParent().getName()
                        log.info('%s/%s' % (parentName, taskName))

        except Exception as e:
            log.error(e)
            msg = 'Thumbnails update failed!'
            success = False

    return {
        'success': success,
        'message': msg
    }


def register(registry, **kw):
    results = []
    temp = ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.action.discover and source.user.username={0}'.format(
            getpass.getuser()
        ),
        discover
    )
    results.append(temp)

    temp = ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.action.launch and source.user.username={0} '
        'and data.actionIdentifier={1}'.format(
            getpass.getuser(), identifier),
        launch
        )
    results.append(temp)


    return results

