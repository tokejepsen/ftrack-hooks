import logging
import os
import datetime
import shutil
import getpass

import ftrack

log = logging.getLogger(__name__)

def delivery(event):

    # replying to event
    ftrack.EVENT_HUB.publishReply(event,
        data={
            'success': True,
            'message': 'Delivery packaging started successfully!'
        }
    )

    # creating job
    user = ftrack.User(id=event['source']['user']['id'])
    job = ftrack.createJob('Delivery packaging', 'running', user)

    try:
        # getting ftrack data
        project = ftrack.Project(id=event['data']['selection'][0]['entityId'])

        review_cat = None
        final_cat = None
        for l in ftrack.getListCategories():
            if l.getName().lower() == 'review deliveries':
                review_cat = l
            if l.getName().lower() == 'final deliveries':
                final_cat = l


        try:
            review_list = project.getList(str(datetime.date.today()) + '_review')
        except:
            review_list = project.createList(str(datetime.date.today()) + '_review',
                                             review_cat, ftrack.AssetVersion)

        try:
            final_list = project.getList(str(datetime.date.today()) + '_final')
        except:
            final_list = project.createList(str(datetime.date.today()) + '_final',
                                            final_cat, ftrack.AssetVersion)


        # creating destination folders
        review_folder = os.path.join(project.getPath(), 'deliveries', 'review',
                                     str(datetime.date.today()))
        if not os.path.exists(review_folder):
            os.makedirs(review_folder)

        final_folder = os.path.join(project.getPath(), 'deliveries', 'final',
                                     str(datetime.date.today()))
        if not os.path.exists(final_folder):
            os.makedirs(final_folder)

        # getting all latest asset versions of type img and mov
        assetVersions = []
        for seq in project.getSequences():
            for shot in seq.getShots():
                for asset in shot.getAssets(assetTypes=['img', 'mov']):
                    v = GetLatestVersion(asset.getVersions(componentNames=['main']))
                    assetVersions.append(v)

        # review
        # collect review file paths
        file_paths = {}
        for v in assetVersions:
            checks = ['proposed final', 'wip']
            if v.getTask().getStatus().getName().lower() in checks:

                path = v.getComponent(name='main').getFilesystemPath()
                if v.getAsset().getType().getShort() == 'img':
                    file_paths[os.path.dirname(path)] = v
                else:
                    file_paths[path] = v

                review_list.append(v)

        # copy file paths
        for p in file_paths:
            try:
                shutil.copy(p, review_folder)
            except:
                path = os.path.join(review_folder, os.path.basename(p))
                if not os.path.exists(path):
                    os.makedirs(path)
                for f in os.listdir(p):
                    shutil.copy(os.path.join(p, f), os.path.join(path, f))

            # updating task status
            v = file_paths[p]
            if v.getTask().getStatus().getName().lower() == 'wip':
                v.getTask().setStatus(GetStatusByName('Sent WIP'))
            if v.getTask().getStatus().getName().lower() == 'proposed final':
                v.getTask().setStatus(GetStatusByName('Sent Proposed Final'))

        # final
        # collect final file paths
        file_paths = {}
        for v in assetVersions:
            checks = ['final']
            if v.getTask().getStatus().getName().lower() in checks:

                path = v.getComponent(name='main').getFilesystemPath()
                if v.getAsset().getType().getShort() == 'img':
                    file_paths[os.path.dirname(path)] = v
                    final_list.append(v)

        # copy file paths
        for p in file_paths:
            try:
                shutil.copy(p, final_folder)
            except:
                path = os.path.join(final_folder, os.path.basename(p))
                if not os.path.exists(path):
                    os.makedirs(path)
                for f in os.listdir(p):
                    shutil.copy(os.path.join(p, f), os.path.join(path, f))

            # updating task status
            v = file_paths[p]
            v.getTask().setStatus(GetStatusByName('Sent Final'))

    except Exception as e:
        job.setStatus('failed')
        job.setDescription(str(e))
    else:
        job.setStatus('done')

