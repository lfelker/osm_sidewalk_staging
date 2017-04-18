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

import sidewalkify

VISUALIZE_LIMIT = 1500

def main():
	web_merc_crs = {'init': 'epsg:4326'}
	redraw_sidewalks = True # allows skipping of redraw during development

	click.echo("Starting Process")
	json_sources = open("source_json_examples/sources_no_boundary.json").read()
	sources = json.loads(json_sources)

	streets_path = sources['layers']['streets']['path']
	streets =  gpd.read_file(streets_path)
	streets_crs = streets.crs
	# TODO: ensure UTM is correct

	# TODO: click.echo("standardizing schema")
	# stadardize column names before being passed to graph
	# standardize_streets(sources)

	# TODO: click.echo("clean data")

	# when calculaing buffers and doing intersections crs should be in utm.
	# for clip operation we want more than what the final buffer will be so we use multipler
	boundary_clip   = bound.get_boundary(sources, streets_crs, streets_crs, buff_multiplier=1.25)
	boundary_real = bound.get_boundary(sources, streets_crs, streets_crs)
	sidewalks = None

	visualize = check_visualization_limit(len(streets))

	if redraw_sidewalks:
		if boundary_clip != None:
			click.echo("Clipping Streets To Boundary")
			streets = bound.bound(streets, boundary_clip)
			if len(streets) == 0:
				raise ValueError("no streets found within specified boundary")

			visualize = check_visualization_limit(len(streets))
			if visualize:
				bound.visualize(streets, buff=boundary_real, title="Streets in Boundary")
			# TODO: what if streets number is really large?

		click.echo("Creating Graph Of Streets")
		G = sidewalkify.graph.create_graph(streets)

		click.echo("Finding Paths in Graph")
		paths = sidewalkify.graph.process_acyclic(G)
		paths += sidewalkify.graph.process_cyclic(G)

		# TODO: strip out MultiLineString here??
		# input is only line strings - one to one mapping to street and sidewalks

		click.echo("Generating Sidewalks")
		sidewalks = sidewalkify.draw.draw_sidewalks(paths, streets_crs)
		sidewalks.to_file('./output/cleaned/sidewalks.shp')
		click.echo("Generated Sidewalks Outputed To: ./output/cleaned/sidewalks.shp")
	else:
		sidewalks = gpd.read_file('./output/cleaned/sidewalks.shp')

	click.echo("Converting Projections To Web Mercator")
	sidewalks = sidewalks.to_crs(web_merc_crs)
	streets = streets.to_crs(web_merc_crs)
	boundary_stage = bound.get_boundary(sources, streets_crs, web_merc_crs)

	click.echo("Visualizing Generated Sidewalks")
	if visualize:
		bound.visualize(sidewalks, buff=boundary_stage, title="Generated Sidewalks")
	else:
		click.echo("Visualization Turned Off Due To Size Of Staging Data")

	#generateCrossings()

	#annotate()

	#addcurbramps

	click.echo('Starting Staging Process')
	layers_gdf = {
		'sidewalks': sidewalks
	}

	#if extra_layers:
	# add extra layers

	import_name = sources['import_name']
	city = sources['city']
	stage.stage(streets, layers_gdf, boundary_stage, city, import_name, visualize)

def check_visualization_limit(number_of_elements):
	return number_of_elements < VISUALIZE_LIMIT


# TODO: make sure streets has sw_left and sw_right and offset
# or change graph to handle alternate inputs
def standardize_streets(sources):
	streets_path = sources['layers']['streets']['path']
	print(streets_path)
	streets = gpd.read_file(streets_path)
	#print(streets.head())

if __name__ == "__main__":
	main()