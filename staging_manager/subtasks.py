import geopandas as gpd
from shapely import ops, geometry
import shapely
import pandas as pd
import numpy as np
from scipy.spatial import Voronoi, voronoi_plot_2d

WEB_CRS = {'init': 'epsg:4326'}
AREA_THRESH = 0.0000000001

def get_tasks(streets, utm_crs, boundary, options):
    task_type = options['type']
    tasks = None
    if task_type == "voronoi":
        voronoi_tasks = voronoi_subtasks(streets, utm_crs)
        tasks = voronoi_tasks
    elif task_type == "block":
        tasks = blocks_subtasks(streets)
    else:
        raise ValueError("tasks division type " + task_type + " not supported")

    if boundary != None:
        if task_type == 'block':
            untasked_area = boundary
            # ensure every area is tasked by finding remaining area
            for task_poly in tasks['geometry']:
                untasked_area = untasked_area.difference(task_poly)
            untasked_polys = []
            # add extra polygons as additional tasks
            for polygon in untasked_area:
                # do not add very small areas that are probably errors in the street network
                if polygon.area > AREA_THRESH:
                    untasked_polys.append(polygon)
                    length = len(tasks)
                    tasks.loc[length] = {'geometry': polygon, 'poly_id': length}

            # bound.visualize(GeoSeries(untasked_polys), title="Extra Areas Found")
        tasks = filter_blocks_by_poly(tasks, boundary) # filter either task type hereA
    if tasks is None:
        raise Exception("Error in tasks creation")
    return tasks


def calculate_intersections(streets, utm_crs, cluster_distance=15):
    #
    # Strategy:
    #
    # 1) Identify all endpoints in the streets dataset
    # 1.5) Group endpoints by wkt to remove duplicates
    # 2) Buffer endpoints by specified distance
    # 3) Union endpoint buffers
    # 4) extract centroid from unioned buffers for rough estimate of intersection point

    # extract endpoints
    starts = streets.geometry.apply(lambda x: geometry.Point(x.coords[0]))
    ends = streets.geometry.apply(lambda x: geometry.Point(x.coords[-1]))
    frames = [starts, ends]
    results = gpd.GeoDataFrame( pd.concat( frames, ignore_index=True) )
    results.sindex
    results['wkt'] = results.apply(lambda r: r.geometry.wkt, axis=1)
    # group endpoints to remove duplicates
    grouped = results.groupby('wkt')

    def extract(group):
        geom = group.iloc[0]['geometry']
        return gpd.GeoDataFrame({
            'geometry': [geom]
        })

    corners = grouped.apply(extract)
    corners.reset_index(drop=True, inplace=True)
    corners.sindex
    # convert to local index
    corners.crs = streets.crs
    corners = corners.to_crs(utm_crs)
    # buffer in meters
    buffered_corners = corners.buffer(cluster_distance)
    # union by intersection
    buffered_corners = shapely.ops.unary_union(buffered_corners)
    # extract polygons
    intersections = []
    for polygon in buffered_corners:
        intersections.append(shapely.geometry.Polygon(polygon))
    isolated_intersections = gpd.GeoDataFrame(geometry=intersections)
    isolated_intersections.crs = utm_crs
    # grab centroid from each cluster
    intersection_centroids = isolated_intersections['geometry'].centroid

    return intersection_centroids.to_crs(WEB_CRS)

# calculates veronoi polygons from street intersection points
def voronoi_subtasks(streets, utm_crs):
    intersections = calculate_intersections(streets, utm_crs)

    points = []
    for point in intersections:
        coords = point.coords
        points.append([coords[0][0], coords[0][1]])
    points = np.array(points)

    vor = Voronoi(points)
    print(vor.ridge_vertices)

    lines = []
    for line in vor.ridge_vertices:
        if -1 not in line:
            # TODO: make check method for bad data that can be used in any city
            data_ok = True
            for point in vor.vertices[line]:
                if point[1] < 47.0:
                    print("ERROR")
                    print(point)
                    print(line)
                    data_ok = False
            if data_ok:
                lines.append(shapely.geometry.LineString(vor.vertices[line]))

    polygons = list(ops.polygonize(lines))
    res = gpd.GeoDataFrame(geometry=polygons)
    res.crs = WEB_CRS
    return res

    # import matplotlib.pyplot as plt
    # voronoi_plot_2d(vor)
    # plt.show()
    # print(vor)
    # return vor


def blocks_subtasks(streets):
    '''Given a street network as the input, generated polygons that roughly
    correspond to street blocks.

    Returns a GeoDataFrame of those blocks, numbered from 0 to n - 1.

    '''
    # Generate blocks by polygonizing streets. Not perfect, but pretty good.
    polygons = list(ops.polygonize(list(streets.geometry)))
    blocks = gpd.GeoDataFrame(geometry=polygons)
    blocks.crs = streets.crs
    blocks['poly_id'] = blocks.index

    return blocks

def blocks_poly_boundary_subtasks(streets, polygon):
    boundary = polygon.boundary
    geoms = list(streets.geometry)
    geoms.append(boundary)
    polygons = list(ops.polygonize(geoms))
    blocks = gpd.GeoDataFrame(geometry=polygons)
    blocks.crs = streets.crs
    blocks['poly_id'] = blocks.index
    new_blocks = blocks.loc[blocks.intersects(polygon)].copy()
    return new_blocks

def filter_blocks_by_poly(blocks, polygon):
    '''Given a GeoDataFrame of polygons (or anything, really), return it
    filtered by that polygon:
    1) Remove block polygons that don't intersect the new polygon
    2) Alter the shape of the block polygons to the intersection between the
       block and the polygon of interest. e.g. trim to the neighborhood.

    '''
    # Initialize the spatial index, if it wasn't already
    blocks.sindex

    # Find the blocks that intersect the polygon (bounding box intersection)
    query = blocks.sindex.intersection(polygon.bounds, objects=True)
    ids = [x.object for x in query]
    bbox_ixn = blocks.loc[ids]

    # Find the blocks that intersect the polygon (actual intersection)
    new_blocks = bbox_ixn.loc[bbox_ixn.intersects(polygon)].copy()

    # Alter the blocks to the shape of the enclosing polygon
    #new_blocks['geometry'] = new_blocks.intersection(polygon)

    # Recreate the index + poly_id
    new_blocks.reset_index(drop=True, inplace=True)
    new_blocks['poly_id'] = new_blocks.index

    return new_blocks