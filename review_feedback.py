import sys
import logging
import os
import getpass
import threading
import traceback
import json
import tempfile
import uuid

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.INFO)

if __name__ == '__main__':
    tools_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.append(os.path.join(tools_path, 'ftrack', 'ftrack-api'))

import ftrack


def async(fn):
    '''Run *fn* asynchronously.'''
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()
    return wrapper


class ReviewFeedback(ftrack.Action):
    '''Custom action.'''

    #: Action identifier.
    identifier = 'review.feedback'

    #: Action label.
    label = 'ReviewFeedback'

    def __init__(self):
        '''Initialise action handler.'''
        self.logger = logging.getLogger(
            __name__ + '.' + self.__class__.__name__
        )

    def register(self):
        '''Register action.'''
        ftrack.EVENT_HUB.subscribe(
            'topic=ftrack.action.discover and source.user.username={0}'.format(
                getpass.getuser()
            ),
            self.discover
        )

        ftrack.EVENT_HUB.subscribe(
            'topic=ftrack.action.launch and source.user.username={0} '
            'and data.actionIdentifier={1}'.format(
                getpass.getuser(), self.identifier
            ),
            self.launch
        )

    def discover(self, event):
        '''Return action config if triggered on a single selection.'''
        data = event['data']

        # If selection contains more than one item return early since
        # this action will only handle a single version.
        selection = data.get('selection', [])

        entityType = selection[0]['entityType']
        if entityType != 'reviewsession':
            return

        return {
            'items': [{
                'label': self.label,
                'actionIdentifier': self.identifier,
            }]
        }

    def generate_feedback(self, event):
        data = event['data']
        selection = data.get('selection', [])
        session = ftrack.ReviewSession(selection[0]['entityId'])

        invitees = {}
        for invite in session.getInvitees():
            invitees[invite.get('id')] = invite.get('name')

        session_objects = {}
        for obj in session.getObjects():
            notes = {'frames': [], 'non_frame': []}
            for note in obj.getNotes():
                meta = note.getMeta()
                data = {'text': note.get('text'),
                        'invitee': invitees[meta['inviteeId']],
                        'replies': []}

                for reply in note.getNotes():
                    data['replies'].append(reply)

                if 'reviewFrame' in note.getMeta():
                    frame_number = json.loads(meta['reviewFrame'])['number']
                    notes['frames'].append(frame_number)

                    if str(frame_number) in notes:
                        notes[str(frame_number)].append(data)
                    else:
                        notes[str(frame_number)] = [data]
                else:
                    notes['non_frame'].append(data)

            session_objects[obj.get('name')] = notes

        text = ''
        for obj in session_objects:
            text += obj + ':\n\n\n'
            frames = list(set(session_objects[obj]['frames']))
            frames.sort()
            for frame in frames:
                text += 'Frame: %s ' % str(frame) + '-' * 50 + '\n\n'
                for note in session_objects[obj][str(frame)]:
                    text += note['invitee'] + ':\n'
                    text += note['text'] + '\n'

                    for reply in note['replies']:
                        text += '\n'
                        text += invitees[reply.getMeta()['inviteeId']] + ':\n'
                        text += reply.get('text') + '\n'

                    text += '\n'
                text += '\n\n'
            text += '-' * 50

        f = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()) + ".txt")
        with open(f, 'w') as temp_file:
            temp_file.write(text)

        return f

    @async
    def create_job(self, event):
        job = ftrack.createJob('Generating Feedback', 'queued',
                               ftrack.User(id=event['source']['user']['id']))
        job.setStatus('running')

        try:
            f = self.generate_feedback(event)
            job.createAttachment(f, fileName=f)
            os.remove(f)
        except:
            logger.error(traceback.format_exc())
            job.setStatus('failed')
        else:
            job.setStatus('done')

    def launch(self, event):

        self.create_job(event)

        return {
            'success': True,
            'message': 'Review Feedback Generating!'
        }


def register(registry, **kw):
    # Validate that registry is the correct ftrack.Registry. If not,
    # assume that register is being called with another purpose or from a
    # new or incompatible API and return without doing anything.
    if registry is not ftrack.EVENT_HANDLERS:
        # Exit to avoid registering this plugin again.
        return

    '''Register action. Called when used as an event plugin.'''
    action = ReviewFeedback()
    action.register()


if __name__ == '__main__':
    ftrack.setup()
    action = ReviewFeedback()
    action.register()

    ftrack.EVENT_HUB.wait()
