import logging

import ftrack_api


class BatchTasksAction(object):
    '''Batch Tasks action

    `label` a descriptive string identifing your action.

    `varaint` To group actions together, give them the same
    label and specify a unique variant per action.

    `identifier` a unique identifier for your action.

    `description` a verbose descriptive text for you action
     '''
    label = "Batch Tasks"
    variant = None
    identifier = "batch-tasks"
    description = None

    def __init__(self, session):
        '''Expects a ftrack_api.Session instance'''

        self.logger = logging.getLogger(
            '{0}.{1}'.format(__name__, self.__class__.__name__)
        )

        if self.label is None:
            raise ValueError(
                'Action missing label.'
            )

        elif self.identifier is None:
            raise ValueError(
                'Action missing identifier.'
            )

        self._session = session

    @classmethod
    def clone_session(cls, session):
        assert (
            isinstance(session, ftrack_api.Session)
        ), 'Must be ftrack_api.Session instance.'

        return ftrack_api.Session(
            session.server_url, session.api_key, session.api_user
        )

    def register(self):
        '''Registers the action, subscribing the the discover and launch
        topics.'''
        self._session.event_hub.subscribe(
            'topic=ftrack.action.discover', self._discover
        )

        self._session.event_hub.subscribe(
            'topic=ftrack.action.launch and data.actionIdentifier={0}'.format(
                self.identifier
            ),
            self._launch
        )

    def _discover(self, event):
        args = self._translate_event(
            self._session, event
        )

        accepts = self.discover(
            self._session, *args
        )

        if accepts:
            return {
                'items': [{
                    'label': self.label,
                    'varian': self.variant,
                    'description': self.description,
                    'actionIdentifier': self.identifier,

                }]
            }

    def discover(self, session, uid, entities, source, values, event):
        '''Return true if we can handle the selected entities.

        *session* is a `ftrack_api.Session` instance

        *uid* is the unique identifier for the event

        *entities* is a list of tuples each containing the entity type and
        the entity id.
        If the entity is a hierarchical you will always get the entity
        type TypedContext, once retrieved through a get operation you
        will have the "real" entity type ie. example Shot, Sequence
        or Asset Build.

        *source* dictionary containing information about the source of the
        event, application id, current user etc.

        *values* is a dictionary containing potential user settings

        *event* the unmodified original event
        '''

        # Only discover the action if any selection is made.
        if entities:
            return True

        return False

    def _translate_event(self, session, event):
        '''Return *event* translated structure to be used with the API.'''

        _uid = event['source']['id']
        _source = event['source']

        _values = event['data'].get('values', {})
        _selection = event['data'].get('selection', [])

        _entities = list()
        for entity in _selection:
            _entities.append(
                (
                    self._get_entity_type(entity), entity.get('entityId')
                )
            )

        return [
            _uid,
            _entities,
            _source,
            _values,
            event
        ]

    def _get_entity_type(self, entity):
        '''Return translated entity type tht can be used with API.'''
        entity_type = entity.get('entityType')
        object_typeid = None

        for schema in self._session.schemas:
            alias_for = schema.get('alias_for')

            if (
                alias_for and isinstance(alias_for, dict) and
                alias_for['id'].lower() == entity_type and
                object_typeid == alias_for.get(
                    'classifiers', {}
                ).get('object_typeid')
            ):

                return schema['id']

        for schema in self._session.schemas:
            alias_for = schema.get('alias_for')

            if (
                alias_for and isinstance(alias_for, basestring) and
                alias_for.lower() == entity_type
            ):
                return schema['id']

        for schema in self._session.schemas:
            if schema['id'].lower() == entity_type:
                    return schema['id']

        raise ValueError(
            'Unable to translate entity type.'
        )

    def _launch(self, event):
        args = self._translate_event(
            self._session, event
        )

        interface = self._interface(
            self._session, *args
        )

        if interface:
            return interface

        response = self.launch(
            self._session, *args
        )

        return self._handle_result(
            self._session, response, *args
        )

    def launch(self, session, uid, entities, source, values, event):
        '''Callback method for the custom action.

        return either a bool (True if successful or False if the action failed)
        or a dictionary with they keys `message` and `success`, the message
        should be a string and will be displayed as feedback to the user,
        success should be a bool, True if successful or False if the action
        failed.

        *session* is a `ftrack_api.Session` instance

        *uid* is the unique identifier for the event

        *entities* is a list of tuples each containing the entity type and the
        entity id.
        If the entity is a hierarchical you will always get the entity
        type TypedContext, once retrieved through a get operation you
        will have the "real" entity type ie. example Shot, Sequence
        or Asset Build.

        *source* dictionary containing information about the source of the
        event, application id, current user etc.

        *values* is a dictionary containing potential user settings
        from previous runs.

        *event* the unmodified original event

        '''
        if 'values' in event['data']:
            values = event['data']['values']
            if 'number_of_tasks' in values:
                items = []
                TASK_TYPE_ENUMERATOR_OPTIONS = [
                    {'label': task_type["name"], 'value': task_type["id"]}
                    for task_type in session.query("Type")
                ]
                for index in range(0, int(values['number_of_tasks'])):
                    items.extend(
                        [
                            {
                                'value': '##Template for Task{0}##'.format(
                                    index
                                ),
                                'type': 'label'
                            },
                            {
                                'label': 'Type',
                                'type': 'enumerator',
                                'name': 'task_{0}_typeid'.format(index),
                                'data': TASK_TYPE_ENUMERATOR_OPTIONS
                            },
                            {
                                'label': 'Name',
                                'type': 'text',
                                'name': 'task_{0}_name'.format(index)
                            }
                        ]
                    )

                return {'success': True, 'message': '', 'items': items}
            else:
                # Create tasks on each entity
                for entity_type, entity_id in entities:
                    entity = session.get(entity_type, entity_id)
                    for count in range(0, len(values.keys()) / 2):
                        task_type = session.query(
                            'Type where id is "{0}"'.format(
                                values["task_{0}_typeid".format(count)]
                            )
                        ).one()

                        # Get name, or assume task type in lower case as name.
                        name = values["task_{0}_name".format(count)]
                        if not name:
                            name = task_type["name"].lower()

                        # Query for existing task.
                        query = (
                            'Task where type.id is "{0}" and name is "{1}" '
                            'and parent.id is "{2}"'
                        )
                        task = session.query(
                            query.format(
                                values["task_{0}_typeid".format(count)],
                                name,
                                entity["id"]
                            )
                        ).first()

                        # Create task.
                        if not task:
                            task = session.create(
                                "Task",
                                {
                                    "name": name,
                                    "type": task_type,
                                    "parent": entity
                                }
                            )

                return {
                    'success': True,
                    'message': 'Action completed successfully'
                }

        return {
            'success': True,
            'message': "",
            'items': [
                {
                    'label': 'Number of tasks',
                    'type': 'number',
                    'name': 'number_of_tasks',
                    'value': 2
                }
            ]
        }

    def _interface(self, *args):
        interface = self.interface(*args)

        if interface:
            return {
                'items': interface
            }

    def interface(self, session, uid, entities, source, values, event):
        '''Return a interface if applicable or None

        *session* is a `ftrack_api.Session` instance

        *uid* is the unique identifier for the event

        *entities* is a list of tuples each containing the entity type and the
        entity id.
        If the entity is a hierarchical you will always get the entity
        type TypedContext, once retrieved through a get operation you
        will have the "real" entity type ie. example Shot, Sequence
        or Asset Build.

        *source* dictionary containing information about the source of the
        event, application id, current user etc.

        *values* is a dictionary containing potential user settings
        from previous runs.

        *event* the unmodified original event
        '''
        return None

    def _handle_result(
            self, session, result, uid, entities, source, values, event):
        '''Validate the returned result from the action callback'''
        if isinstance(result, bool):
            result = {
                'success': result,
                'message': (
                    '{0} launched successfully.'.format(
                        self.label
                    )
                )
            }

        elif isinstance(result, dict):
            for key in ('success', 'message'):
                if key in result:
                    continue

                raise KeyError(
                    'Missing required key: {0}.'.format(key)
                )

        else:
            self.logger.error(
                'Invalid result type must be bool or dictionary!'
            )
        session.commit()
        return result


def register(session):

    # Validate that session is an instance of ftrack_api.Session. If not,assume
    # that register is being called from an old or incompatible API and return
    # without doing anything.
    if not isinstance(session, ftrack_api.Session):
        return

    # Create action and register to respond to discover and launch actions.
    action = BatchTasksAction(session)
    action.register()
