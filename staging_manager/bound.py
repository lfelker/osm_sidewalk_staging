import geopandas as gpd
from geopandas import GeoSeries
from . import buffer_logic

import matplotlib.pyplot as plt

# Three options determined by sources boundary parameters
# 1) No Boundary
# 2) Boundary Passed In
# 3) Bondaries Passed in with Name
# 4) Point Passed in with Buffer Distance
def bound(sidewalks, boundary):
	sidewalks = buffer_logic.clip_data(sidewalks, boundary)
	print("number of sidewalks in section = " + len(sidewalks))
	print("visualizing area")
	visualize(sidewalks, buff=boundary)
	return sidewalks


def get_boundary(sources, crs):
	boundary_path = sources['boundary']['path']
	if boundary_path == "None":
		return None
	else:
		boundaries = gpd.read_file(boundary_path)
		# convert crs to standard web mercator so intersections line up
		boundaries = boundaries.to_crs(crs)
		# check if we need further selection of data like to a nighborhood
		if sources['boundary']['selection'] == "True":
			selector = sources['boundary']['attribute_selector']
			value = sources['boundary']['attribute_selector_value']
			boundary_selection = boundaries[boundaries[selector] == value]
			buffer_distance = sources['boundary']['buffer_distance_meters']
			if buffer_distance > 0:
				# treat boundary as a point to buffer
				# return polygon boundary
				# what projection should the buffer be done in??
				return buffer_logic.buffer_point(boundary_selection, buffer_distance)
			else:
				boundaries = boundary_selection.geometry
		
		assert len(boundaries) == 1

		# return first boundary, but key may not be zero
		for index, value in boundaries.iteritems():
			return value

def visualize(data, buff=None):
	#plt.ion()
	if buff == None:
		data.plot(color='grey')
		plt.show()
	else: 
		buffers = []
		buffers.append(buff)
		plot_ref = GeoSeries(buffers).plot()
		data.plot(ax=plot_ref, color='grey')
		plt.show()