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
	crs = {'init': 'epsg:4326'}
	redraw_sidewalks = True

	click.echo("starting process")
	json_sources = open("source_json_examples/sources_neighborhood_boundary.json").read()
	sources = json.loads(json_sources)

	# TODO: load and clip data before graph creation?
	streets_path = sources['layers']['streets']['path']
	streets =  gpd.read_file(streets_path)
	streets_crs = streets.crs

	click.echo("clipping streets")

	#TODO: click.echo("standardizing schema")
	# standardize_streets(sources)

	#TODO: click.echo("clean data")
	sidewalks = None
	if redraw_sidewalks:
		# TODO: clip data before graph creation.....
		# use explode_gemoitries

		click.echo("creating graph")
		G = sidewalkify.graph.create_graph(streets)

		click.echo("creating paths")
		paths = sidewalkify.graph.process_acyclic(G)
		paths += sidewalkify.graph.process_cyclic(G)

		# TODO: strip out MultiLineString here
		# input is only line strings - one to one mapping to street and sidewalks

		click.echo("redrawing sidewalks")

		sidewalks = sidewalkify.draw.draw_sidewalks(paths, streets_crs)
		sidewalks.to_file('./source_data/sidewalks.shp')
	else:
		sidewalks = gpd.read_file('./output/cleaned/sidewalks.shp')

	click.echo("converting projections")
	# Web Mercator
	# convert to web mercator
	sidewalks = sidewalks.to_crs(crs)
	streets = streets.to_crs(crs)

	click.echo("clipping data to boundary")
	boundary = bound.get_boundary(sources, crs)
	if boundary != None:
		sidewalks = bound.bound(sidewalks, boundary)
		if len(sidewalks) == 0:
			print("Error, No sidewalks in intersection.")
	else:
		bound.visualize(sidewalks)

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
	stage.stage(streets, layers_gdf, boundary, city, import_name)
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