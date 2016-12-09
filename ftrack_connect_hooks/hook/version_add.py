import logging
import getpass
import traceback

import ftrack


class VersionAdd(ftrack.Action):
    """Custom action."""

    identifier = "version.add"
    label = "VersionAdd"

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

    def is_valid_selection(self, selection):
        """Return true if the selection is valid."""

        if not selection:
            return False

        if selection[0]["entityType"] != "task":
            return False

        entity = selection[0]
        task = ftrack.Task(entity["entityId"])

        if task.getObjectType() != "Task":
            return False

        return True

    def discover(self, event):
        """Return action config if triggered on a single selection."""

        if not self.is_valid_selection(
            event["data"].get("selection", [])
        ):
            return

        return {
            "items": [{
                "label": self.label,
                "actionIdentifier": self.identifier,
            }]
        }

    def launch(self, event):
        if "values" in event["data"]:
            success = True
            msg = ""

            try:
                for item in event["data"]["selection"]:
                    values = event["data"]["values"]
                    task = ftrack.Task(item["entityId"])
                    parent = task.getParent()
                    version_name = values["version_name"]
                    version_type = values["version_type"]

                    asset = parent.createAsset(name=version_name,
                                               assetType=version_type)
                    version = asset.createVersion(taskid=task.getId())
                    version.publish()
                    version.set("version", value=int(values["version_number"]))

                    msg = "Version %s " % values["version_name"]
                    msg += "v%s created." % values["version_number"].zfill(3)
            except Exception as e:
                self.logger.error(traceback.format_exc())
                success = False
                msg = str(e)

            return {
                "success": success,
                "message": msg
            }

        asset_types = []
        for at in ftrack.getAssetTypes():
            asset_types.append({"label": at.getName(), "value": at.getShort()})

        return {
            "items": [
                {
                    "label": "Version Name",
                    "type": "text",
                    "name": "version_name",
                },
                {
                    "label": "Version Type",
                    "type": "enumerator",
                    "name": "version_type",
                    "data": asset_types
                },
                {
                    "label": "Version Number",
                    "type": "number",
                    "name": "version_number",
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
    action = VersionAdd()
    action.register()


if __name__ == "__main__":
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)

    ftrack.setup()
    action = VersionAdd()
    action.register()

    ftrack.EVENT_HUB.wait()