def delivery_movies(event):

    # replying to event
    ftrack.EVENT_HUB.publishReply(event,
        data={
            'success': True,
            'message': 'Delivery packaging started successfully!'
        }
    )

    # creating job
    user = ftrack.User(id=event['source']['user']['id'])
    job = ftrack.createJob('Delivery packaging', 'running', user)

    try:
        # getting ftrack data
        project = ftrack.Project(id=event['data']['selection'][0]['entityId'])

        review_cat = None
        for l in ftrack.getListCategories():
            if l.getName().lower() == 'review deliveries':
                review_cat = l

        try:
            review_list = project.getList(str(datetime.date.today()) + '_review')
        except:
            review_list = project.createList(str(datetime.date.today()) + '_review',
                                             review_cat, ftrack.AssetVersion)

        # creating destination folders
        review_folder = os.path.join(project.getPath(), 'deliveries', 'review',
                                     str(datetime.date.today()))
        if not os.path.exists(review_folder):
            os.makedirs(review_folder)

        # getting all latest asset versions of type img and mov
        assetVersions = []
        for seq in project.getSequences():
            for shot in seq.getShots():
                for asset in shot.getAssets(assetTypes=['mov']):
                    v = GetLatestVersion(asset.getVersions(componentNames=['main']))
                    assetVersions.append(v)

        # review
        # collect review file paths
        file_paths = {}
        for v in assetVersions:
            checks = ['proposed final', 'wip']
            if v.getTask().getStatus().getName().lower() in checks:

                path = v.getComponent(name='main').getFilesystemPath()
                if v.getAsset().getType().getShort() == 'img':
                    file_paths[os.path.dirname(path)] = v
                else:
                    file_paths[path] = v

                review_list.append(v)

        # copy file paths
        for p in file_paths:
            try:
                shutil.copy(p, review_folder)
            except:
                path = os.path.join(review_folder, os.path.basename(p))
                if not os.path.exists(path):
                    os.makedirs(path)
                for f in os.listdir(p):
                    shutil.copy(os.path.join(p, f), os.path.join(path, f))

            # updating task status
            v = file_paths[p]
            if v.getTask().getStatus().getName().lower() == 'wip':
                v.getTask().setStatus(GetStatusByName('Sent WIP'))
            if v.getTask().getStatus().getName().lower() == 'proposed final':
                v.getTask().setStatus(GetStatusByName('Sent Proposed Final'))

    except Exception as e:
        job.setStatus('failed')
        job.setDescription(str(e))
    else:
        job.setStatus('done')

def discover(event):
    '''Return action based on *event*.'''
    data = event['data']

    # cancel discover if selection is greater than 1
    if len(data['selection']) > 1:
        log.info('selection is greater than 1')
        return


    # return if selection is a project
    if data['selection'][0]['entityType'] == 'show':
        return {
            'items': [{
                'label': 'Delivery',
                'actionIdentifier': 'delivery'
            },{
                'label': 'Delivery Movies',
                'actionIdentifier': 'delivery.movies'
            }]
        }


def register(registry, **kw):
    '''Register action.'''
    ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.action.discover and source.user.username={0}'.format(
            getpass.getuser()
        ),
        discover
    )

    ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.action.launch and source.user.username={0} '
        'and data.actionIdentifier={1}'.format(
            getpass.getuser(), 'delivery'),
        delivery
        )

    ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.action.launch and source.user.username={0} '
        'and data.actionIdentifier={1}'.format(
            getpass.getuser(), 'delivery.movies'),
        delivery_movies
        )


def GetLatestVersion(versions):
    version_number = 0
    latest_version = None
    for v in versions:
        if v.getVersion() > version_number:
            version_number = v.getVersion()
            latest_version = v

    return latest_version


def GetStatusByName(name):
    statuses = ftrack.getTaskStatuses()

    result = None
    for s in statuses:
        if s.get('name').lower() == name.lower():
            result = s

    return result
