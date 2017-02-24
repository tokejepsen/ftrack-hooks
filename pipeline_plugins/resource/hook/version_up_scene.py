import getpass
import threading

import ftrack


def async(fn):
    """Run *fn* asynchronously."""
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()
    return wrapper


@async
def create_job(event):

    job = ftrack.createJob("Version Up Tasks", "queued",
                           ftrack.User(id=event["source"]["user"]["id"]))
    job.setStatus("running")

    try:
        for item in event["data"]["selection"]:
            task = ftrack.Task(item["entityId"])

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


def launch(event):

    create_job(event)


def discover(event):

    data = event["data"]

    for item in data["selection"]:
        if item["entityType"] != "task":
            return

    return {
        "items": [{
            "label": "Version Up Scene",
            "actionIdentifier": "version_up_scene"
        }]
    }


def register(registry, **kw):
    """Register location plugin."""

    # Validate that registry is the correct ftrack.Registry. If not,
    # assume that register is being called with another purpose or from a
    # new or incompatible API and return without doing anything.
    if registry is not ftrack.EVENT_HANDLERS:
        # Exit to avoid registering this plugin again.
        return

    """Register action."""
    ftrack.EVENT_HUB.subscribe(
        "topic=ftrack.action.discover and source.user.username={0}".format(
            getpass.getuser()
        ),
        discover
    )

    ftrack.EVENT_HUB.subscribe(
        "topic=ftrack.action.launch and source.user.username={0} "
        "and data.actionIdentifier={1}".format(
            getpass.getuser(), "version_up_scene"),
        launch
        )


if __name__ == "__main__":
    ftrack.setup()

    """Register action."""
    ftrack.EVENT_HUB.subscribe(
        "topic=ftrack.action.discover and source.user.username={0}".format(
            getpass.getuser()
        ),
        discover
    )

    ftrack.EVENT_HUB.subscribe(
        "topic=ftrack.action.launch and source.user.username={0} "
        "and data.actionIdentifier={1}".format(
            getpass.getuser(), "version_up_scene"),
        launch
        )

    ftrack.EVENT_HUB.wait()
