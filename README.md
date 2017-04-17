# osm_sidewalk_staging
tool to prepare sidewalk data for OSM staging with Open Sidewalks schema

# Basic Workflow
## input required:
- streets center line data set with sidewalk left and right data
- sources.json file in source_json_examples folder edited to have appropriate parameter information

## input optional:
- curbramps location
- bondary of data to stage like a nighborhood to stage

## output:
- osm.xml files split into tasks (default is by block) to be uploaded to Open Sidewalks tasking manager

