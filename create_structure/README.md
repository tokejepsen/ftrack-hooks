# Create Structure

This action will add the ability to use generate a structure on disk.

## Usage

Select the entities to create structures from and run the action.

## Setup

Add ```ftrack-hooks\create_structure``` to ```FTRACK_CONNECT_PLUGIN_PATH```.
Add ```ftrack-hooks``` to ```PYTHONPATH```.

By default no structure will be created. To get the action to scan for directories and files to make, you'll need to setup an application launch plugin. The launch plugin needs to append directories and files to the event in the following way:

```python
event["data"]["directories"].append("path/to/some/directory")
event["data"]["files"].append(
  ("path/to/the/source/file", "path/to/the/destination/file")
)
```

Further the event contains the requested entities; ```event["data"]["entitites"]```

The following example prints the requested entities, creates a directory and two files in the temporary folder of the OS, for each entity.

```python
import os
import tempfile

import ftrack_api


def modify_launch(event):
    """Return each entities in the selection in data dictionaries."""

    print event["data"]["entities"]

    for entity in event["data"].get("entities", []):

        # Make a temporary directory
        directory = tempfile.mkdtemp()
        event["data"]["directories"].append(directory)
        os.rmdir(directory)

        # Make a temporary files
        temp = tempfile.NamedTemporaryFile()
        temp.close()
        with open(temp.name, 'w') as f:
            f.write("")
        event["data"]["files"].append((temp.name, temp.name + "_copy"))

    return event


def register(session, **kw):
    '''Register event listener.'''

    # Validate that session is an instance of ftrack_api.Session. If not,
    # assume that register is being called from an incompatible API
    # and return without doing anything.
    if not isinstance(session, ftrack_api.Session):
        # Exit to avoid registering this plugin again.
        return

    # Register the event handler
    session.event_hub.subscribe('topic=create_structure.launch', modify_launch)
```
