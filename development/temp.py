# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack
import argparse
import os
import sys
import logging
import threading
import datetime
import time
import uuid

import sys
sys.path.append(r'K:\tools\FTrack\ftrack-api')

import ftrack
#from docraptor import DocRaptor

def async(fn):
    '''Run *fn* asynchronously.'''
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()
    return wrapper

def getEntity(entityType=None, entityId=None):
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
def getPath(entityType=None, entity=None):
    parents=[]
    path = ''
    try:
        parents = entity.getParents()
    except:
        pass
    for i in parents[:-1]:
        path = (i.getName()) + " / " + path
    return path

def getEntityPath(entityType=None, entity=None):
    if entity is None:
        return

    if entityType == 'user':
        return ' **' + entity.getName()  + '**  *(' + entityType + ')*'

    path=''
    parents=[]

    try:
        parents = entity.getParents()
    except:
        pass
    for i in parents:
        path = (i.getName()) + " / " + path
    path='  **' + path + entity.get('name') + '**  *(' + (entityType if entityType != 'show' else 'project') + ')*'
    return path

def getEntityChildren(entityType=None, entity=None):
    '''Get children for Projects, Tasks(sequences and shots) and Lists'''
    if entityType == 'list':
        return entity.getObjects()
    if entityType == 'task':
        return entity.getChildren(depth=1)
    if entityType == 'show':
        return entity.getChildren(depth=2)
    if entityType == 'reviewsession':
        #a bit more complex
        reviewEntities = entity.reviewSessionObjects()
        lst = []
        for i in reviewEntities:
            #get the id of the published version from review session object
            v = ftrack.AssetVersion(id=i.get('version_id'))
            lst.append(v)
        return lst
    return []

def getName(entityType=None, entity=None):
    if entityType != 'reviewsession':
        return xstr(entity.get('name'))
    else:
        return xstr(entity.getParent().get('name'))

def getDescription(entityType=None, entity=None):
    if entityType != 'reviewsession':
        return xstr(entity.getDescription())
    else:
        return xstr(entity.getComment())

def getState(entityType=None, entity=None):
    try:
        state =  xstr(entity.getStatus().getState())
        if state == "NOT_STARTED":
            return ('bg-warning', 'Not started')
        if state == "IN_PROGRESS":
            return ('bg-info', 'In progress')
        if state == "BLOCKED":
            return ('bg-danger', 'Blocked')
        if state == "DONE":
            return ('bg-success', 'Completed')
    except:
        return ('','')

def xstr(s):
    try:
        if s is None:
            return ''
        return s
    except:
        return ''

@async
def create(userId=None, entityType=None, entity=None, values=None):
    return createPDF(userId=userId,entityType=entityType, entity=entity, values=values)

