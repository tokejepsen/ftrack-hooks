import os
import sys
import argparse
import logging
import getpass
import threading
import traceback
import shutil

import ftrack
import ftrack_template
import ftrack_api

session = ftrack_api.Session()


def async(fn):
    """Run *fn* asynchronously."""
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()
    return wrapper


@async
def create_job(event):

    job = ftrack.createJob("Create Structure", "queued",
                           ftrack.User(id=event["source"]["user"]["id"]))
    job.setStatus("running")

    try:
        for item in event["data"]["selection"]:
            # Geting any object types
            entity_id = item["entityId"]
            entity = session.get("TypedContext", entity_id)

            if not entity:
                entity_type = item["entityType"].lower()

                if entity_type == "show":
                    entity = session.get("Project", entity_id)
                if entity_type == "assetversion":
                    entity = session.get("AssetVersion", entity_id)
                if entity_type == "component":
                    entity = session.get("Component", entity_id)

            templates = ftrack_template.discover_templates()
            valid_templates = ftrack_template.format(
                {}, templates, entity, return_mode="all"
            )

            print "Creating Directories/Files:"
            for path, template in valid_templates:

                if template.isfile:
                    if not os.path.exists(os.path.dirname(path)):
                        print os.path.dirname(path)
                        os.makedirs(os.path.dirname(path))

                    if not os.path.exists(path):
                        print path
                        shutil.copy(template.source, path)
                else:
                    if not os.path.exists(path):
                        print path
                        os.makedirs(path)
    except:
        print traceback.format_exc()
        job.setStatus("failed")
    else:
        job.setStatus("done")


class CreateStructure(ftrack.Action):
    """Custom action."""

    identifier = "create.structure"
    label = "Create Structure"

    def __init__(self):
        """Initialise action handler."""
        self.logger = logging.getLogger(
            __name__ + "." + self.__class__.__name__
        )

    def register(self):
        """Register action."""
        ftrack.EVENT_HUB.subscribe(
            "topic=ftrack.action.discover and source.user.username={0}".format(
                getpass.getuser()
            ),
            self.discover
        )

        ftrack.EVENT_HUB.subscribe(
            "topic=ftrack.action.launch and source.user.username={0} "
            "and data.actionIdentifier={1}".format(
                getpass.getuser(), self.identifier
            ),
            self.launch
        )

    def discover(self, event):
        """Return action config if triggered on a single selection."""

        selection = event["data"].get("selection", [])

        if not selection:
            return

        return {
            "items": [{
                "label": self.label,
                "actionIdentifier": self.identifier,
            }]
        }

    def launch(self, event):

        create_job(event)


def register(registry, **kw):
    """Register action. Called when used as an event plugin."""
    # Validate that registry is the correct ftrack.Registry. If not,
    # assume that register is being called with another purpose or from a
    # new or incompatible API and return without doing anything.
    if registry is not ftrack.EVENT_HANDLERS:
        # Exit to avoid registering this plugin again.
        return

    logging.basicConfig(level=logging.INFO)
    action = CreateStructure()
    action.register()


def main(arguments=None):
    """Set up logging and register action."""
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
        "-v", "--verbosity",
        help="Set the logging output verbosity.",
        choices=loggingLevels.keys(),
        default="info"
    )
    namespace = parser.parse_args(arguments)

    """Register action and listen for events."""
    logging.basicConfig(level=loggingLevels[namespace.verbosity])

    ftrack.setup()
    action = CreateStructure()
    action.register()

    ftrack.EVENT_HUB.wait()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
