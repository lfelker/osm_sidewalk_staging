# About
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
- 

## sources.json specification
### City Name
- Example: "city": "Seattle"

### Import Name
- The name of the folder where the resulting osm.xml are found
- Example: "import_name": "University District"

### Layer Information
#### Streets
##### Path
- Example: "path": "./source_data/seattle/streets.shp"
##### Source
- Description of where the data is from
- Example: "source": "King County GIS Data Portal Streets Network"
##### Sidewalk Coding Information

##### Metadata

#### Curbramps
##### Path
- Example: "path": "./source_data/seattle/curbramps.shp"

### Bondary Specification

