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
- Sidewalk coding is used to understand what the sidewalk values represent. 
- In the absent["code"] field, you specify all values that represent that there is no sidewalk. A value of zero means anything less than or equal to zero.
- In the offset["type"] field, you specify what offset coresponds to each sidewalk code. The optional values are "feet", "meter", and "category". "feet" and "meter" values are interpreted to be the offset distance in that unit. "category" values are translated using the way type. The way type code is translated to one of five waytypes using the categorymap of the way type column and then each waytype is translated to an offset distance using "category_offset".

	- Example:
	"swk_coding": {
		"absent": {
			"code": [0, 2]
		},
		"offset": {
			"type": "category",
			"category_offset": {
	            "freeway": 0,
	            "primary_arterial": 20,
	            "minor_arterial": 11,
	            "colector_arterial": 8,
	            "local": 6.25
          	}
		}
	}
##### Metadata
1) primary key
- colum name
- null value
2) sidewalk left value 
- column name
3) sidewalk right value
- column name
4) way type (if category used as offset type)
- column name
- category map (translate each category key to associated type)

#### Curbramps (Optional)
##### Path
- Example: "path": "./source_data/seattle/curbramps.shp"

### Bondary Specification
- Give details of the boundary of the data you want staged
#### Path
- Example: "path": "./source_data/seattle/neighborhoods.shp"
#### Selection
- Specify if you want a slection of your data staged (True) or all of it (False).
- Example "selection": "True"
#### Attribute Selector Colum Name
- Example "attribute_selector": "name",
#### Attribute Selector value
- Example "attribute_selector_value": "University District",
#### Buffer Distance Meters
- If you are trying to create a boundary a cetain distance around a point, then the selected feature about must be a point, and here you select how large of a buffer. If your above selection is a polygon then set this value to zero.
- Example "buffer_distance_meters": 850

