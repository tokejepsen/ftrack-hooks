import os
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
