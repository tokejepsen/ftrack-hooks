import threading
import getpass

import ftrack


def async(fn):
    """Run *fn* asynchronously."""
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()
    return wrapper


@async
def callback(event):

    # Return early if event wasn't triggered by the current user.
    if "user" in event["data"]:
        user = ftrack.User(event["data"]["user"]["userid"])
        if user.getUsername() != getpass.getuser():
            return

    for entity in event['data'].get('entities', []):

        # Filter non-assetversions
        if entity.get('entityType') == 'task' and entity['action'] == 'update':

            if 'statusid' not in entity.get('keys'):
                return

            # Find task if it exists
            task = None
            try:
                task = ftrack.Task(id=entity.get('entityId'))
            except:
                return

            new_status = ftrack.Status(entity["changes"]["statusid"]["new"])

            # To Pending Changes
            if new_status.getName().lower() == "pending changes":

                user = ftrack.User(id=event["source"]["user"]["id"])
                job = ftrack.createJob("Version Up Tasks", "queued", user)
                job.setStatus("running")

                try:
                    asset = task.getParent().createAsset(
                        task.getName(),
                        "scene",
                        task=task
                    )

                    asset.createVersion(taskid=task.getId())

                    asset.publish()
                except:
                    job.setStatus("failed")
                else:
                    job.setStatus("done")


def register(registry, **kw):

    # Validate that registry is the correct ftrack.Registry. If not,
    # assume that register is being called with another purpose or from a
    # new or incompatible API and return without doing anything.
    if registry is not ftrack.EVENT_HANDLERS:
        # Exit to avoid registering this plugin again.
        return

    # Subscribe to events with the update topic.
    ftrack.EVENT_HUB.subscribe("topic=ftrack.update", callback)
