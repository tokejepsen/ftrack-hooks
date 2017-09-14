# Dynamic Environment

This plugin let's you dynamically load environments when launching apps from Ftrack.

It is production tested, however keep in mind that it's mechanisms are fairly simplistic. If you need a full featured robust system for environment management, you might want to look at:

 - [Ecosystem](https://github.com/PeregrineLabs/Ecosystem)
 - [rez](https://github.com/nerdvegas/rez)

Requirements
--------------

1. .json config file for each tool you have available (follow instructions below to see how)
2. Environment variable `FTRACK_APP_ENVIRONMENTS` pointing to a location where all your .json config files are stored
3. Hierarchical attribute called *'environment'* (type 'Text') in ftrack
4. This ftrack plugin in your `FTRACK_CONNECT_PLUGIN_PATH` location

Usage
---------

**Ftrack Attribute**

Ftrack Custom Attributes with following settings needs to be created

```
Name:     'environment'
Label:    'environment' (or whatever you choose)
Type:     Text
Added to: Hierarchical
```

It then needs to be filled with a list of tools that the entity and all it's children can use, separated with a comma ```,```. Keep in mind that these are additional tools on top of whatever app you chose to run from ftrack actions.

What you put in the attribute is purely up to you, but each item must correspond to a .json config file on disk. Most often these would be plugins you need to be loaded in maya, or nuke, but can be a custom set of environment variables as well. By default this plugin will generate a file name from each item in the Ftrack ```environment``` attribute, including the platform and application identifier which looks like this:

```
{platform}_{application identifier}_{item}
```

Key | Description | Examples
--- | --- | ---
platform | Name of the operating system. | ```windows```, ```unix```
application identifier | The identifier of the Ftrack action being launched. | ```maya_2016```, ```maya_2017```, ```nuke_10.0v1```, ```nuke_10.5v3```
item | The item in the ```environment``` attribute | ```mtoa_2.0.1```, ```yeti_2.1.0```, ```golaem_6.1```, ```my_custom_environment```

The full file name will be split by ```_``` and step will become a json file which the plugin will search for. For example when you launch Maya 2017 on Windows from a task with the environment of ```mtoa_2.0.1,yeti_2.1.0``` (**NOTE: there are no space between the comma**), the plugin will search for these file names on each path of the ```FTRACK_APP_ENVIRONMENTS``` environment variables:

```
windows.json
windows_maya.json
windows_maya_2017.json
windows_maya_2017_mtoa.json
windows_maya_2017_mtoa_2.0.1.json
windows_maya_2017_yeti.json
windows_maya_2017_yeti_2.1.0
```

Each json file allows you to have granular control over the environment. Any files not found will get ignored.


**Environment Files**

Each version of a tool (plugin, software, whatever) needs it's own config file, which is just a simple json formatted dictionary holding all the environment variables needed to run the tool.

Note that you can use environment variable in these config file. Anything wrapped in curly brackets `{}` will be resolved as environment variable when app is launched.

Examples of config files for Maya:

**windows_maya.json**
```json
{
    "MAYA_PLUG_IN_PATH": [
        "{STUDIO_TOOLS}\\maya\\plugins"
    ],
    "MAYA_AUTOSAVE_FOLDER": [
        "C:\\mayatemp\\autosave"
    ],
    "MAYA_SCRIPT_PATH": [
        "{STUDIO_TOOLS}\\maya\\scripts",
        "{STUDIO_REPOS}\\maya\\shelves"
    ]
}
```
**windows_maya_2017.json**
```json
{
    "MAYA_PLUG_IN_PATH": [
        "{STUDIO_REPOS}\\maya\\2017\\plugins"
    ],
    "MAYA_MODULE_PATH": [
        "{STUDIO_REPOS}\\maya\\2017\\modules"
    ],
}
```
**windows_maya_2017_mtoa_2.0.1**
```json
{
    "MAYA_MODULE_PATH": [
        "{STUDIO_SOFT}\\arnold\\mtoa_2017_2.0.1.1"
    ],
    "MAYA_RENDER_DESC_PATH": [
        "{STUDIO_SOFT}\\arnold\\mtoa_2017_2.0.1.1"
    ],
    "solidangle_LICENSE": [
        "port@SERVER"
    ]
}
```

Inheritance
-----------

All the json files this plugins picks up get merged together to form the final environment for the given task and app.

Plugin determines what environment to use by traversing up the hierarchy from the task (or any other entity) and uses the first environment attribute that has anything inputted. That allows overrides on any level that will affect all the children of the given entity, unless the child has it's own override

Example:

- Project01: *manual* - `mtoa_2.0.1,yeti_2.1.0`
    - SQ01: *inherits from Project01*
        - SH010: *inherits from SQ01*
            - Task01: *inherits from SH010*
            - Task02: *override* -  `mtoa_2.0.1,yeti_2.1.0,golaem_5`
        - SH020: *override* -  `mtoa_1.4.2`
            - Task03: *inherits from SH020*
            - Task04: *inherits from SH020*
    - SQ02: *override* -  `mtoa_2.0.1,yeti_2.1.0,golaem_6.1`
        - SH030: *inherits from SQ020*
            - Task05: *override* -  `mtoa_2.0.1,yeti_2.1.0`
            - Task06: *inherits from SH030*

Following environments will be set up when launching tasks:

Task | environment
--- | ---
Task01 | `mtoa_2.0.1,yeti_2.1.0`
Task01 | `mtoa_2.0.1,yeti_2.1.0`
Task02 | `mtoa_2.0.1,yeti_2.1.0,golaem_5_2017`
Task03 | `mtoa_1.4.2`
Task04 | `mtoa_1.4.2`
Task05 | `mtoa_2.0.1,yeti_2.1.0`
Task06 | `mtoa_2.0.1,yeti_2.1.0,golaem_6.1`


Limitations:
--------------

- Currently there is no way of excluding specified tools from being loaded, if they are in the environment attribute in ftrack. This means, that if a task has `mtoa_2.0.1` in it's environment attribute, it will try to load it even if we're launching Nuke 10.5v1. It will skip it, because the version resolve looks for `windows_nuke_10.5v1_mtoa_2.0.1.json` which won't exist on the disk so it gracefully ignores it, but it's something to keep in mind.
