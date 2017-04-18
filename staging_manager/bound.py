import geopandas as gpd
from geopandas import GeoSeries
from . import buffer_logic

import matplotlib.pyplot as plt

def bound(data, boundary):
	clipped_data = buffer_logic.clip_data(data, boundary)
	return clipped_data

# Three options determined by sources boundary parameters
# 1) No Boundary
# 2) Boundary Passed In
# 3) Bondaries Passed in with Name
# 4) Point Passed in with Buffer Distance
# returns bondard in utm_crs passed as parameter
def get_boundary(sources, buffer_crs, result_crs, buff_multiplier=1):
	boundary_path = sources['boundary']['path']
	if boundary_path == "None":
		return None
	else:
		boundaries = gpd.read_file(boundary_path)
		# convert crs to standard web mercator so intersections line up
		boundaries = boundaries.to_crs(buffer_crs)
		# check if we need further selection of data like to a nighborhood
		if sources['boundary']['selection'] == "True":
			selector = sources['boundary']['attribute_selector']
			value = sources['boundary']['attribute_selector_value']
			boundary_selection = boundaries[boundaries[selector] == value]
			buffer_distance = sources['boundary']['buffer_distance_meters'] * buff_multiplier
			if buffer_distance > 0:
				# treat boundary as a point to buffer
				# return polygon boundary
				return buffer_logic.buffer_point(boundary_selection, buffer_distance, buffer_crs, result_crs)
			else:
				boundaries = boundary_selection.geometry
		
		assert len(boundaries) == 1

		# return first boundary, but key may not be zero
		for index, value in boundaries.iteritems():
			return value

def visualize(data, buff=None, title=None, extras=[]):
	#plt.ion()
	plot_ref = None
	if buff == None:
		plot_ref = data.plot(color='grey')
	else: 
		buffers = []
		buffers.append(buff)
		plot_ref = GeoSeries(buffers).plot()
		data.plot(ax=plot_ref, color='grey')
	if title != None:
		plt.title(title)
	if len(extras) > 0:
		for layer in extras:
			layer.plot(ax=plot_ref, color='blue')
	plt.show()
