import os
import json
import shutil
import threading
import traceback
import logging

import ftrack_api
from ftrack_hooks.action import BaseAction


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
                'description': 'Create Structure: Generate file structure.'
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


class CreateStructureAction(BaseAction):
    '''Create Structure action

    `label` a descriptive string identifing your action.

    `varaint` To group actions together, give them the same
    label and specify a unique variant per action.

    `identifier` a unique identifier for your action.

    `description` a verbose descriptive text for you action
     '''
    label = "Create Structure"
    variant = None
    identifier = "create-structure"
    description = None

    def __init__(self, session):
        """Expects a ftrack_api.Session instance"""
        super(CreateStructureAction, self).__init__(session)

    def discover(self, session, entities, event):

        # Only discover the action if any selection is made.
        if entities:
            return True

        return False

    def get_children_recursive(self, entity, children=[]):

        for child in entity["children"]:
            children.append(child)
            children.extend(self.get_children_recursive(child, []))

        return children

    def launch(self, session, entities, event):

        if "values" in event["data"]:

            entity_objects = []

            for entity_type, entity_id in entities:
                entity = session.get(entity_type, entity_id)
                entity_objects.append(entity)

                # Collect children if requested
                if event["data"]["values"]["include_children"]:
                    entity_objects.extend(
                        self.get_children_recursive(entity, [])
                    )
                # Collect parents if requested
                if event["data"]["values"]["include_parents"]:
                    for item in reversed(entity['link'][:-1]):
                        entity_objects.insert(
                            0, session.get(item['type'], item['id'])
                        )

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
                data["entities"] = entity_objects
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


        return {
            "success": True,
            "message": "",
            "items": [
                {
                    "label": "Include parents",
                    "type": "boolean",
                    "name": "include_parents",
                    "value": False
                },
                {
                    "label": "Include children",
                    "type": "boolean",
                    "name": "include_children",
                    "value": False
                }
            ]
        }



def register(session):

    # Validate that session is an instance of ftrack_api.Session. If not,assume
    # that register is being called from an old or incompatible API and return
    # without doing anything.
    if not isinstance(session, ftrack_api.Session):
        return

    # Create action and register to respond to discover and launch actions.
    action = CreateStructureAction(session)
    action.register()
