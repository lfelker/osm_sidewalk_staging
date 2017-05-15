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
from staging_manager import buffer_logic, bound, stage

import data_manager
from data_manager import standardize

# import sidewalkify
import sidewalkify

VISUALIZE_LIMIT = 1500

def main():
	web_merc_crs = {'init': 'epsg:4326'}
	redraw_sidewalks = True # allows skipping of redraw during development

	click.echo("Loading Data")
	json_sources = open("source_json_examples/sources_ufl.json").read()
	sources = json.loads(json_sources)
	import_name = sources['import_name']
	city = sources['city']

	streets_path = sources['layers']['streets']['path']
	streets =  gpd.read_file(streets_path)
	streets_crs = streets.crs
	# TODO: ensure UTM is correct

	# TODO: click.echo("clean data")

	# when calculaing buffers and doing intersections crs should be in utm.
	# for clip operation we want more than what the final buffer will be so we use multipler
	boundary_clip   = bound.get_boundary(sources, streets_crs, streets_crs, buff_multiplier=1.25)
	boundary_real = bound.get_boundary(sources, streets_crs, streets_crs)
	sidewalks = None

	# visualization takes too long if there is a lot of data
	visualize = check_visualization_limit(len(streets))

	if redraw_sidewalks:
		if boundary_clip != None:
			click.echo("Clipping Streets To Boundary")
			streets = bound.bound(streets, boundary_clip)
			if len(streets) == 0:
				raise ValueError("no streets found within specified boundary")

			visualize = check_visualization_limit(len(streets))
			# if visualize:
			# 	bound.visualize(streets, buff=boundary_real, title="Streets in Boundary")

		click.echo("Standardizing Schema")
		# streets = build_associated_street(streets, sources)
		# Associated Street should be directly linked to OSM street value.
		# To do this we would need to have a one to one mapping between municipal street data and OSM data
		streets = prepare_sidewalk_offset(streets, sources)
		st_meta = sources['layers']['streets']['metadata']
		streets = standardize.standardize_df(streets, st_meta)

		for line in streets['geometry']:
			if len(line.coords) < 2:
				raise ValueError

		click.echo("Creating Graph Of Streets")
		G = sidewalkify.graph.create_graph(streets)

		click.echo("Finding Paths in Graph")
		paths = sidewalkify.graph.process_acyclic(G)
		paths += sidewalkify.graph.process_cyclic(G)

		click.echo("Generating Sidewalks")
		sidewalks = sidewalkify.draw.draw_sidewalks(paths, streets_crs, resolution=1)
		sidewalks.to_file('./output/cleaned/sidewalks.shp')
		click.echo("Generated Sidewalks Outputed To: ./output/cleaned/sidewalks.shp")
	else:
		sidewalks = gpd.read_file('./output/cleaned/sidewalks.shp')

	click.echo("Converting Projections To Web Mercator")
	sidewalks = sidewalks.to_crs(web_merc_crs)
	print(sum_sidewalks(sidewalks, 'geometry'))
	streets = streets.to_crs(web_merc_crs)
	boundary_stage = bound.get_boundary(sources, streets_crs, web_merc_crs)

	click.echo("Removing Freeways from streets Network")
	# TODO: paramaterize this
	if "waytype" in streets:
		streets = streets.loc[streets.waytype != "freeway"]

	click.echo("Visualizing Generated Sidewalks")
	# if visualize:
	# 	bound.visualize(sidewalks, buff=boundary_stage, title=import_name + " Generated Sidewalks")
	# else:
	# 	click.echo("Visualization Turned Off Due To Size Of Staging Data")

	#generateCrossings()

	#annotatecrossings()

	blocks_layers = {
		'sidewalks': sidewalks
	}

	crossing_layers = {
		#'crossings': crossings
	}

	if 'curbramps' in sources['layers']:
		click.echo("Loading curbramps")
		curbramps = gpd.read_file(sources['layers']['curbramps']['path'])
		crossing_layers['curbramps'] = curbramps


	click.echo("Starting Staging Process")
	tasks_options = sources['tasks'] 
	if tasks_options['joined'] == "True":
		joined_layers = blocks_layers
		for layer_key in crossing_layers.keys():
			joined_layers[layer_key] = crossing_layers[layer_key]
		click.echo("All layers staged together")
		stage.stage(streets, joined_layers, boundary_stage, city, import_name, visualize, streets_crs, tasks_options)
	else:
		click.echo("Blocks and Crossings staged seperately")
		block_tasks_options = {'type': tasks_options['blocks_type']}
		stage.stage(streets, blocks_layers, boundary_stage, city, import_name + "_blocks", visualize, streets_crs, block_tasks_options)
		crossings_tasks_options = {'type': tasks_options['crossings_type']}
		stage.stage(streets, crossing_layers, boundary_stage, city, import_name + "_crossings", visualize, streets_crs, crossings_tasks_options)



def check_visualization_limit(number_of_elements):
	return number_of_elements < VISUALIZE_LIMIT

# Example of associatedStreet json in metadata
#        "associatedStreet": {
#          "colname": "associatedStreet",
#          "build_from_colnames": ["PREFIX_L", "NAME_L", "TYPE_L", "SUFFIX_L"]
#        }
def build_associated_street(streets, sources):

	print("here")
	if "associatedStreet" in sources["layers"]["streets"]["metadata"]:
		print("now here")
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

	def claculate_offset(street):
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
	streets_correct_offset = streets.apply(claculate_offset, axis=1)
	streets_correct_offset.crs = streets_crs
	return streets_correct_offset

if __name__ == "__main__":
	main()