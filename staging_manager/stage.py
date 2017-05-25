import geopandas as gpd
from geopandas import GeoDataFrame, GeoSeries
import os
import shutil
import click
from . import osm
from . import subtasks
from . import bound

# These should be consistent across imports
FINAL_CRS = {'init': 'epsg:4326'}
BASE_URL = 'https://import.opensidewalks.com'

# requires: street network to create tasks
#					boundary for data staging
# 					layers dictionary with sidewalk and crossing geo-data-frames to stage for OSM
# optional: curbramp geo-data-frame or additionaly layers in dictionary
# performs: stageing for OSM
def stage(streets, layers, boundary, city, title, utm_crs, options):
	tasks = subtasks.get_tasks(streets, utm_crs, boundary, options)

	element_sum = 0
	for layer in layers:
		element_sum += len(layers[layer])
	click.echo(str(element_sum) + " Sidewalks Split Into " + str(len(tasks)) + " Tasks")

	title_escp = title.replace(' ', '_')
	tasks_path = prepare_output_directory(tasks, city, title_escp)

	layers_gdfs = {}
	for layer_key in layers.keys():
		layers_gdfs[layer_key] = layers[layer_key].to_crs(FINAL_CRS)

	vis_data = []
	for key in layers_gdfs.keys():
		vis_data.append(layers_gdfs[key])

	bound.visualize(tasks, title=str(len(tasks)) + " Tasks Created", extras=vis_data)

	layers_gdfs = prepare_layer_for_osm(layers_gdfs)

	tasks_gdfs = split_geometry_into_tasks(layers_gdfs, tasks)
	convert_to_osm_xml_and_write(layers_gdfs, tasks, tasks_gdfs, tasks_path, title_escp)


def prepare_output_directory(tasks, city, title_escp):
	folder = os.path.join(BASE_URL, city, title_escp)
	poly_ids = tasks['poly_id'].astype(str)
	tasks['url'] = folder + '/' + poly_ids + '/' + title_escp + '-' + poly_ids + '.osm'

	# Prepare output directory
	tasks_path = './output/{}'.format(title_escp)
	if os.path.exists(tasks_path):
		shutil.rmtree(tasks_path)
	os.mkdir(tasks_path)

	staging_path = ('./output/{}/{}.geojson'.format(title_escp, title_escp))
	tasks.to_file(staging_path, driver='GeoJSON')
	return tasks_path


# requires: dictionary of layer name to layer geo-data-frame
# returns: layers dictionary with osm taggs added as columns 
def prepare_layer_for_osm(layers_gdfs):
	click.echo('adding tags')
	for layer_name in layers_gdfs.keys():
		layer = layers_gdfs[layer_name]
		if layer_name == 'sidewalks' or layer_name == 'links':
			if 'associatedStreet' in layer:
				layer = layer[['geometry', 'associatedStreet']]
			else:
				layer = layer[['geometry']]
			layer['highway'] = 'footway'
			layer['footway'] = 'sidewalk'
			layer['wheelchair'] = 'yes'
			layer['surface'] = 'paved'
		elif layer_name == 'crossings':
			if 'marked' in layer:
				layer = layer[['geometry', 'marked']]
			else:
				layer = layer[['geometry']]
			layer['highway'] = 'footway'
			layer['footway'] = 'crossing'
			layer['surface'] = 'paved'
			layer['crossing'] = 'unmarked'
		elif layer_name == 'raised_curbs':
			layer = layer[['geometry']]
			layer['kerb'] = 'raised'
		elif layer_name == 'lowered_curbs':
			layer = layer[['geometry']]
			layer['kerb'] = 'lowered'

		# all get
		layer['project'] = 'OpenSidewalks'
		layers_gdfs[layer_name] = layer
	click.echo('done')
	return layers_gdfs


# requires: dictionary of layer name to layer geo-data-frame
#			tasks geo-data-frame
# returns: tasks with layer geometry added
def split_geometry_into_tasks(layers_gdfs, tasks):
	click.echo('spliting geometires into separate tasks')
	# Split into tasks and validate

	seen_it = {}

	for key in layers_gdfs.keys():
		seen_it[key] = set()

	# print(seen_it)
	# print(layers_gdfs)
	# print(tasks)

	tasks_gdfs = {}

	for idx, task in tasks.iterrows():
		click.echo('Processed task {} of {}'.format(idx, tasks.shape[0]))
		tasks_gdfs[idx] = {}

		for key, value in layers_gdfs.items():
			# FIXME: need to remove redundant data (use poly_id!)
			# Extract
			data = value.loc[value.intersects(task.geometry)].copy()
			# print("DATA")
			# print(data)

			# Check the set of IDs we've seen and remove the features if we've
			# already processed them into a task. Add the new IDs to the ID set for
			# this layer.
			data = data.loc[~data.index.isin(seen_it[key])]
			for layer_idx in list(data.index):
				seen_it[key].add(layer_idx)

			tasks_gdfs[idx][key] = data
	click.echo('Done')
	return tasks_gdfs


def convert_to_osm_xml_and_write(layers_gdfs, tasks, tasks_gdfs, tasks_path, title_escp):
	click.echo('converting to osm xml')
	for idx, task in tasks.iterrows():
		task_dirname = os.path.join(tasks_path, str(task['poly_id']))
		task_fname = '{}-{}.osm'.format(title_escp, task['poly_id'])
		task_path = os.path.join(task_dirname, task_fname)

		if not os.path.exists(task_dirname):
			os.mkdir(task_dirname)

		task_layers = {}

		for key, value in layers_gdfs.items():
			data = tasks_gdfs[idx][key]

			# Convert to GeoJSON
			the_json = osm.to_geojson(data)

			# Convert to osmizer intermediate format (OSM-compatible).
			feature_type = key
			if key == 'links':
				feature_type = 'sidewalks'
			elif key == 'raised_curbs' or key == 'lowered_curbs':
				feature_type = 'curbramps'

			features = osm.json_to_dom(the_json, featuretype=feature_type)

			task_layers[key] = features

			# Combine OSM XML DOMs into a single DOM and dedupe
			# TODO: fix the way that merge works - it edits the first argument inplace.
			# same for dedupe...
			merged = None
			for layer in task_layers.keys():
				if merged == None:
					merged = task_layers[layer]
				else:
					osm.merge(merged, task_layers[layer])
			osm.dedupe(merged)
			osm.write_dom(merged, task_path)