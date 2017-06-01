import os
import threading
import json

import ftrack_api
import clique


def async(fn):
    """Run *fn* asynchronously."""
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()
    return wrapper


def query(entitytype, data):
    """ Generate a query expression from data supplied.
    If a value is not a string, we"ll add the id of the entity to the
    query.
    Args:
        entitytype (str): The type of entity to query.
        data (dict): The data to identify the entity.
        exclusions (list): All keys to exclude from the query.
    Returns:
        str: String query to use with "session.query"
    """
    queries = []
    for key, value in data.iteritems():
        if not isinstance(value, (basestring, int)):
            if "id" in value.keys():
                queries.append(
                    "{0}.id is \"{1}\"".format(key, value["id"])
                )
        else:
            queries.append("{0} is \"{1}\"".format(key, value))

    query = (
        "select id from " + entitytype + " where " + " and ".join(queries)
    )
    return query


def create_component(session, event, component_name, assetversion, component):

    component_location = session.get("Location", event["data"]["location_id"])
    location = session.pick_location()

    component_data = {
        "name": component_name,
        "version": assetversion
    }

    component_path = ""
    try:
        collection = clique.parse(
            component_location.get_resource_identifier(component),
            pattern="{head}{padding}{tail}"
        )
    except ValueError:
        # Assume its a single file
        component_path = component_location.get_resource_identifier(component)
    else:
        members = list(component.get("members", []))
        for member in members:
            collection.add(component_location.get_resource_identifier(member))

        component_path = collection.format()

    # Component
    component_entity = session.query(
        query("Component", component_data)
    ).first()

    # Overwrite existing component data if requested.
    if component_entity:

        origin_location = session.query(
            "Location where name is \"ftrack.origin\""
        ).one()

        # Removing existing members from location
        components = list(component_entity.get("members", []))
        components += [component_entity]
        for component in components:
            for loc in component["component_locations"]:
                if location["id"] == loc["location_id"]:
                    location.remove_component(
                        component, recursive=False
                    )

        # Deleting existing members on component entity
        for member in component_entity.get("members", []):
            session.delete(member)
            del(member)

        session.commit()

        # Reset members in memory
        if "members" in component_entity.keys():
            component_entity["members"] = []

        # Add components to origin location
        try:
            collection = clique.parse(component_path)
        except ValueError:
            # Assume its a single file
            origin_location.add_component(
                component_entity, component_path
            )
        else:
            # Create member components for sequence.
            for member_path in collection:

                size = 0
                try:
                    size = os.path.getsize(member_path)
                except OSError:
                    pass

                name = collection.match(member_path).group("index")

                member_data = {
                    "name": name,
                    "container": component_entity,
                    "size": size,
                    "file_type": os.path.splitext(member_path)[-1]
                }

                component = session.create(
                    "FileComponent", member_data
                )
                origin_location.add_component(
                    component, member_path, recursive=False
                )
                component_entity["members"].append(component)

        # Add components to location.
        location.add_component(
            component_entity, origin_location, recursive=True
        )

    # Create new component if none exists.
    if not component_entity:
        component = assetversion.create_component(
            component_path,
            data=component_data,
            location=location
        )


@async
def callback(event):

    session = ftrack_api.Session()
    component = session.get("Component", event["data"]["component_id"])

    # Not interested in non-existent components
    if not component:
        return

    assetversion = component.get("version", None)

    # Not interested in sub-components
    if not assetversion:
        return

    # Assuming playable component is "main".
    component_name = assetversion["asset"]["type"]["component"]
    # Not interested when adding the playable component
    if component["name"] == component_name:
        return

    # Create job and execute
    user = session.query(
        "User where username is \"{0}\"".format(
            event["source"]["user"]["username"]
        )
    ).one()

    job = session.create("Job", {
        "user": user,
        "status": "running",
        "data": json.dumps({
            "description": "Create playable component."
        })
    })

    try:
        create_component(
            session, event, component_name, assetversion, component
        )
    except:
        job["status"] = "failed"
        session.commit()
    else:
        job["status"] = "done"
        session.commit()


def register(session):

    # Validate that session is an instance of ftrack_api.Session. If not,assume
    # that register is being called from an old or incompatible API and return
    # without doing anything.
    if not isinstance(session, ftrack_api.Session):
        return

    session.event_hub.subscribe(
        "topic=ftrack.location.component-added",
        callback
    )
