This plugin let's you dynamicaly load environments when launching apps from ftrack. 

It is production tested, however keep in mind that it's mechanisms are fairly simplistic. If you need a full featured robust system for environment management, you might want to look at something like ecosystem or rez

Requirements:
--------------

1. .json config file for each tool you have available (follow instructions below to see how)
2. Environment variable `FTRACK_APP_ENVIRONMENTS` pointing to a location where all your .json config files are stored
3. Hierarchical attribute called *'environment'* (type 'string') in ftrack
4. this ftrack plugin in your `FTRACK_CONNECT_PLUGIN_PATH` location

Usage:
---------

**Ftrack attribute:**

Ftrack Custom Attributes with following settings needs to be created

```
Name:     'environment'
Label:    'environment' (or whatever you choose)
Type:     Text
Added to: Hierarchical
```

It then needs to be filled with a list of tools that the entity and all it's children can use, separated with a comma `,`. Keep in mind that these are additional tools on top of whatever app you chose to run from ftrack actions.

What you put in the attribute is purely up to you, but each item must correspond to a .json config file on disk. Most often these would be plugins you need to be loaded in maya, or nuke, but can be a custom set of environment variables as well. Additionaly this plugin automatically adds the app version (maya, nuke ...) at the end of the plugin name. This is to allow picking the correct version of the plugin in case of multiple versions of host app being available on the system. For example mtoa_1.4.2 exists for maya 2017 and 2018. The mechanism should probably be made a bit more flexible eventualy. 

when you launch maya 2017 from task with environment: `mtoa_2.0.1, yeti_2.1.0, golaem_6.1` the resulting config files loaded will be `mtoa_2.0.1_2017.json, yeti_2.1.0_2017.json, golaem_6.1_2017.json`


**Environment files:**

Each versin of a tool (plugin, software, whatever) needs it's own config file, which is just a simple .json formatted dictionary holding all the environment variables needed to run the tool. 

Note that you can use environment variable in these config file. Anything wrapped in curly brackets `{}` will be resolved as environment variable when app is launched. 

Example of config files for maya.

**maya.json**
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
**maya_2017.json**
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
**mtoa_2.0.1_2017**
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

Mechanism and inheritance:
----------- 

All the .json files this plugins picks up get merged together to form the final environment for the given task and app. You can also separate out version specific environmnents from global ones. For example when you launch Maya 2017 from ftrack task, the plugin will first look for `maya.json` config, then `maya_2017.json`, then it will add all the additional config files specified in the ftrack *'environment'* attribute.

Plugin determines what environment to use by traversing up the hierarchy from the task (or any other entity) and uses the first environment that has an override. That allows overrides on any level that will affect all the children of the given entity, unless the child has it's own override

Example:

- Project01: *manual* - `mtoa_2.0.1, yeti_2.1.0`
    - SQ01: *inherits from Project01*
        - SH010: *inherits from SQ01*
            - Task01: *inherits from SH010*
            - Task02: *override* -  `mtoa_2.0.1, yeti_2.1.0, golaem_5`
        - SH020: *override* -  `mtoa_1.4.2`
            - Task03: *inherits from SH020*
            - Task04: *inherits from SH020*
    - SQ02: *override* -  `mtoa_2.0.1, yeti_2.1.0, golaem_6.1`
        - SH030: *inherits from SQ020*
            - Task05: *override* -  `mtoa_2.0.1, yeti_2.1.0`
            - Task06: *inherits from SH030*

Following environments will be set up when launching tasks:

| Application  | Task           | environmnet |
| :---         |     :---      |          :--- |
|Maya 2017 | Task01 | `mtoa_2.0.1_2017.json, yeti_2.1.0_2017.json`|
|Maya 2018 | Task01 | `mtoa_2.0.1_2018.json, yeti_2.1.0_2018.json`|
|Maya 2017 | Task02 | `mtoa_2.0.1_2017.json, yeti_2.1.0_2017.json, golaem_5_2017.json`|
|Maya 2017 | Task03 | `mtoa_1.4.2_2017.json`|
|Maya 2017 | Task04 | `mtoa_1.4.2_2017.json`|
|Maya 2017 | Task05 | `mtoa_2.0.1_2017.json, yeti_2.1.0_2017.json`|
|Maya 2017 | Task06 | `mtoa_2.0.1_2017.json, yeti_2.1.0_2017.json, golaem_6.1_2017.json`|


Limitations:
--------------

- Currently there is now way of excluding specified tools from being loaded, if they are in the environment attribute in ftrack. This means, that if a task has `mtoa_2.0.1` in it's enviro attr, it will try to load it even if we're launching Nuke 10.5. It will naturaly skip it, because of the version resolving it'll actually look for `mtoa_2.0.1_10.5.json` which won't exist on the disk so it gracefully ignores it, but it's something to keep in mind.

- the way the system recognizes the app name and version is prone to errors in case the app identifier (in the ftrack action) contains more that one underscore `_`. This is currently a problem only with the default installation of ftrack connect, which uses`nuke_studio_{version]` applicationIdentifier for nuke studio. An easy remedy is to change the applicationIdentifier in the ftrack connect files to `nukestudio_{version}` 

