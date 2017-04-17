from geopandas import GeoSeries

# visualization capabilities
import matplotlib.pyplot as plt
import matplotlib
import fiona

standard_crs = {'init': 'epsg:4326'}

# accepts a point, a buffer distance in meters, and the univeral transverse mercator (UTM) epsg value
# for example Seattle's utm epsg value is 26910. To find value for your city, google UTM [CITY NAME] epsg
# this projection value is needed to create an accurate buffer at the given distance
def buffer_point(point, distance, city_utm_epsg):
	point = point.to_crs(city_utm_epsg)
	buff = point.buffer(distance)
	buff = buff.to_crs(standard_crs)
	buff_result = buff.iloc[0]
	return buff_result

# accepts a geodataframe and a buffer, both in the same projection (probably epsg 4326)
# returns data within the buffer
def clip_data(data, buff):
	intersection = data.loc[data.intersects(buff)]
	return intersection

def plot_buffer(data, buff):
	cliped_streets = clip_data(data, buff)
	buffers = []
	buffers.append(buff)
	plot_ref = GeoSeries(buffers).plot()
	cliped_streets.plot(ax=plot_ref)
	cliped_streets.head()
	plt.show()