# DJV View

This action will add the ability to use DJV Viewer from Ftrack.

## Usage

When launching DJV View you'll get a dropdown menu of files to choosing from. When hitting ```Submit``` the selected files will be loaded into DJV View.

## Setup

Add ```ftrack-hooks\djv_plugin``` to ```FTRACK_CONNECT_PLUGIN_PATH```.

By default no files will be loaded into the DJV dropdown menu. To get the action to scan for files, you'll need to setup an application launch plugin. See example below.

```python
import ftrack


def modify_launch(event):
    """Modify the application launch command with potential files to open"""

    # Collect published paths
    data = {}
    for item in event["data"].get("selection", []):

        versions = []

        if item["entityType"] == "assetversion":
            version = ftrack.AssetVersion(item["entityId"])
            if version.getAsset().getType().getShort() in ["img", "mov"]:
                versions.append(version)

        # Add latest version of "img" and "mov" type from tasks.
        if item["entityType"] == "task":
            task = ftrack.Task(item["entityId"])
            for asset in task.getAssets(assetTypes=["img", "mov"]):
                versions.append(asset.getVersions()[-1])

        for version in versions:
            for component in version.getComponents():
                component_list = data.get(component.getName(), [])
                component_list.append(component)
                data[component.getName()] = component_list

                label = "v{0} - {1} - {2}"
                label = label.format(
                    str(version.getVersion()).zfill(3),
                    version.getAsset().getType().getName(),
                    component.getName()
                )

                file_path = component.getFilesystemPath()
                if component.isSequence():
                    if component.getMembers():
                        frame = int(component.getMembers()[0].getName())
                        file_path = file_path % frame

                event["data"]["items"].append(
                    {"label": label, "value": file_path}
                )

    return event


def register(registry, **kw):
    """Register location plugin."""

    # Validate that registry is the correct ftrack.Registry. If not,
    # assume that register is being called with another purpose or from a
    # new or incompatible API and return without doing anything.
    if registry is not ftrack.EVENT_HANDLERS:
        # Exit to avoid registering this plugin again.
        return

    ftrack.EVENT_HUB.subscribe(
        "topic=djvview.launch",
        modify_launch
    )
```
