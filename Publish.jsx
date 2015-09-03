var comp_names = [];
var comp_paths = [];
var args = '';
for( i = 1; i <= app.project.renderQueue.numItems; ++i )
{
    args += '--render';
    args += ' "' + app.project.renderQueue.item(i).comp.name + '"';
    args += ' "' + app.project.renderQueue.item(i).outputModule(1).file.fsName + '"';
    args += ' "' + (app.project.renderQueue.item(i).timeSpanStart) * (1 / app.project.renderQueue.item(i).comp.frameDuration) + '"';
    args += ' "' + (app.project.renderQueue.item(i).timeSpanDuration) * (1 / app.project.renderQueue.item(i).comp.frameDuration) + '"';
    args += ' ';
}

args += '--version "' + app.version + '" ';

app.project.save()
args += '--scene "' + app.project.file.fsName + '"';

$.setenv("PYBLISHARGUMENTS", args);

var batFile= new File("K:/production/tools/pyblish/pyblish.bat");

batFile.execute();
