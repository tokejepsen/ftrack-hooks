import os
import tempfile
import subprocess
import json

import ftrack_api
from ftrack_api.structure.id import IdStructure
from ftrack_hooks.action import BaseAction


class ProcessReviewAction(BaseAction):
    """Process Review action

    `label` a descriptive string identifing your action.

    `varaint` To group actions together, give them the same
    label and specify a unique variant per action.

    `identifier` a unique identifier for your action.

    `description` a verbose descriptive text for you action
     """
    label = "Process Review"
    variant = None
    identifier = "process-review"
    description = None

    def __init__(self, session):
        """Expects a ftrack_api.Session instance"""
        super(ProcessReviewAction, self).__init__(session)

    def discover(self, session, entities, event):

        # Only discover the action if any selection is made.
        if not entities:
            return False

        # Only operate on AssetVersions
        for entity in entities:
            if entity[0] != "AssetVersion":
                return False

        return True

    def process_review(self, src_asset_version, preset):

        src_component = self._session.query(
            "Component where version.id is \"{0}\" and "
            "name is \"ftrackreview-mp4\"".format(src_asset_version["id"])
        ).first()

        # Get ftrack.server location
        server_location = self._session.query(
            "Location where name is \"ftrack.server\""
        ).one()

        tempdir = tempfile.mkdtemp()
        movie_path = self.download_component(
            src_component, tempdir, server_location
        )

        review_path = self.process_preset(movie_path, preset)

        self.create_review_component(
            review_path, src_asset_version, server_location, src_component
        )

    def launch(self, session, entities, event):

        if "values" in event["data"]:
            preset = event["data"]["values"]["preset"]

            # Create job and execute
            user = session.query(
                "User where username is \"{0}\"".format(
                    event["source"]["user"]["username"]
                )
            ).one()

            job = self._session.create("Job", {
                "user": user,
                "status": "running",
                "data": json.dumps({
                    "description": "Process review."
                })
            })

            try:
                for data in entities:
                    entity = self._session.get(data[0], data[1])
                    self.process_review(entity, preset)
            except:
                job["status"] = "failed"
                self._session.commit()
            else:
                job["status"] = "done"
                self._session.commit()

            return {
                'success': True,
                'message': 'Action completed successfully'
            }

        data = []
        for preset in self.discover_presets():
            data.append({"label": os.path.basename(preset), "value": preset})

        return {
            "success": True,
            "message": "",
            "items": [
                {
                    "label": "Preset",
                    "type": "enumerator",
                    "name": "preset",
                    "data": data
                }
            ]
        }

    def download_component(self, component, tempdir, server_location):
        """Downloads the components file from "ftrack.server" location."""

        # Setup a temporary location
        temp_location = self._session.create("Location")
        temp_location.accessor = ftrack_api.accessor.disk.DiskAccessor(
            prefix=tempdir
        )
        temp_location.structure = IdStructure()

        # Transfer data from ftrack.server to temporary location.
        resource_identifier = temp_location.structure.get_resource_identifier(
            component
        )
        temp_location._add_data(
            component, resource_identifier, server_location
        )

        self._session.delete(temp_location)

        return os.path.join(tempdir, resource_identifier)

    def discover_presets(self, paths=None, recursive=True):
        """Search *paths* for mount points and load presets from."""
        presets = []

        if paths is None:
            paths = os.environ.get("REVIEW_PRESETS", "").split(os.pathsep)

        for path in paths:
            for base, directories, filenames in os.walk(path):
                for filename in filenames:
                    _, extension = os.path.splitext(filename)
                    if extension != ".py":
                        continue

                    presets.append(os.path.join(base, filename))

                if not recursive:
                    del directories[:]

        return presets

    def process_preset(self, movie_path, preset):

        review_path = movie_path.replace(".mov", "_review.mov")
        subprocess.call(["python", preset, movie_path, review_path])

        return review_path

    def create_review_component(self, component_path, src_asset_version,
                                server_location, src_component):

        # Create Asset
        asset_data = {
            "name": src_asset_version["asset"]["name"] + "_review",
            "type": src_asset_version["asset"]["type"],
            "parent": src_asset_version["asset"]["parent"],
        }

        asset_entity = self._session.query(
            "Asset where name is \"{0}\" and type.id is \"{1}\" and parent.id "
            "is \"{2}\"".format(
                asset_data["name"],
                asset_data["type"]["id"],
                asset_data["parent"]["id"]
            )
        ).first()

        if not asset_entity:
            asset_entity = self._session.create("Asset", asset_data)

        # Create AssetVersion
        assetversion_data = {
            "version": src_asset_version["version"],
            "asset": asset_entity,
            "task": src_asset_version["task"],
            "thumbnail_id": src_asset_version["thumbnail"]["id"]
        }

        dst_asset_version = self._session.query(
            "AssetVersion where version is \"{0}\" and asset.id is \"{1}\" "
            "and task.id is \"{2}\"".format(
                assetversion_data["version"],
                assetversion_data["asset"]["id"],
                assetversion_data["task"]["id"]
            )
        ).first()

        if not dst_asset_version:
            dst_asset_version = self._session.create(
                "AssetVersion", assetversion_data
            )

        self._session.commit()

        # Recreate Component
        component_data = {
            "name": "ftrackreview-mp4",
            "version": dst_asset_version
        }

        dst_component = self._session.query(
            "Component where name is \"{0}\" and version.id is \"{1}\"".format(
                component_data["name"],
                component_data["version"]["id"],
            )
        ).first()

        if dst_component:
            self._session.delete(dst_component)

        dst_component = dst_asset_version.create_component(
            component_path,
            data=component_data,
            location=server_location
        )

        # Add metadata
        dst_component["metadata"] = dict(src_component["metadata"])

        self._session.commit()


def register(session):

    # Validate that session is an instance of ftrack_api.Session. If not,assume
    # that register is being called from an old or incompatible API and return
    # without doing anything.
    if not isinstance(session, ftrack_api.Session):
        return

    # Create action and register to respond to discover and launch actions.
    action = ProcessReviewAction(session)
    action.register()