def createPDF(userId=None, entityType=None, entity=None, values=None):
    description = u'Project boards'
    job = ftrack.createJob(
        description=description,
        status='running',
        user=userId
    )
    try:
        style=values['style']

        html = "\
                <html>\
                    <head>\
                        <style>\
                            @page { padding: 10pt}\
                            @page { margin: 0em; }\
                            @page { size: A4}\
                            @page { size: A4 landscape }\
                            img { page-break-inside: avoid; }\
                            .break { clear:both; page-break-after:always; }\
                            td, th { page-break-inside: avoid; }\
                        </style>\
                        <link rel='stylesheet' href='https://maxcdn.bootstrapcdn.com/bootstrap/3.3.2/css/bootstrap.min.css'>\
                        <link rel='stylesheet' href='https://maxcdn.bootstrapcdn.com/bootstrap/3.3.2/css/bootstrap-theme.min.css'>\
                    </head>\
                    <body>"

        if style=="rows" or style=="rows-compact":
            html = html + "\
                        <table class='table " + ("table-condensed" if style=="rows-compact" else '') + "'>\
                            <tr>\
                                <th style='min-width:3px; max-width:3px; width:3px'></th>\
                                <th>Thumbnail</th>\
                                <th>Name</th>\
                                <th>Description</th>\
                            </tr>"
            lst = getEntityChildren(entityType, entity)
            for i in lst:
                state = getState(entityType=entityType, entity=i)
                html = html + "\
                            <tr>\
                                <td class='" + state[0] + "' style='min-width:3px; max-width:3px;'></td>\
                                <td style='" + ("width:100px; height:65px;" if style=="rows-compact" else 'width:200px; height:130px;') + "'><img class='img-responsive' src='" + xstr(i.getThumbnail()) + "'></td>\
                                <td style='width:200px;'><small><strong>" + getName(entityType=entityType, entity=i) +"</strong></small>\
                                    <p class='text-muted small'>" + getPath(entityType=entityType, entity=i) + "</p>\
                                </td>\
                                <td style=''><small>" + getDescription(entityType=entityType, entity=i) + "</small></td>\
                            </tr>"
            html = html + "\
                        </table>"

        if style == "grid":
            html = html + "\
                        <table class='table table-bordered'>"

            lst = getEntityChildren(entityType, entity)
            for j, i in enumerate(lst, start = 4):
                state = getState(entityType=entityType, entity=i)
                if (j % 4) is 0:
                    html = html + "\
                            <tr>"

                html= html + "\
                                <td style='width:200px; height:130px; vertical-align:bottom'>\
                                    <center><img class='img-responsive' src='" + xstr(i.getThumbnail()) + "'></center><br/>\
                                    <small><strong>" + getName(entityType=entityType, entity=i) +"</strong></small>\
                                    <p class='text-muted small'>" + getPath(entityType=entityType, entity=i) + "</p>\
                                    <div class='" + state[0] + " small' style='padding:5px; text-align: center;'>" + state[1] + "</div> \
                                </td>"
                if (j+5 % 4) is 0:
                    html = html + "\
                            </tr>"

            html = html + "\
                        </table>"

        html= html + "\
                    </body>\
                </html>"

        # html alternative to create PDF (see below)
        filename = "board-{0}.html".format(str(uuid.uuid1()))
        html_file= open(filename,"w")
        html_file.write(html.encode("utf-8"))
        html_file.close()
        job.createAttachment(filename, fileName=filename)


        #signup for docraptor (free trial) or use other PDF generator library
        #install docraptor with "pip install python-docraptor"

        # docraptor = DocRaptor(ADD YOUR API KEY HERE)
        # filename = "board-{0}.pdf".format(str(uuid.uuid1()))
        # resp = docraptor.create({
        #                             'document_content': html,
        #                             'document_type':'pdf',
        #                             'test': False,
        #                             'strict': 'none',
        #                             'async': True,
        #                             'prince_options': {'media': 'screen', 'insecure':False, 'input':'html'}
        #                             })

        # status_id = resp['status_id']
        # resp = docraptor.status(status_id)
        # while resp['status'] != 'completed':
        #     time.sleep(3)
        #     resp = docraptor.status(status_id)
        # f = open(filename, 'w+b')
        # f.write(docraptor.download(resp['download_key']).content)
        # f.seek(0)
        # job.createAttachment(f, fileName=filename)

        job.setStatus('done')
        os.remove(filename)
    except:
        job.setStatus('failed')

class PDFBoards(ftrack.Action):
    '''Generate row or grid based boards based on selection.'''

    label = 'PDF Boards (Entities)'
    identifier = 'com.ftrack.pdfboards'

    def discover(self, event):
        '''Return action config if triggered on a single selection.'''
        data = event['data']

        # If selection contains more than one item return early since
        # this action can only handle a single version.
        selection = data.get('selection', [])
        self.logger.info('Got selection: {0}'.format(selection))
        if len(selection) != 1:
            return

        return {
            'items': [{
                'label': self.label,
                'actionIdentifier': self.identifier,
                'icon':"https://www.ftrack.com/wp-content/uploads/reports1.png"
            }]
        }

    def launch(self, event):
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
            create(userId=userId, entityType=entityType, entity=entity, values=values)
            return

        return {
            'items': [
                {
                    'type': 'label',
                    'value': 'Your selection: ' + getEntityPath(entityType=entityType, entity=entity)
                }, {
                    'type': 'label',
                    'value': '___'
                }, {
                    'label': 'Select data',
                    'type': 'enumerator',
                    'name': 'select_columns',
                    'value':'0',
                    'data': [
                    {
                    'label': 'Thumbnail / Name / Description',
                    'value': '0'
                }, {
                    'label': 'Thumbnail / Name / Description',
                    'value': '1'
                }]
                },{
                    'type': 'label',
                    'value': '___'
                },{
                    'label': 'Select layout',
                    'type': 'enumerator',
                    'name': 'style',
                    'value':'rows',
                    'data': [
                    {
                    'label': 'Rows',
                    'value': 'rows'
                }, {
                    'label': 'Compact rows',
                    'value': 'rows-compact'
                }, {
                    'label': 'Grid',
                    'value': 'grid'
                }]
                }
            ]
        }

def main(arguments=None):
    '''Set up logging and register action.'''
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
        '-v', '--verbosity',
        help='Set the logging output verbosity.',
        choices=loggingLevels.keys(),
        default='info'
    )
    namespace = parser.parse_args(arguments)

    # Set up basic logging
    logging.basicConfig(level=loggingLevels[namespace.verbosity])
    logging.basicConfig(level=logging.INFO)

    ftrack.setup()
    action = PDFBoards()
    action.register()

    ftrack.EVENT_HUB.wait()


if __name__ == '__main__':
    main()
