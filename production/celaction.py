import os
import sys
import shutil
import getpass
import subprocess
import traceback
import logging
import socket
import getpass
import time

import ftrack

log = logging.getLogger(__name__)

identifier = 'toot.celaction.%s' % os.getenv('username')

def register(registry, **kw):
    results = []
    temp = ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.action.discover and source.user.username={0}'.format(
            getpass.getuser()
        ),
        discover
    )
    results.append(temp)
    temp = ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.action.launch and source.user.username={0} '
        'and data.actionIdentifier={1}'.format(
            getpass.getuser(), identifier),
        launch
        )
    results.append(temp)

    return results

def discover(event):
    '''Return action config if triggered on a single asset version.'''
    data = event['data']

    # If selection contains more than one item return early since
    # this action can only handle a single version.
    selection = data.get('selection', [])

    if len(selection) != 1 or selection[0].get('entityType') != 'task':
        return

    if not os.path.exists(r'C:\Program Files (x86)\CelAction\CelAction2D.exe'):
        return

    return {
        'items': [{
            'label': 'CelAction',
            'actionIdentifier': identifier
        }]
    }

def launch(event):
    '''Callback method for custom action.'''

    success = True
    msg = 'CelAction application started.'

    if event['data']['actionIdentifier'] == identifier:

        taskid = event['data']['selection'][0]['entityId']
        try:
            launchCelaction(taskid)
        except:
            log.error(traceback.format_exc())
            success = False
            msg = 'CelAction application start failed!'

    return {'success': success, 'message': msg}

def launchCelaction(taskid):
    task = ftrack.Task(id=taskid)
    step = task.getType().getName()
    parents = task.getParents()

    showName = None
    sequenceName = None
    shotName = None
    episodeNum = None
    episodeName = None
    #get common variables
    for parent in parents:
        if parent.get('entityType') == 'show':
            showName = parent.getName()
        elif parent.get('entityType') == 'task':
            if parent.getObjectType() == 'Shot':
                shotName = parent.getName()
            elif parent.getObjectType() == 'Sequence':
                sequenceName = parent.getName()
            elif parent.getObjectType() == 'Episode':
                episodeNum = parent.getName()
                episodeName = parent.getDescription()


    """Prepares paths. This is very production specific and should be eventually replaced with something more flexible"""
    episodeFolder = showName + '_' + episodeNum + '_' + episodeName
    if step == 'Animation':
        animSceneFolder = os.path.join('Q:\\', showName, 'episodes', episodeFolder, step, shotName)
    layoutSceneFolder = os.path.join('Q:\\', showName, 'episodes', episodeFolder, step,'build', sequenceName)
    layoutScenePublishFolder = os.path.join('Q:\\', showName, 'episodes', episodeFolder, 'Layout', 'publish')
    layoutWorkFileName = showName + '_' + episodeNum  + '_' + sequenceName + '_' + '0001.scn'
    emptyCelactionScene = r"K:\ftrack-event-plugins\hook\celaction_empty.scn"
    scenePath = ''

    log.debug('\n*******************************************************************************\n')

    username = os.getenv('username').split('.')[0]

    log.debug('Hi ' + username.title() + '\n')

    if shotName and sequenceName:
        log.debug('You are working in context: ' + showName + ' / ' + episodeNum + ' / ' + sequenceName + ' / ' + shotName + ' / ' + step + '\n')
    elif sequenceName:
        log.debug('You are working in context: ' + showName + ' / ' + episodeNum + ' / ' + sequenceName+ ' / ' + step + '\n')
    elif shotName:
        log.debug('You are working in context: ' + showName + ' / ' + episodeNum + ' / ' + shotName + ' / ' + step + '\n')
    elif episodeNum:
        log.debug('You are working in context: ' + showName + ' / ' + episodeNum + ' / ' + step + '\n')
    elif showName:
        log.debug('You are working in context: ' + showName + ' / ' + step + '\n')


    ###############################################################
    ## Execute script based on gives rules
    ###############################################################

    if step == 'Animation':
        #grab all the cellaction scenefiles from the folder
        scenes = []
        for f in os.listdir(animSceneFolder ):
            if f.endswith(".scn"):
                scenes.append(os.path.join(animSceneFolder, f))

        #find the latest file version
        if len(scenes)>0:
            log.debug('Found working Animation scenes \n')
            versionNumber = 0
            for file in scenes:
                (filepath, filename) = os.path.split(file)
                (basename, extension) = os.path.splitext(filename)
                version = int(basename.split('_')[-1])
                if version > versionNumber:
                    scenePath = file
                    versionNumber = version
        else:
            log.debug('No Animation scenes found, creating new from published layout \n')
            publishedFiles = []
            for f in os.listdir(layoutScenePublishFolder ):
                if f.endswith(".scn"):
                    publishedFiles.append(os.path.join(layoutScenePublishFolder, f))
            found = None
            for file in publishedFiles:
                """NEEDS TO EVENTUALLY JUST CHECK THROUGH THE WHOLE STRING"""
                (filepath, filename) = os.path.split(file)
                (basename, extension) = os.path.splitext(filename)
                shotFromFile = basename.split('_')[-1]
                if shotFromFile == shotName:
                    log.debug('found matching publish')
                    fileToCopy = file
                    target = os.path.join(animSceneFolder, (basename + '_0001' + extension))
                    if not os.path.exists(animSceneFolder):
                        os.makedirs(animSceneFolder)
                    shutil.copy(fileToCopy, target)
                    scenePath = target
                    found = 1
                    log.debug('Created Version 0001 of Animation scene from published layout \n')
                    log.debug('Opening scene: ' + scenePath + '\n')

            if not found:
                log.error('Couldn\'t find Layout scene for this shot. It probably wasn\'t published yet. \n')

    elif step == 'Layout':
        #grab all the cellaction scenefiles from the folder
        scenes = []
        for f in os.listdir(layoutSceneFolder ):
            if f.endswith(".scn"):
                scenes.append(os.path.join(layoutSceneFolder, f))

        #find the latest file version
        if len(scenes)==1:
            versionNumber = '0001'
            (filepath, filename) = os.path.split(scenes[0])
            (basename, extension) = os.path.splitext(filename)
            newBaseName = basename + '_' + versionNumber
            scenePath = os.path.join(filepath, (newBaseName + extension))
            os.rename(scenes[0], scenePath)
        elif len(scenes)>1:
            log.debug('Found working Layout scene')
            versionNumber = 0
            for file in scenes:
                (filepath, filename) = os.path.split(file)
                (basename, extension) = os.path.splitext(filename)
                version = int(basename.split('_')[-1])
                if version > versionNumber:
                    scenePath = file
                    versionNumber = version
        else:
            log.debug('No Layout scenes found, creating fresh scene \n')
            fileToCopy = emptyCelactionScene
            target= os.path.join(layoutSceneFolder, layoutWorkFileName)
            shutil.copy(fileToCopy, target)
            scenePath = target
            log.debug('Created Version 0001 of Layout scene\n')

        log.debug('Opening scene: ' + scenePath + '\n')

    else:
        cmd = "\"C:\\Program Files (x86)\\CelAction\\CelAction2D.exe\""

    app = r'C:\\Program Files (x86)\\CelAction\\CelAction2D.exe'
    if os.path.exists(scenePath):
        subprocess.Popen([app, scenePath])
    else:
        subprocess.Popen([app])
