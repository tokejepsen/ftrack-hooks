from operator import itemgetter
import ftrack


def get_file_for_component(component):
    file_path = component.getFilesystemPath()

    if component.isSequence():
        members = component.getMembers()
        if members:
            frame = int(members[0].getName())
            file_path = file_path % frame

    return file_path


def get_components(event, asset_types):
    # finding components
    data = []
    for item in event["data"].get("selection", []):
        selection = event["data"]["selection"]
        entity_type = selection[0]["entityType"]

        # get all components on version
        if entity_type == "assetversion":
            version = ftrack.AssetVersion(item["entityId"])

            if not version.get("ispublished"):
                version.publish()

            for c in version.getComponents():
                data.append({
                    "label": c.getName(),
                    "value": {
                        'name': c.getName(),
                        'filename': get_file_for_component(c)
                    }
                })

        # get all components on all valid versions
        if entity_type == "task":
            task = ftrack.Task(selection[0]["entityId"])

            for asset in task.getAssets(assetTypes=asset_types):
                for version in asset.getVersions():
                    padded_version = str(version.getVersion()).zfill(3)
                    for component in version.getComponents():
                        label = "v" + padded_version
                        label += " - " + asset.getType().getName()
                        label += " - " + component.getName()
                        data.append({
                            "label": label,
                            "value": {
                                'name': c.getName(),
                                'filename': get_file_for_component(c)
                            }
                        })

            data = sorted(data, key=itemgetter("label"), reverse=True)

    return data