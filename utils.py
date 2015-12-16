import os
import tempfile
import subprocess
import operator
import sys

tools_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(os.path.join(tools_path, 'ftrack', 'ftrack-api'))

import ftrack


def GetFtrackConnectPath():
    return os.path.join(tools_path, 'ftrack', 'ftrack-connect-package',
                        'windows', 'current')

def GetStatusByName(entity, name):
    project = entity.getParents()[-1]
    statuses = project.getTaskStatuses()

    result = None
    for s in statuses:
        if s.get('name').lower() == name.lower():
            result = s

    return result

def GetNextTask(task):
    shot = task.getParent()
    tasks = shot.getTasks()
    project = shot.getParents()[-1]

    def sort_types(types):
        data = {}
        for t in types:
            data[t] = t.get('sort')

        data = sorted(data.items(), key=operator.itemgetter(1))
        results = []
        for item in data:
            results.append(item[0])

        return results

    types_sorted = sort_types(project.getTaskTypes())

    next_type = None
    for t in types_sorted:
        if t.get('name') == task.get('name'):
            try:
                next_type = types_sorted[types_sorted.index(t) + 1]
            except:
                pass

    next_task = None
    if next_type:
        for t in tasks:
            if t.get('name').lower() == next_type.get('name').lower():
                next_task = t

    return next_task

def getLatestVersion(versions):
    latestVersion = None
    if len(versions) > 0:
        versionNumber = 0
        for item in versions:
            if item.get('version') > versionNumber:
                versionNumber = item.getVersion()
                latestVersion = item
    return latestVersion

def getShots(entity):
    result = []

    if entity.get('objecttypename') == 'Task':
        for parent in entity.getParents():
            try:
                if parent.get('objecttypename') == 'Shot':
                    result.append(parent)
            except:
                pass

    if entity.get('objecttypename') == 'Shot':
        result.append(entity)

    if entity.get('objecttypename') == 'Sequence':
        for shot in entity.getShots():
            result.extend(getShots(shot))

    if entity.get('objecttypename') == 'Episode':
        for seq in entity.getSequences():
            result.extend(getShots(seq))

    return result

def submitQT(version):
    component = version.getComponent('main')
    filePath = component.getFile()
    settingsPath = r'K:\ftrack\ftrack.git\quicktime_export_settings.xml'
    settingsPath =settingsPath.replace('\\', '/')

    #frames
    versionPath = os.path.dirname(filePath)
    files = os.listdir(versionPath)
    files = sorted(files, key = lambda x: x.split('_')[-1].split('.')[0])
    firstFrame = files[0].split('_')[-1].split('.')[0]
    lastFrame = files[-1].split('_')[-1].split('.')[0]

    #outputdir
    outputDir = os.path.dirname(os.path.dirname(filePath))

    #outputfilename
    outputFilename = os.path.basename(filePath)
    outputFilename = '_'.join(outputFilename.split('_')[0:-1]) + '.mov'

    #inputimages
    inputimages = os.path.join(versionPath, files[0])

    #outputfile
    outputfile = os.path.join(outputDir, outputFilename).replace('\\', '/')

    #audiofile
    pathList = os.path.dirname(filePath.replace('/', '\\')).split(os.sep)
    pathList[2] = 'episodes'
    pathList.insert(1, os.sep)
    path = os.path.join(*pathList)

    pathList.insert(-2, 'audio')
    pathList[-2] = '_'.join(outputFilename.split('_')[0:-1]) + '.wav'
    filePath = os.path.join(*pathList[0:-1])

    audiofile = None
    if os.path.exists(filePath):
        audiofile = filePath

    #get temp directory
    tempDir=tempfile.gettempdir()

    #generate plugin file
    jobData = 'Plugin=Quicktime\nPriority=50\nPool=medium\nChunkSize=100000\n'
    jobData += 'Comment=Ftrack submit\n'
    jobData += 'Name=%s\n' % outputFilename.replace('.mov', '')
    jobData += 'Frames=%s-%s\n' % (int(firstFrame), int(lastFrame))
    jobData += 'OutputFilename0=%s\n' % outputfile

    jobFile=open((tempDir+'/job_info.job'),'w')
    jobFile.write(jobData)
    jobFile.close()
    jobFile=(tempDir+'/job_info.job')
    jobFile=jobFile.replace('\\','/')

    #generate submit file
    pluginData = 'FrameRate=25.0\nCodec=QuickTime Movie\n'
    pluginData += 'InputImages=%s\n' % inputimages.replace('\\', '/')
    pluginData += 'OutputFile=%s\n' % outputfile
    if audiofile:
        pluginData += 'AudioFile=%s\n' % audiofile.replace('\\', '/')

    pluginFile=open((tempDir+'/plugin_info.job'),'w')
    pluginFile.write(pluginData)
    pluginFile.close()
    pluginFile=(tempDir+'/plugin_info.job')
    pluginFile=pluginFile.replace('\\','/')

    #submitting to Deadline
    deadlineCommand = 'C:/Program Files/Thinkbox/Deadline6/bin/deadlinecommand.exe'

    if not os.path.exists(path):
        deadlineCommand = 'C:/Program Files/Thinkbox/Deadline7/bin/deadlinecommand.exe'

    result =  subprocess.Popen((deadlineCommand,jobFile,pluginFile,settingsPath),
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT,shell=False)

    #create movie if none exists, or delete old and create new
    try:
        version.createComponent(name='movie', path=outputfile)
    except:
        movComponent = version.getComponent(name='movie')
        movComponent.delete()
        version.createComponent(name='movie', path=outputfile)

def getThumbnailRecursive(task):
    if task.get('thumbid'):
        thumbid = task.get('thumbid')
        return ftrack.Attachment(id=thumbid)
    if not task.get('thumbid'):
        parent = ftrack.Task(id=task.get('parent_id'))
        return getThumbnailRecursive(parent)

def getTasksRecursive(entity):
    result = []

    if entity.get('objecttypename') == 'Task':
        result.append(entity)

    if entity.get('objecttypename') == 'Shot':
        for task in entity.getTasks():

            result.append(task)

    if entity.get('objecttypename') == 'Sequence':
        for shot in entity.getShots():
            result.extend(getTasksRecursive(shot))

    if entity.get('objecttypename') == 'Episode':
        for seq in entity.getSequences():
            result.extend(getTasksRecursive(seq))

    return result

def getGlobExpression(filename):

    _kVersionRegex = "([/._]v)(\\d+)"
    _kPaddedSequenceRegex = "%((\\d)*)(d)"

    # Replace version indices
    matches = [match for match in re.finditer(_kVersionRegex, filename, re.IGNORECASE)]
    if len(matches) > 0:

        # Obtain version index from the last version string, ignore the others
        match = matches[-1]

        # Replace sequence padding.
        matches = [match for match in re.finditer(_kPaddedSequenceRegex, filename, re.IGNORECASE)]
        if len(matches) > 0:
          # Iterate through matches, if the version string equals versionIndex ("active one"), substitute
          # NB: Reverse iteration guarantees safety of modifying filename by splitting at given positions (match.start() / end())
          for match in matches:
            pre = filename[:match.start() - 1] # -1 is to remove possibly leading '.' or similar before sequence padding
            post = filename[match.end():]
            filename = pre + "*" + post

        return filename
