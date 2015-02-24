def handleCallbackActions(topic, buttonId, userId, selection):

    """Handles all Action Menu events"""

    if buttonId == 'consolidate-versions':
        #create a job to inform the user that something is going on
        job = ftrack.createJob(description="Consolidate versions", status="running", user=userId)

        try:
            for s in selection:
                print '***********************************************************'
                version = ftrack.AssetVersion(s['entityId'])

                asset = version.getAsset()
                print 'Consolidating versions for asset: ' + asset.getName()
                versions = asset.getVersions()

                for version in versions:  #Iterate through versions and remove unpublished ones
                    if version.get('ispublished'):
                        pass
                    else:
                        version.delete()
                versions = asset.getVersions()
                sorted_by_version = sorted(versions, key=lambda version: version.getVersion())

                for i, item in enumerate(sorted_by_version):  #iterate through remaining versions and renumber them sequentially
                    item.set('version', i+1)

            job.setStatus('done')

            print '***********************************************************'

        except:
            job.setStatus('failed')
            raise

    if buttonId == 'create-movie':
        #create a job to inform the user that something is going on
        job = ftrack.createJob(description="Creating Movies", status="running", user=userId)

        #might need some better feedback for the console, so to know what is getting updated
        try:
            print '***********************************************************'
            print 'Creating movie for shots:'
            for item in selection:

                ID = item['entityId']
                entity = ftrack.Task(id=ID)
                for shot in getShots(entity):
                    try:
                        asset = shot.getAssets(['img'], ['render'])[0]
                        version = getLatestVersion(asset.getVersions())
                        submitQT(version)
                        print '%s successfull.' % shot.getName()
                    except Exception,e:
                        print '%s failed:' % shot.getName()
                        print str(e)

            job.setStatus('done')  #inform the user that the action is done
        except:
            job.setStatus('failed')  #fail the job if something goes wrong
            raise

    if buttonId == 'keep-latest-version':
        #create a job to inform the user that something is going on
        job = ftrack.createJob(description="Keeping Latest Versions", status="running", user=userId)

        #might need some better feedback for the console, so to know what is getting updated
        try:
            print '***********************************************************'
            print 'Keeping latest version for shots:'
            for item in selection:
                ID = item['entityId']
                entity = ftrack.Task(id=ID)
                for shot in getShots(entity):
                    try:
                        for asset in shot.getAssets(ftrack.getAssetTypes()):
                            versions = asset.getVersions()
                            for version in versions:
                                if not version == getLatestVersion(versions):
                                    for component in version.getComponents():
                                        globEx = getGlobExpression(component.getFile())
                                        for f in glob.glob(globEx):
                                            if os.path.exists(f):
                                                os.remove(f)
                                                try:
                                                    os.rmdir(os.path.dirname(f))
                                                except:
                                                    pass

                                    version.delete()

                        print '%s successfull.' % shot.getName()
                    except Exception,e:
                        print '%s failed:' % shot.getName()
                        print str(e)

            job.setStatus('done')  #inform the user that the action is done
        except Exception,e:
            job.setStatus('failed')  #fail the job if something goes wrong
            job.setDescription(e)
            raise
