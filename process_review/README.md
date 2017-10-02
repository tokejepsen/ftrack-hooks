# Process Review

This action will add the ability to process an online review locally and upload.

## Usage

- Launch ```Process Review``` on an assetversion or with multiple assetversions selected.
- Choose which process preset to use.

## Setup

This plugin processes a review with presets. A preset is a python script that accepts two arguments; source movie path and destination movie path.

The plugin searches for presets on the ```REVIEW_PRESETS``` environment variable.
