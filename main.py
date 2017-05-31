import json
import os
import click
import geopandas as gpd
from geopandas import GeoSeries
import shapely

# for visualizations
import matplotlib.pyplot as plt
import matplotlib
import fiona

import staging_manager
import data_manager
import sidewalkify
import crossify
from staging_manager import buffer_logic, bound, stage
from data_manager import standardize

VISUALIZE_LIMIT = 4000 # number of segments in data
FINAL_CRS = {'init': 'epsg:4326'}

def main():
	click.echo("Loading Data")
	json_sources = open("sources.json").read()
	sources = json.loads(json_sources)

	streets_path = sources['layers']['streets']['path']
	streets =  gpd.read_file(streets_path)
	streets_crs = streets.crs

	# when calculaing buffers and doing intersections. crs should be in utm.
	# for clip operation we want more than what the final buffer will be so we use multipler
	boundary_clip = bound.get_boundary(sources, streets_crs, streets_crs, buff_multiplier=1.25)
	boundary_real = bound.get_boundary(sources, streets_crs, streets_crs)

	if boundary_clip != None:
		click.echo("Clipping Streets To Boundary")
		streets = bound.bound(streets, boundary_clip)
		if len(streets) == 0:
			raise ValueError("no streets found within specified boundary")

	click.echo("Visualizing Stagging Area")
	#visualize(streets, boundary_real, "Streets in Staging Area")

	click.echo("Standardizing Schema")
	streets = prepare_sidewalk_offset(streets, sources)
	st_meta = sources['layers']['streets']['metadata']
	streets = standardize.standardize_df(streets, st_meta)
	if "waytype" in streets:
		streets = streets.loc[streets.waytype != "freeway"]

	click.echo("Creating Graph Of Streets")
	G = sidewalkify.graph.create_graph(streets)

	click.echo("Finding Paths in Graph")
	paths = sidewalkify.graph.process_acyclic(G)
	paths += sidewalkify.graph.process_cyclic(G)

	click.echo("Generating Sidewalks")
	sidewalks = sidewalkify.draw.draw_sidewalks(paths, streets_crs, resolution=1)
	if sidewalks.empty:
	    raise Exception('Generated No Sidewalks')
	sidewalks.to_file('./output/cleaned/sidewalks.shp')
	click.echo("Generated Sidewalks Outputed To: ./output/cleaned/sidewalks.shp")

	click.echo('Generating Crossings...')
	streets_clipped = bound.bound(streets, boundary_real)
	crossings_results = crossify.cross.make_graph(sidewalks, streets_clipped)
	full_crossings = crossings_results['crossings']

	click.echo('Joining Crossings To Sidewalks')
	sidewalks = crossify.cross.add_endpoints_to_sidewalks(sidewalks, full_crossings)
	if full_crossings.empty:
	    raise Exception('Generated No Crossings')

	click.echo('Offsetting Crossing From Corner')
	offset_results = crossify.cross.generate_crossing_offset(sidewalks, full_crossings)
	full_crossings = offset_results['crossings']
	sidewalks = offset_results['sidewalks']

	click.echo('Creating Links')
	split_crossings = crossify.cross.split_crossings(full_crossings)
	crossings = split_crossings['crossings']
	links = split_crossings['links']
	raised_curbs = split_crossings['raised_curbs']

	corner_crossing_nodes = split_crossings['corner_crossing_nodes']
	corner_crossing_nodes = gpd.GeoDataFrame(geometry=corner_crossing_nodes)
	click.echo('Generating Corner Curb Ramps')
	corner_ramps_results = crossify.cross.generate_corner_ramps(sidewalks, corner_crossing_nodes)

	click.echo('Preparing Crossing Geo Data Frames')
	crossings.extend(corner_ramps_results['crossings'])
	links.extend(corner_ramps_results['links'])
	lowered_curbs = corner_ramps_results['lowered_curbs']

	crossings = gpd.GeoDataFrame(geometry=crossings)
	links = gpd.GeoDataFrame(geometry=links)
	raised_curbs = gpd.GeoDataFrame(geometry=raised_curbs)
	lowered_curbs = gpd.GeoDataFrame(geometry=lowered_curbs)

	crossings.crs =  sidewalks.crs
	links.crs = sidewalks.crs
	raised_curbs.crs = sidewalks.crs
	lowered_curbs.crs = sidewalks.crs

	click.echo("Visualizing Generated Sidewalks")
	import_name = sources['import_name']
	visualize(sidewalks, boundary_real, import_name + " Generated Sidewalks", [links, raised_curbs, crossings, streets, lowered_curbs])

	click.echo("Converting Projections To Web Mercator")
	sidewalks = sidewalks.to_crs(FINAL_CRS)
	streets = streets.to_crs(FINAL_CRS)
	boundary_stage = bound.get_boundary(sources, streets_crs, FINAL_CRS)

	click.echo("Starting Staging Process")
	blocks_layers = {
		'sidewalks': sidewalks
	}

	crossing_layers = {
		'crossings': crossings,
		'links': links,
		'raised_curbs': raised_curbs,
		'lowered_curbs': lowered_curbs
	}

	# It was decided not use any CITY curb ramp info
	# if 'curbramps' in sources['layers']:
	# 	click.echo("Loading curbramps")
	# 	curbramps = gpd.read_file(sources['layers']['curbramps']['path'])
	# 	crossing_layers['curbramps'] = curbramps

	tasks_options = sources['tasks'] 
	city = sources['city']
	if tasks_options['joined'] == "True":
		joined_layers = blocks_layers
		for layer_key in crossing_layers.keys():
			joined_layers[layer_key] = crossing_layers[layer_key]
		click.echo("All Layers Are Being Staged Together")
		stage.stage(streets, joined_layers, boundary_stage, city, import_name, streets_crs, tasks_options)
	else:
		click.echo("Blocks and Crossings Are Being Staged Seperately")
		block_tasks_options = {'type': tasks_options['blocks_type']}
		stage.stage(streets, blocks_layers, boundary_stage, city, import_name + "_blocks", streets_crs, block_tasks_options)
		crossings_tasks_options = {'type': tasks_options['crossings_type']}
		stage.stage(streets, crossing_layers, boundary_stage, city, import_name + "_crossings", streets_crs, crossings_tasks_options)

