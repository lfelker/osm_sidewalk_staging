import geopandas as gpd
from shapely import ops


def blocks_subtasks(streets):
    '''Given a street network as the input, generated polygons that roughly
    correspond to street blocks.

    Returns a GeoDataFrame of those blocks, numbered from 0 to n - 1.

    '''
    # Generate blocks by polygonizing streets. Not perfect, but pretty good.
    polygons = list(ops.polygonize(list(streets.geometry)))
    blocks = gpd.GeoDataFrame(geometry=polygons)
    blocks['poly_id'] = blocks.index

    return blocks


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
    new_blocks['geometry'] = new_blocks.intersection(polygon)

    # Recreate the index + poly_id
    new_blocks.reset_index(drop=True, inplace=True)
    new_blocks['poly_id'] = new_blocks.index

    return new_blocks