import os
import sys
import logging
import argparse

import ftrack_api


def callback(event):

    # Return early if event wasn"t triggered by the current user.
    if event["source"]["user"]["username"] != os.environ["FTRACK_API_USER"]:
        return

    session = ftrack_api.Session()
    for entity_data in event["data"]["entities"]:

        # Filter to tasks.
        if entity_data["entityType"].lower() != "task":
            continue

        if "statusid" not in entity_data["keys"]:
            continue

        task = session.get("Task", entity_data["entityId"])

        # Status assignees.
        assignees = []
        if task["metadata"].get("assignees"):
            assignees = [
                session.get("User", userid)
                for userid in task["metadata"]["assignees"].split(",")
            ]

        # Get task users and remove status assigned users.
        task_users = set()
        status_appointments = []
        for appointment in task["appointments"]:
            resource = appointment["resource"]

            # Filter to Users.
            if not isinstance(resource, session.types["User"]):
                continue

            if resource in assignees:
                status_appointments.append(appointment)
                continue

            task_users.add(resource)

        for appointment in status_appointments:
            session.delete(appointment)

        # Getting status members.
        project = session.get(
            "Project", entity_data["parents"][-1]["entityId"]
        )
        status_users = set()
        for allocation in project["allocations"]:
            resource = allocation["resource"]

            # Filter to groups.
            if not isinstance(resource, session.types["Group"]):
                continue

            # Filter to groups named the same as the tasks status.
            if resource["name"].lower() != task["status"]["name"].lower():
                continue

            for child in resource["children"]:
                # Filter to groups.
                if not isinstance(child, session.types["Group"]):
                    continue

                # Filter to groups named the same as the tasks type.
                if child["name"].lower() != task["type"]["name"].lower():
                    continue

                # Collect all users from group.
                for membership in child["memberships"]:
                    status_users.add(membership["user"])

        # Assign members to task.
        assigned_users = []
        for user in status_users:
            if user in task_users:
                continue

            session.create(
                "Appointment",
                {
                    "context": task,
                    "resource": user,
                    "type": "assignment"
                }
            )
            assigned_users.append(user)

        # Storing new assignees.
        task["metadata"].update(
            {"assignees": ",".join([user["id"] for user in assigned_users])}
        )

        session.commit()


def register(session, **kw):
    # Subscribe to events with the update topic.
    session.event_hub.subscribe("topic=ftrack.update", callback)


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

    # Set up basic logging
    logging.basicConfig(level=loggingLevels[namespace.verbosity])

    session = ftrack_api.Session()
    register(session)

    # Wait for events
    logging.info(
        "Registered actions and listening for events. Use Ctrl-C to abort."
    )
    session.event_hub.wait()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
