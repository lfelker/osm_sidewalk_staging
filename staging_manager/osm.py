'''Uses the modules in the osmizer cli app to convert GeoJSON for sidewalks,
curb ramps, and crossings (each in separate files) into a single merged OSM
file.

'''
import geojson

from staging_manager.osmizer.features.feature import Feature
from staging_manager.osmizer.features.crossing import Crossing
from staging_manager.osmizer.features.curbramp import CurbRamp
from staging_manager.osmizer.features.sidewalk import Sidewalk


def to_geojson(gdf):
    # Converts GeoDataFrame to GeoJSON. All non-geometry columns become
    # properties. Input validation is up to the user and all keys/values will
    # be coerced to strings.
    features = []
    for idx, row in gdf.iterrows():
        properties = row.to_dict()
        properties.pop('geometry')
        if 'marked' in properties:
            if properties['marked'] == '1':
                print('Zebra!')
                properties['crossing'] = 'zebra'
            properties.pop('marked')
        feature = geojson.Feature(geometry=row['geometry'],
                                  properties=properties)
        features.append(feature)
    fc = geojson.FeatureCollection(features)

    return fc


# Use Crossing, Sidewalk, CurbRamp classes (input is Python object of
# json.load) to contain intermediate data. Use .validate() to ensure good data.
# Use .convert() method to create XML DOM objects.
def json_to_dom(json, featuretype):
    if featuretype == 'crossings':
        features = Crossing(json)
    elif featuretype == 'curbramps':
        features = CurbRamp(json)
    elif featuretype == 'sidewalks':
        features = Sidewalk(json)
    else:
        raise ValueError('Only crossing, curbramp, sidewalk accepted')

    # Validate the data
    # FIXME: this was disabled because osmizer didn't actually use proper
    # OSM tags
    # features.validate()

    # Convert to dom
    return features.convert()


# Use Feature.__merge_doms(dom1, dom2) to iteratively build merged DOM.
def merge(dom1, dom2):
    return Feature.__merge_doms__(dom1, dom2)


# Use Feature.dedup(dom, tolerance) to dedupe the nodes. A good default
# tolerance is 0.0000001
def dedupe(dom, tolerance=0.0000001):
    return Feature.dedup(dom, tolerance)


# Write dom (XML tree) to file using (Feature).to_xml(dom, path)
def write_dom(dom, path):
    return Feature.to_xml(dom, path)
