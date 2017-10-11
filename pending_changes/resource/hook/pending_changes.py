import json
import getpass

import ftrack_api
from ftrack_connect.session import get_shared_session


def callback(event):

    session = get_shared_session()

    for entity_data in event["data"].get("entities", []):

        # Filter to tasks
        if entity_data.get('entityType') != 'task':
            continue

        # Filter to updates
        if entity_data['action'] != 'update':
            continue

        # Filter to status changes
        if 'statusid' not in entity_data.get('keys'):
            continue

        # Filter to "Pending Changes"
        new_status = session.get(
            "Status", entity_data["changes"]["statusid"]["new"]
        )

        if new_status["name"].lower() != "pending changes":
            continue

        task = session.get("Task", entity_data["entityId"])
        user = session.get("User", event["source"]["user"]["id"])
        job = session.create(
            "Job",
            {
                "user": user,
                "status": "running",
                "data": json.dumps({"description": "Version Up Scene."})
            }
        )
        session.commit()

        try:
            versions = session.query(
                "select version,components,asset.name,asset.parent,"
                "asset.type.id,asset.parent.id,asset.type.id from AssetVersion"
                " where task.id is \"{0}\" and asset.type.short is "
                "\"scene\"".format(task["id"])
            )

            latest_version = {"version": 0}
            for version in versions:
                if latest_version["version"] < version["version"]:
                    latest_version = version

            # Skip if no scene version was found
            if latest_version["version"] == 0:
                job["status"] = "done"
                continue

            # Skip if an empty scene version exists
            if len(latest_version["components"]) == 0:
                job["status"] = "done"
                continue

            # Create Asset
            asset_data = {
                "name": latest_version["asset"]["name"],
                "type": latest_version["asset"]["type"],
                "parent": latest_version["asset"]["parent"],
            }

            asset_entity = session.query(
                "Asset where name is \"{0}\" and type.id is \"{1}\" and "
                "parent.id is \"{2}\"".format(
                    asset_data["name"],
                    asset_data["type"]["id"],
                    asset_data["parent"]["id"]
                )
            ).first()

            if not asset_entity:
                asset_entity = session.create("Asset", asset_data)

            # Create AssetVersion
            assetversion_data = {
                "version": latest_version["version"] + 1,
                "asset": asset_entity,
                "task": task
            }

            dst_asset_version = session.query(
                "AssetVersion where version is \"{0}\" and asset.id is "
                "\"{1}\" and task.id is \"{2}\"".format(
                    assetversion_data["version"],
                    assetversion_data["asset"]["id"],
                    assetversion_data["task"]["id"]
                )
            ).first()

            if not dst_asset_version:
                dst_asset_version = session.create(
                    "AssetVersion", assetversion_data
                )

            session.commit()
        except:
            job["status"] = "failed"
        else:
            job["status"] = "done"

        session.commit()


def register(session, **kw):
    """Register event listener."""

    # Validate that session is an instance of ftrack_api.Session. If not,
    # assume that register is being called from an incompatible API
    # and return without doing anything.
    if not isinstance(session, ftrack_api.Session):
        # Exit to avoid registering this plugin again.
        return

    # Register the event handler
    subscription = (
        "topic=ftrack.update and source.applicationId=ftrack.client.web and "
        "source.user.username={0}".format(getpass.getuser())
    )
    session.event_hub.subscribe(subscription, callback)
