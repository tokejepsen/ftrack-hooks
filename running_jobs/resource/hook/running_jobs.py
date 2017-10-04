import ftrack_api
from ftrack_hooks.action import BaseAction


class RunningJobsAction(BaseAction):
    """Running Jobs action

    `label` a descriptive string identifing your action.

    `varaint` To group actions together, give them the same
    label and specify a unique variant per action.

    `identifier` a unique identifier for your action.

    `description` a verbose descriptive text for you action
     """
    label = "Running Jobs"
    variant = None
    identifier = "running-jobs"
    description = None

    def __init__(self, session):
        """Expects a ftrack_api.Session instance"""
        super(RunningJobsAction, self).__init__(session)

    def discover(self, session, entities, event):

        return True

    def launch(self, session, entities, event):

        if "values" in event["data"]:

            status = event["data"]["values"]["status"]

            running_jobs = session.query("Job where status is \"running\"")
            for job in running_jobs:
                job["status"] = status

            session.commit()

            return {
                'success': True,
                'message': 'Action completed successfully'
            }

        return {
            "success": True,
            "message": "",
            "items": [
                {
                    "label": "Set running jobs to:",
                    "type": "enumerator",
                    "name": "status",
                    "data": [
                        {"label": "Failed", "value": "failed"},
                        {"label": "Done", "value": "done"}
                    ]
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
    action = RunningJobsAction(session)
    action.register()