def visualize(data, stage_bound, vis_title, extra_data=[]):
	if check_visualization_limit(len(data)):
		bound.visualize(data, buff=stage_bound, title=vis_title, extras=extra_data)
	else:
		click.echo(vis_title + "Not Visualized Due To Size Of Data")

def check_visualization_limit(number_of_elements):
	return number_of_elements < VISUALIZE_LIMIT

# Example of associatedStreet json in metadata
#        "associatedStreet": {
#          "colname": "associatedStreet",
#          "build_from_colnames": ["PREFIX_L", "NAME_L", "TYPE_L", "SUFFIX_L"]
#        }
def build_associated_street(streets, sources):

	if "associatedStreet" in sources["layers"]["streets"]["metadata"]:
		columns = sources["layers"]["streets"]["metadata"]["associatedStreet"]["build_from_colnames"]

		def build_street(street):
			associated_street = ""
			for column in columns:
				element = street[column]
				if element == None:
					continue
				elif len(associated_street) == 0 and len(element) > 0:
					associated_street = element
				elif len(associated_street) > 0 and len(element) > 0:
					associated_street += " " + element
			street["associatedStreet"] = associated_street
			return street

		streets = streets.apply(build_street, axis=1)
	return streets

def sum_sidewalks(gdf, sum_row_name):
	sidewalk_sum = 0.0
	for index, row in gdf.iterrows():
		geo = row[sum_row_name]
		road_length = geo.length
		sidewalk_sum += road_length
	return sidewalk_sum

# convert offset values to follow <= 0 absent and >0 = offset distance
# also conditionally convert waytype to offset value if offset distance unknown
def prepare_sidewalk_offset(streets, sources):
	st_meta = sources['layers']['streets']['metadata']
	swk_meta = sources['layers']['streets']['swk_coding']
	offset_type = swk_meta['offset']['type']

	def calculate_offset(street):
		swk_left_colname = st_meta['sw_left']['colname']
		swk_right_colname = st_meta['sw_right']['colname']
		left_offset = street[swk_left_colname]
		right_offset = street[swk_right_colname]
		street[swk_left_colname] = translate_offset(left_offset, street)
		street[swk_right_colname] = translate_offset(right_offset, street)
		return street

	def translate_offset(offset, street):
		swk_absent_values = swk_meta['absent']['code']
		if offset in swk_absent_values or offset < 0:
			return 0
		else:
			# return 1
			if offset_type == "category":
				waytype_colname = st_meta['waytype']['colname']
				way_code = street[waytype_colname]
				way_type = st_meta['waytype']['categorymap'][way_code]
				offset_value = swk_meta['offset']['category_offset'][way_type]
				return offset_value
			else:
				return offset

	streets_crs = streets.crs
	streets_correct_offset = streets.apply(calculate_offset, axis=1)
	streets_correct_offset.crs = streets_crs
	return streets_correct_offset

if __name__ == "__main__":
	main()