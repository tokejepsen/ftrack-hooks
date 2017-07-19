import os
import json
import shutil
import threading
import traceback

import ftrack_api
from ftrack_action_handler import action


def async(fn):
    """Run *fn* asynchronously."""
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()
    return wrapper


@async
def create_job(event, session):

    user = session.query(
        'User where username is "{0}"'.format(os.environ["LOGNAME"])
    ).one()
    job = session.create(
        'Job',
        {
            'user': user,
            'status': 'running',
            'data': json.dumps({
                'description': 'Create Structure: Scanning for data.'
            })
        }
    )
    # Commit to feedback to user.
    session.commit()

    try:
        for directory in event["data"]["directories"]:
            if not os.path.exists(directory):
                print 'Create directory: "{0}"'.format(directory)
                os.makedirs(directory)

        for src, dst in event["data"]["files"]:
            if not os.path.exists(dst):
                print 'Copy "{0}" to "{1}"'.format(src, dst)
                shutil.copy(src, dst)
    except:
        print traceback.format_exc()
        job["status"] = "failed"
    else:
        job["status"] = "done"

    # Commit to end job.
    session.commit()


class CreateStructureAction(action.BaseAction):

    label = "Create Structure"
    identifier = "create-structure"

    def __init__(self, session):
        super(CreateStructureAction, self).__init__(session)

    def discover(self, session, uid, entities, source, values, event):
        '''Return true if we can handle the selected entities.

        *session* is a `ftrack_api.Session` instance

        *uid* is the unique identifier for the event

        *entities* is a list of tuples each containing the entity type and
        the entity id.
        If the entity is a hierarchical you will always get the entity
        type TypedContext, once retrieved through a get operation you
        will have the "real" entity type ie. example Shot, Sequence
        or Asset Build.

        *source* dictionary containing information about the source of the
        event, application id, current user etc.

        *values* is a dictionary containing potential user settings

        *event* the unmodified original event
        '''

        # Only discover the action if any selection is made.
        if entities:
            return True

        return False

    def launch(self, session, uid, entities, source, values, event):
        '''Callback method for the custom action.

        return either a bool (True if successful or False if the action failed)
        or a dictionary with they keys `message` and `success`, the message
        should be a string and will be displayed as feedback to the user,
        success should be a bool, True if successful or False if the action
        failed.

        *session* is a `ftrack_api.Session` instance

        *uid* is the unique identifier for the event

        *entities* is a list of tuples each containing the entity type and the
        entity id.
        If the entity is a hierarchical you will always get the entity
        type TypedContext, once retrieved through a get operation you
        will have the "real" entity type ie. example Shot, Sequence
        or Asset Build.

        *source* dictionary containing information about the source of the
        event, application id, current user etc.

        *values* is a dictionary containing potential user settings
        from previous runs.

        *event* the unmodified original event

        '''
        user = session.query(
            'User where username is "{0}"'.format(os.environ["LOGNAME"])
        ).one()
        job = session.create(
            'Job',
            {
                'user': user,
                'status': 'running',
                'data': json.dumps({
                    'description': 'Create Structure: Scanning for data.'
                })
            }
        )
        # Commit to feedback to user about running job.
        session.commit()

        try:
            data = event["data"]
            data["selection"] = entities
            data["directories"] = []
            data["files"] = []
            session.event_hub.publish(
                ftrack_api.event.base.Event(
                    topic='create_structure.launch',
                    data=data
                ),
                synchronous=True
            )
        except:
            print traceback.format_exc()
            job["status"] = "failed"
        else:
            job["status"] = "done"

        # Commit to end job.
        session.commit()

        create_job(event, session)

        return True


def register(session):

    # Validate that session is an instance of ftrack_api.Session. If not,assume
    # that register is being called from an old or incompatible API and return
    # without doing anything.
    if not isinstance(session, ftrack_api.Session):
        return

    # Create action and register to respond to discover and launch actions.
    action = CreateStructureAction(session)
    action.register()
