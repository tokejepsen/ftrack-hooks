# Process Review

This action will add the ability to process an online review locally and upload.

## Usage

- Launch ```Process Review``` on an assetversion or with multiple assetversions selected.
- Choose which process preset to use.

## Setup

Add ```ftrack-hooks\process_review``` to ```FTRACK_CONNECT_PLUGIN_PATH```.
Add ```ftrack-hooks``` to ```PYTHONPATH```.

This plugin processes a review with presets. A preset is a python script that accepts two arguments; source movie path and destination movie path.

There is an optional third argument passed to the python script; thumbnail path.

The plugin searches for presets on the ```REVIEW_PRESETS``` environment variable.
