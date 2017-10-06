import os
import tempfile
import json
import traceback
import shutil
import uuid
import subprocess
import getpass

import requests
import ftrack_api
from ftrack_hooks.action import BaseAction
from ftrack_connect.session import get_shared_session


class ProcessReviewAction(BaseAction):
    """ProcessReview action

    `label` a descriptive string identifing your action.

    `varaint` To group actions together, give them the same
    label and specify a unique variant per action.

    `identifier` a unique identifier for your action.

    `description` a verbose descriptive text for you action
     """
    label = "ProcessReview"
    variant = None
    identifier = "process-review" + getpass.getuser()
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

    def discover_presets(self):
        """Search *paths* for mount points and load presets from."""
        presets = []
        paths = os.environ.get("REVIEW_PRESETS", "").split(os.pathsep)
        for path in paths:
            for base, directories, filenames in os.walk(path):
                for filename in filenames:
                    _, extension = os.path.splitext(filename)
                    if extension != ".py":
                        continue

                    presets.append(os.path.join(base, filename))

                del directories[:]

        return presets

    def download_component(self, component, tempdir, server_location):
        """Downloads the components file from "ftrack.server" location."""

        url = server_location.get_url(component)
        path = os.path.join(tempdir, str(uuid.uuid4()) + ".mov")

        r = requests.get(url, stream=True)
        with open(path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

        return path

    def process_preset(self, movie_path, preset):

        review_path = movie_path.replace(".mov", "_review.mov")
        thumbnail_path = movie_path.replace(".mov", "_thumbnail.png")
        subprocess.call(
            ["python", preset, movie_path, review_path, thumbnail_path]
        )

        if not os.path.exists(review_path):
            raise IOError(
                "Preset \"{0}\"did not generate the review "
                "movie.".format(preset)
            )

        return [review_path, thumbnail_path]

    def create_review_components(self, movie_path,
                                 src_asset_version, server_location,
                                 src_component, thumbnail_path=""):

        session = get_shared_session()

        # Create Asset
        asset_data = {
            "name": src_asset_version["asset"]["name"] + "_review",
            "type": src_asset_version["asset"]["type"],
            "parent": src_asset_version["asset"]["parent"],
        }

        asset_entity = session.query(
            "Asset where name is \"{0}\" and type.id is \"{1}\" and parent.id "
            "is \"{2}\"".format(
                asset_data["name"],
                asset_data["type"]["id"],
                asset_data["parent"]["id"]
            )
        ).first()

        if not asset_entity:
            asset_entity = session.create("Asset", asset_data)

        # Create AssetVersion
        assetversion_data = {
            "version": src_asset_version["version"],
            "asset": asset_entity,
            "task": src_asset_version["task"]
        }

        dst_asset_version = session.query(
            "AssetVersion where version is \"{0}\" and asset.id is \"{1}\" "
            "and task.id is \"{2}\"".format(
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

        # Recreate movie component
        component_data = {
            "name": "ftrackreview-mp4",
            "version": dst_asset_version
        }

        movie_component = session.query(
            "Component where name is \"{0}\" and version.id is \"{1}\"".format(
                component_data["name"],
                component_data["version"]["id"],
            )
        ).first()

        if movie_component:
            session.delete(movie_component)

        movie_component = dst_asset_version.create_component(
            movie_path,
            data=component_data,
            location=server_location
        )

        # Add metadata
        movie_component["metadata"] = dict(src_component["metadata"])

        session.commit()

        # Recreate thumbnail component if the file exists
        if not os.path.exists(thumbnail_path):
            return

        component_data = {
            "name": "thumbnail",
            "version": dst_asset_version
        }

        thumbnail_component = session.query(
            "Component where name is \"{0}\" and version.id is \"{1}\"".format(
                component_data["name"],
                component_data["version"]["id"],
            )
        ).first()

        if thumbnail_component:
            session.delete(thumbnail_component)

        thumbnail_component = dst_asset_version.create_component(
            thumbnail_path,
            data=component_data,
            location=server_location
        )

        dst_asset_version["thumbnail_id"] = thumbnail_component["id"]

        session.commit()

    def process_review(self, src_asset_version, preset, tempdir):

        session = get_shared_session()

        src_component = session.query(
            "Component where version.id is \"{0}\" and "
            "name is \"ftrackreview-mp4\"".format(src_asset_version["id"])
        ).first()

        # Get ftrack.server location
        server_location = session.query(
            "Location where name is \"ftrack.server\""
        ).one()

        movie_path = self.download_component(
            src_component, tempdir, server_location
        )

        [review_path, thumbnail_path] = self.process_preset(movie_path, preset)

        self.create_review_components(
            review_path, src_asset_version, server_location,
            src_component, thumbnail_path=thumbnail_path
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

            job = session.create(
                "Job",
                {
                    "user": user,
                    "status": "running",
                    "data": json.dumps({"description": "Process review."})
                }
            )
            session.commit()

            tempdir = tempfile.mkdtemp()

            try:
                for data in entities:
                    entity = session.get(data[0], data[1])
                    self.process_review(entity, preset, tempdir)
            except:
                print traceback.format_exc()
                job["status"] = "failed"
            else:
                job["status"] = "done"

            shutil.rmtree(tempdir)
            session.commit()

            return {
                'success': True,
                'message': 'Action completed successfully'
            }

        data = []
        for path in self.discover_presets():
            data.append({"label": os.path.basename(path), "value": path})

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


def register(session):

    # Validate that session is an instance of ftrack_api.Session. If not,assume
    # that register is being called from an old or incompatible API and return
    # without doing anything.
    if not isinstance(session, ftrack_api.Session):
        return

    # Create action and register to respond to discover and launch actions.
    action = ProcessReviewAction(session)
    action.register()
