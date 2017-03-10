import sys
import argparse
import logging
import getpass

import ftrack


class AssetDelete(ftrack.Action):
    """Custom action."""

    identifier = "asset.delete"
    label = "Asset Delete"

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
        if "values" in event["data"]:
            # Do something with the values or return a new form.
            values = event["data"]["values"]

            success = True
            msg = "Asset deleted."

            # deleting all assets
            if values["asset"] == "all":
                entity = None
                try:
                    entity = ftrack.Project(
                        event["data"]["selection"][0]["entityId"]
                    )
                except:
                    entity = ftrack.Task(
                        event["data"]["selection"][0]["entityId"]
                    )
                for asset in entity.getAssets():
                    asset.delete()

                return {
                    "success": success,
                    "message": "All assets deleted."
                }

            asset = ftrack.Asset(values["asset"])
            asset.delete()

            return {
                "success": success,
                "message": msg
            }

        data = []
        entity = None
        try:
            entity = ftrack.Project(event["data"]["selection"][0]["entityId"])
        except:
            entity = ftrack.Task(event["data"]["selection"][0]["entityId"])
        for asset in entity.getAssets():
            if asset.getName():
                name = "{0} ({1})".format(
                    asset.getName(), asset.getType().getName()
                )
                data.append({"label": name, "value": asset.getId()})
            else:
                data.append({"label": "None", "value": asset.getId()})

        if len(data) > 1:
            data.append({"label": "All", "value": "all"})

        return {
            "items": [
                {
                    "label": "Asset",
                    "type": "enumerator",
                    "name": "asset",
                    "data": data
                }
            ]
        }


def register(registry, **kw):
    """Register action. Called when used as an event plugin."""
    # Validate that registry is the correct ftrack.Registry. If not,
    # assume that register is being called with another purpose or from a
    # new or incompatible API and return without doing anything.
    if registry is not ftrack.EVENT_HANDLERS:
        # Exit to avoid registering this plugin again.
        return

    logging.basicConfig(level=logging.INFO)
    action = AssetDelete()
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
    action = AssetDelete()
    action.register()

    ftrack.EVENT_HUB.wait()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
