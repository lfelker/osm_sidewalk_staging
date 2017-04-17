import geopandas as gpd
import os
import shutil
import click
from . import osm
from . import subtasks

# These should be consistent across imports
crs_staging = {'init': 'epsg:4326'}
base_url = 'https://import.opensidewalks.com'

# requires: street network to create tasks
#						boundary for data staging
# 					layers dictionary with sidewalk and crossing geo-data-frames to stage for OSM
# optional: curbramp geo-data-frame or additionaly layers in dictionary
# performs: stageing for OSM
def stage(streets, layers, boundary, city, title):
	click.echo('staging ' + title)

	tasks = subtasks.blocks_subtasks(streets)
	if boundary != None:
		tasks = subtasks.filter_blocks_by_poly(tasks, boundary)
	tasks.crs = crs_staging
	#tasks = tasks.to_crs(crs_staging)
	title_escp = title.replace(' ', '_')
	tasks_path = prepare_output_directory(tasks, city, title_escp)

	layers_gdfs = {}
	for layer_key in layers.keys():
		layers_gdfs[layer_key] = layers[layer_key].to_crs(crs_staging)

	layers_gdfs = prepare_layer_for_osm(layers_gdfs)
	tasks_gdfs = split_geometry_into_tasks(layers_gdfs, tasks)
	convert_to_osm_xml_and_write(layers_gdfs, tasks, tasks_gdfs, tasks_path, title_escp)
	click.echo('staging file was output to folder')


def prepare_output_directory(tasks, city, title_escp):
	folder = os.path.join(base_url, city, title_escp)
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
		if layer_name == 'sidewalks':
			layers = layer[['geometry']]
			layer['highway'] = 'footway'
			layer['footway'] = 'sidewalk'
		elif layer_name == 'crossings':
			layer = layer[['geometry', 'marked']]
			layer['highway'] = 'footway'
			layer['footway'] = 'crossing'
		elif layer_name == 'curbramps':
			layer = layer[['geometry']]
			layer['kerb'] = 'lowered'
			layers_gdfs[layer_name] = layer
	click.echo('done')
	return layers_gdfs


# requires: dictionary of layer name to layer geo-data-frame
#			tasks geo-data-frame
# returns: tasks with layer geometry added
def split_geometry_into_tasks(layers_gdfs, tasks):
	click.echo('spliting geometires into separate tasks')
	# Split into tasks and validate

	seen_it = {
		'sidewalks': set(),
		'curbramps': set(),
		'crossings': set()
	}

	tasks_gdfs = {}

	for idx, task in tasks.iterrows():
		click.echo('Processed task {} of {}'.format(idx, tasks.shape[0]))
		tasks_gdfs[idx] = {}

		for key, value in layers_gdfs.items():
			# FIXME: need to remove redundant data (use poly_id!)
			# Extract
			data = value.loc[value.intersects(task.geometry)].copy()

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
			features = osm.json_to_dom(the_json, featuretype=key)

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