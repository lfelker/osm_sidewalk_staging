# TODO: dockerfile to install directories
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

import data_manager as dm
#from data_manager import graph, redraw

import staging_manager
from staging_manager import buffer_logic, bound, stage

import sidewalkify

def main():
	web_merc_crs = {'init': 'epsg:4326'}
	redraw_sidewalks = True # allows skipping or redraw during development

	click.echo("starting process")
	json_sources = open("source_json_examples/sources_point_buffer_boundary.json").read()
	sources = json.loads(json_sources)

	streets_path = sources['layers']['streets']['path']
	streets =  gpd.read_file(streets_path)
	streets_crs = streets.crs

	#TODO: click.echo("standardizing schema")
	# stadardize column names before being passed to graph
	# standardize_streets(sources)

	#TODO: click.echo("clean data")

	# when calculaing buffers and doing intersections this boundary needs to be in the same crs
	# as the streets dataset which whould be in utm
	boundary_clip   = bound.get_boundary(sources, streets_crs, streets_crs, buff_multiplier=1.25)
	boundary = bound.get_boundary(sources, streets_crs, streets_crs)
	sidewalks = None
	if redraw_sidewalks:
		if boundary_clip != None:
			click.echo("clipping streets to boundary")
			streets = bound.bound(streets, boundary_clip)
			if len(streets) == 0:
				raise ValueError("no streets found within specifiedboundary")
			bound.visualize(streets, buff=boundary, title="Streets in Boundary")
			#streets = streets.to_crs(streets_crs) # streets must be converted back to original crs before generating sidewalks
			# TODO: what if streets number is really large?

		click.echo("creating graph")
		G = sidewalkify.graph.create_graph(streets)

		click.echo("creating paths")
		paths = sidewalkify.graph.process_acyclic(G)
		paths += sidewalkify.graph.process_cyclic(G)

		# TODO: strip out MultiLineString here
		# input is only line strings - one to one mapping to street and sidewalks

		click.echo("redrawing sidewalks")
		sidewalks = sidewalkify.draw.draw_sidewalks(paths, streets_crs)
		click.echo("redrawn sidewalks outputed to ./source_data/sidewalks.shp")
		sidewalks.to_file('./output/cleaned/sidewalks.shp')
	else:
		sidewalks = gpd.read_file('./output/cleaned/sidewalks.shp')

	# do we need to clip sidewalks if streets have already been clipped? no
	click.echo("visualizing generated sidewalks")
	if boundary_clip != None:
		bound.visualize(sidewalks, buff=boundary, title="Generated Sidewalks In Boundary")
	else:
		bound.visualize(sidewalks, title="Generate Sidewalks")

	click.echo("converting projections to web mercator")
	sidewalks = sidewalks.to_crs(web_merc_crs)
	streets = streets.to_crs(web_merc_crs)
	# recalculate the boundary with web_merc_crs
	boundary_stage = bound.get_boundary(sources, streets_crs, web_merc_crs)
	bound.visualize(streets, boundary_stage)
	# TODO: convert boundary

	#generateCrossings()

	#annotate()

	#addcurbramps

	click.echo('starting staging process')
	layers_gdf = {
		'sidewalks': sidewalks
	}

	#if extra_layers:
	# add extra layers

	import_name = sources['import_name']
	city = sources['city']
	# Should bondary be in web mercator??
	stage.stage(streets, layers_gdf, boundary_stage, city, import_name)
	#stage()


# TODO: make sure streets has sw_left and sw_right and offset
# or change graph to handle alternate inputs
def standardize_streets(sources):
	streets_path = sources['layers']['streets']['path']
	print(streets_path)
	streets = gpd.read_file(streets_path)
	#print(streets.head())

if __name__ == "__main__":
	main()