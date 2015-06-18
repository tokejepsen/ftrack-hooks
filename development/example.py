# :coding: utf-8
import os
import logging
import uuid

import sys
sys.path.append(r'K:\tools\FTrack\ftrack-api')

import ftrack

def getEntity(entityType=None, entityId=None):
    ''' A helper to get Entity object '''
    if entityType is None or entityId is None:
        return None
    if entityType == 'user':
        return ftrack.User(entityId)
    if entityType == 'show':
        return ftrack.Project(entityId)
    elif entityType == 'task':
        return ftrack.Task(entityId)
    elif entityType == 'list':
        return ftrack.List(entityId)
    elif entityType == 'reviewsession':
        return ftrack.ReviewSession(entityId)
    else:
        return None

def doSomething(userId=None, entityType=None, entity=None, values=None):
    description = u'Running Example Job'
    job = ftrack.createJob(
        description=description,
        status='running',
        user=userId
    )
    try:
        color=values['color']

        html = "\
                <html>\
                    <head>\
                        <link rel='stylesheet' href='https://maxcdn.bootstrapcdn.com/bootstrap/3.3.2/css/bootstrap.min.css'>\
                        <link rel='stylesheet' href='https://maxcdn.bootstrapcdn.com/bootstrap/3.3.2/css/bootstrap-theme.min.css'>\
                    </head>\
                    <body>\
                       <h3>My Example Selection <span class='label {0}''>{1}</span></h3>\
                    </body>\
                </html>".format('label-success' if color == 'green' else 'label-info', entity.get('name'))

        # have a html file to attach to job list
        filename = "example-{0}.html".format(str(uuid.uuid1()))
        f= open(filename,"w")
        f.write(html)
        f.close()

        job.createAttachment(filename, fileName=filename)
        job.setStatus('done')
        job.setDescription("You color is {0}".format(color))
        os.remove(filename)
    except:
        job.setStatus('failed')

class Example(ftrack.Action):
    '''A simple Action example'''

    label = 'My Example Action'
    identifier = 'com.ftrack.{0}'.format(str(uuid.uuid1()))

    def discover(self, event):
        '''Return action config if triggered on a single selection.'''
        data = event['data']

        # If selection contains more than one item return early since
        # this action will only handle a single version.
        selection = data.get('selection', [])
        entityType = selection[0]['entityType']
        self.logger.info('Got selection: {0}'.format(selection))
        if len(selection) != 1 or entityType == 'user':
            return

        return {
            'items': [{
                'label': self.label,
                'actionIdentifier': self.identifier,
                'icon':"https://www.ftrack.com/wp-content/uploads/reports1.png"
            }]
        }

    def launch(self, event):
        # get id of user invoking this action
        userId = event['source']['user']['id']
        data = event['data']
        selection = data.get('selection', [])
        entityId = selection[0]['entityId']
        entityType = selection[0]['entityType']
        entity = getEntity(entityType=entityType, entityId=entityId)
        if 'values' in event['data']:
            # Do something with the values or return a new form.
            values = event['data']['values']
            ftrack.EVENT_HUB.publishReply(
                event,
                data={
                    'success': True,
                    'message': 'Action was successful'
                }
            )
            doSomething(userId=userId, entityType=entityType, entity=entity, values=values)
            return

        return {
            'items': [
                {
                    'type': 'label',
                    'value': 'Your selection: {0}'.format(entity.get('name'))
                }, {
                    'type': 'label',
                    'value': '___'
                }, {
                    'label': 'Select color',
                    'type': 'enumerator',
                    'name': 'color',
                    'value':'green',
                    'data': [
                    {
                    'label': 'Green',
                    'value': 'green'
                }, {
                    'label': 'Blue',
                    'value': 'blue'
                }]
                }
            ]
        }

def main():
    '''Register action and listen for events.'''
    logging.basicConfig(level=logging.INFO)

    ftrack.setup()
    action = Example()
    action.register()

    ftrack.EVENT_HUB.wait()

if __name__ == '__main__':
    main()
