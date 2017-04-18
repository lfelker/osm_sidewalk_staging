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
	redraw_sidewalks = True # allows for 

	click.echo("starting process")
	json_sources = open("source_json_examples/sources_neighborhood_boundary.json").read()
	sources = json.loads(json_sources)

	# TODO: load and clip data before graph creation? 
	streets_path = sources['layers']['streets']['path']
	streets =  gpd.read_file(streets_path)
	streets_crs = streets.crs

	lines = streets.loc[streets.geometry.type == 'LineString']
	multilines = streets.loc[streets.geometry.type == 'MultiLineString']
	print("Lines Count: " + str(len(lines)))
	print("MultiLines Count " + str(len(multilines)))

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
		print(type(paths))
		print(paths[0])
		edges = []
		geoms = []
		for path in paths:
			for edge in path["edges"]:
				geom = edge['geometry'].parallel_offset(1, 'right',
                                                					resolution=10,
   		                                          					join_style=2)
				if geom.type == 'MultiLineString':
					print("EDGE GEOMETRY")
					print(edge['geometry'])
					print("GEOM AFTER PARALLEL OFFSET")
					print(geom)
				geoms.append({'geometry': geom})
				edges.append(edge)

		edges_gdf = gpd.GeoDataFrame(edges)
		geoms_gdf = gpd.GeoDataFrame(geoms)
		print(edges_gdf.head())
		print(geoms_gdf.head())

		pathLines = edges_gdf.loc[edges_gdf.geometry.type == 'LineString']
		pathMulti = edges_gdf.loc[edges_gdf.geometry.type == 'MultiLineString']
		geomsMulti = geoms_gdf.loc[geoms_gdf.geometry.type == 'MultiLineString']

		print("Line Count = " + str(len(pathLines)))
		print("Multi Line Count = " + str(len(pathMulti)))
		print("Multi Line Count = " + str(len(geomsMulti)))

		#paths = remove_multi_and_short_chords2(paths)

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

def remove_multi_and_short_chords(paths):
	for path in paths:
		for edge in path['edges']:
			geom = edge['geometry']
			print(type(geom))
			if type(geom) == "MultiLineString" or len(geom.coords) < 2:
				print("here")
				path['edges'] = path['edges'].remove(edge)
	return paths

def remove_multi_and_short_chords2(paths):
	for path in paths:
		for edge in path['edges']:
			offset = edge['offset']
			if offset:
				geom = edge['geometry'].parallel_offset(offset, 'right',resolution=10, join_style=2)
				if geom.type == "MultiLineString" or len(geom.coords) < 2:
					print("heyo")
					path['edges'] = path['edges'].remove(edge)
	return paths

def explode_multilinestrings(df):
# Expand MultiLineStrings into separate rows of LineStrings
	linestrings = df.loc[df.geometry.type == 'LineString']

	newlines = []
	for i, row in df.loc[df.geometry.type == 'MultiLineString'].iterrows():
	    for geom in row.geometry:
	        # Keep metadata
	        newlines.append(row.copy())
	        newlines[-1].geometry = geom
	multilinestrings = gpd.GeoDataFrame(newlines)

	# Create fresh index
	df.reset_index(drop=True, inplace=True)

	df = gpd.GeoDataFrame(pd.concat([linestrings, multilinestrings]))

	return df

if __name__ == "__main__":
	main()