# :coding: utf-8
import logging


class BaseAction(object):
    '''Custom Action base class

    `label` a descriptive string identifing your action.

    `varaint` To group actions together, give them the same
    label and specify a unique variant per action.

    `identifier` a unique identifier for your action.

    `description` a verbose descriptive text for you action

     '''
    label = None
    variant = None
    identifier = None
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
                    'variant': self.variant,
                    'description': self.description,
                    'actionIdentifier': self.identifier,

                }]
            }

    def discover(self, session, entities, event):
        '''Return true if we can handle the selected entities.

        *session* is a `ftrack_api.Session` instance


        *entities* is a list of tuples each containing the entity type and the
        entity id.
        If the entity is a hierarchical you will always get the entity
        type TypedContext, once retrieved through a get operation you
        will have the "real" entity type ie. example Shot, Sequence
        or Asset Build.

        *event* the unmodified original event

        '''

        return False

    def _translate_event(self, session, event):
        '''Return *event* translated structure to be used with the API.'''

        _selection = event['data'].get('selection', [])

        _entities = list()
        for entity in _selection:
            _entities.append(
                (
                    self._get_entity_type(entity), entity.get('entityId')
                )
            )

        return [
            _entities,
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

    def launch(self, session, entities, event):
        '''Callback method for the custom action.

        return either a bool ( True if successful or False if the action
        failed ) or a dictionary with they keys `message` and `success`, the
        message should be a string and will be displayed as feedback to the
        user, success should be a bool, True if successful or False if the
        action failed.

        *session* is a `ftrack_api.Session` instance

        *entities* is a list of tuples each containing the entity type and the
        entity id.
        If the entity is a hierarchical you will always get the entity
        type TypedContext, once retrieved through a get operation you
        will have the "real" entity type ie. example Shot, Sequence
        or Asset Build.

        *event* the unmodified original event

        '''
        raise NotImplementedError()

    def _interface(self, *args):
        interface = self.interface(*args)

        if interface:
            return {
                'items': interface
            }

    def interface(self, session, entities, event):
        '''Return a interface if applicable or None

        *session* is a `ftrack_api.Session` instance

        *entities* is a list of tuples each containing the entity type and the
        entity id.
        If the entity is a hierarchical you will always get the entity
        type TypedContext, once retrieved through a get operation you
        will have the "real" entity type ie. example Shot, Sequence
        or Asset Build.

        *event* the unmodified original event
        '''
        return None

    def _handle_result(self, session, result, entities, event):
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
