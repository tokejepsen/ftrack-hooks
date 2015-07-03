import logging
import os
import datetime
import shutil
import getpass
import traceback
import tempfile


import sys
sys.path.append(r'K:\tools\FTrack\ftrack-api')
import ftrack

temp_dir = tempfile.gettempdir()
path = os.path.join(temp_dir, 'delivery_action.log')
if os.path.exists(path):
    os.remove(path)

logging.basicConfig(level=logging.INFO, filename=path)

# set up logging to console
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
# set a format which is simpler for console use
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
console.setFormatter(formatter)
# add the handler to the root logger
logging.getLogger('').addHandler(console)
log = logging.getLogger(__name__)


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

def undeliver_images(event):

    # replying to event
    ftrack.EVENT_HUB.publishReply(event,
        data={
            'success': True,
            'message': 'Undeliver versions started successfully!'
        }
    )

    # creating job
    user = ftrack.User(id=event['source']['user']['id'])
    job = ftrack.createJob('Undeliver packaging', 'running', user)

    try:
        for item in event['data']['selection']:

            # getting data
            version = ftrack.AssetVersion(id=item['entityId'])
            log.info(version.getTask().getParent().getName())

            delivery_component = version.getComponent(name='delivery')
            delivery_path = delivery_component.getFilesystemPath()
            delivery_dir = os.path.dirname(delivery_path)

            main_component = version.getComponent(name='main')
            main_path = main_component.getFilesystemPath()
            main_dir = os.path.dirname(main_path)

            # ensuring destination path exists
            if not os.path.exists(main_dir):
                os.makedirs(main_dir)

            # moving files
            for f in os.listdir(delivery_dir):
                shutil.move(os.path.join(delivery_dir, f),
                            os.path.join(main_dir, f))

            # removing delivery folder
            os.rmdir(delivery_dir)

            # delete delivery component
            delivery_component.delete()

            # removing version from list
            ls = None
            project = version.getParents()[-1]

            for l in project.getLists():
                for obj in l.getObjects():
                    if obj.getId() == version.getId():
                        ls = l

            ls.remove(version)

            # revert status to "Final"
            task = version.getTask()
            task.setStatus(GetStatusByName('Final'))

            log.info('Undelivered %s' % version)

    except:
        job.setStatus('failed')

        log.error(traceback.format_exc())
    else:
        job.setStatus('done')

def delivery_images(event):

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
            if l.getName().lower() == 'final deliveries':
                final_cat = l

        try:
            final_list = project.getList(str(datetime.date.today()) + '_final')
        except:
            final_list = project.createList(str(datetime.date.today()) + '_final',
                                            final_cat, ftrack.AssetVersion)


        # creating destination folders
        final_folder = os.path.join(project.getPath(), 'deliveries', 'final',
                                     str(datetime.date.today()))
        if not os.path.exists(final_folder):
            os.makedirs(final_folder)

        # getting all latest asset versions of type img and mov
        assetVersions = []
        checks = ['final']
        for seq in project.getSequences():
            for shot in seq.getShots():
                if shot.getStatus().getName().lower() in checks:
                    for task in shot.getTasks():
                        if task.getStatus().getName().lower() in checks:

                            log.info(task.getParent().getName())

                            assets = task.getAssets(assetTypes=['img'])

                            # clean up assets
                            if len(assets) > 1:
                                for asset in task.getAssets(assetTypes=['img']):
                                    if asset.getName() == 'None':
                                        asset.delete()

                            # get latest version
                            asset = task.getAssets(assetTypes=['img'])[0]
                            versions = asset.getVersions(componentNames=['main'])
                            v = GetLatestVersion(versions)
                            if v:

                                # copying files
                                component = v.getComponent(name='main')
                                path = component.getFilesystemPath()
                                folder = os.path.dirname(path)
                                destination = os.path.join(final_folder,
                                                            os.path.basename(folder))

                                log.info('%s >> %s' % (folder, destination))
                                try:

                                    # moving files
                                    if not os.path.exists(destination):
                                        os.makedirs(destination)
                                    for f in os.listdir(folder):
                                        shutil.move(os.path.join(folder, f),
                                                    os.path.join(destination, f))

                                    file_name = os.path.basename(path)
                                    delivery = os.path.join(destination,
                                                            file_name)
                                    v.createComponent(name='delivery',
                                                      path=delivery)
                                    v.publish()

                                    final_list.append(v)

                                    task.setStatus(GetStatusByName('Sent Final'))
                                except:
                                    log.error(traceback.format_exc())

    except:
        job.setStatus('failed')

        log.error(traceback.format_exc())
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

        # getting all latest asset versions of type mov
        assetVersions = []
        for seq in project.getSequences():
            for shot in seq.getShots():
                for asset in shot.getAssets(assetTypes=['mov']):
                    versions = asset.getVersions(componentNames=['main'])
                    v = GetLatestVersion(versions)
                    if v:
                        assetVersions.append(v)

        # review
        # collect review file paths
        file_paths = {}
        for v in assetVersions:
            checks = ['proposed final', 'wip']
            try:
                if v.getTask().getStatus().getName().lower() in checks:

                    path = v.getComponent(name='main').getFilesystemPath()
                    file_paths[path] = v

                    review_list.append(v)
            except Exception as e:
                log.info(e)
                log.info(traceback.format_exc())

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
        log.error(traceback.format_exc())
        job.setStatus('failed')
    else:
        job.setStatus('done')

def discover(event):
    '''Return action based on *event*.'''
    data = event['data']

    if data['selection'][0]['entityType'] == 'assetversion':
        return {
            'items': [{
                'label': 'Undeliver Images',
                'actionIdentifier': 'undeliver.images'
            }]
        }

    # return if selection is a project
    if data['selection'][0]['entityType'] == 'show':
        return {
            'items': [{
                'label': 'Delivery Images',
                'actionIdentifier': 'delivery.images'
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
            getpass.getuser(), 'delivery.images'),
        delivery_images
        )

    ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.action.launch and source.user.username={0} '
        'and data.actionIdentifier={1}'.format(
            getpass.getuser(), 'undeliver.images'),
        undeliver_images
        )

    ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.action.launch and source.user.username={0} '
        'and data.actionIdentifier={1}'.format(
            getpass.getuser(), 'delivery.movies'),
        delivery_movies
        )
"""
def register():
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
            getpass.getuser(), 'delivery.images'),
        delivery_images
        )

    ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.action.launch and source.user.username={0} '
        'and data.actionIdentifier={1}'.format(
            getpass.getuser(), 'undeliver.images'),
        undeliver_images
        )

    ftrack.EVENT_HUB.subscribe(
        'topic=ftrack.action.launch and source.user.username={0} '
        'and data.actionIdentifier={1}'.format(
            getpass.getuser(), 'delivery.movies'),
        delivery_movies
        )

ftrack.setup()
register()
ftrack.EVENT_HUB.wait()
"""
