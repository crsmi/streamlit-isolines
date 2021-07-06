# Updating for Isoline Routing API v8

import folium
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point,Polygon
import requests

import folium
from pathlib import Path

import flexpolyline as fp

import uuid


def isochrone_request(
    point,
    time_range='600',
    oord='destination',
    heretime='2020-01-29T09:00:00',
    transport_mode='car', #car,truck,pedestrian
    routing_mode='fast', #fast,short, - should only apply to distance
    optimize_for = 'quality',#quality,balanced,performance
    max_points = None,
    avoid_features=None,#"tollRoad,controlledAccessHighway,ferry,carShuttleTrain,tunnel,dirtRoad,difficultTurns",
    api_key=None,
    ):
    ''' Requires global `hereApiKey`'''
    params = {'apiKey': api_key, 'range[type]': 'time'}

    if oord=='destination':
        params['destination'] =  str(point[0]) + ',' + str(point[1])
        params['arrivalTime'] = heretime #+ '-04:00'
    elif oord=='origin':
        params['origin'] = str(point[0]) + ',' + str(point[1])
        params['departureTime'] = heretime #+ '-04:00'
    else:
        print('Error: oord should be "origin" or "destination"')
    params['transportMode'] = transport_mode
    params['routingMode'] = routing_mode
    params['range[values]'] =  time_range
    if max_points:
        params['shape[maxPoints]'] = str(max_points)
    params['optimizeFor'] = optimize_for
    if avoid_features:
        params['avoid[features]'] = avoid_features

    response = requests.get('https://isoline.router.hereapi.com/v8/isolines', params=params)


    if (response.status_code != 200) or ('isolines' not in response.json()):
        print(f'Error: Reponse: {response.status_code}',response.json())
        return gpd.GeoDataFrame(),response
    isolines = response.json()['isolines']
    polygons_per_isoline = [len(isoline['polygons']) for isoline in isolines]
    if max(polygons_per_isoline) > 1:
        print("ERROR: An isolines has more than one polygon.")
    ranges = [isoline['range'] for isoline in isolines]
    names = [r['value'] for r in ranges] 
    #print(isolines)
    if isolines[0]['polygons'] == []:
        # Handle Error where no polygon is returned by returning just the point
        print('Error',isolines,params,response.json())
        the_point = Point(float(point[1]),float(point[0]))
        isochrones = gpd.GeoDataFrame(names,crs='epsg:4326',columns=['range'],geometry=[Polygon([the_point,the_point,the_point])])
    else:
        polygons = [Polygon([(p[1],p[0]) for p in fp.decode(isoline['polygons'][0]['outer'])]) for isoline in isolines]    
        isochrones = gpd.GeoDataFrame(names,geometry=polygons,crs='epsg:4326',columns=['range'])
    return isochrones, response

def isochrone_request_v7(
    point,
    time_range='600',
    oord='destination',
    heretime='2020-01-29T09:00:00',
    transport_mode='car', #car,truck,pedestrian
    routing_mode='fast', #fast,short,
    optimize_for = 'quality',#quality,balanced,performance
    max_points = None,
    avoid_features=None,#"tollRoad,controlledAccessHighway,ferry,carShuttleTrain,tunnel,dirtRoad,difficultTurns",
    api_key=None,
    ):
    ''' 
    
    Translates a v8 style request into a v7 request and then gets the results.
    '''
    
    params = {'apiKey': api_key}

    if oord=='destination':
        params['destination'] =  'geo!' + str(point[0]) + ',' + str(point[1])
        params['arrival'] = heretime
        snap_point_label = 'destination'
    elif oord=='origin':
        params['start'] = 'geo!' + str(point[0]) + ',' + str(point[1])
        params['departure'] = heretime
        snap_point_label = 'start'
    else:
        print('Error: oord should be "origin" or "destination"')
    # Translate Routing Mode
    routing_mode_to_type_map = {'fast':'fastest','short':'shortest','balanced':'balanced'} # Balanced will not be used as it is not in v8
    routing_type = routing_mode_to_type_map[routing_mode]
    params['mode'] = routing_type + ';'
    params['mode'] += transport_mode + ';' # Ignores carHOV, publicTransport, publicTransportTimeTable and bicycle as these are not in v8
    params['mode'] += 'traffic:enabled'
    params['rangeType'] = 'time'
    params['range'] =  time_range
    if max_points:
        params['maxPoints'] = str(max_points)
    optimize_for_to_quality = {'quality':1,'balanced':2,'performance':3}
    params['quality'] = optimize_for_to_quality[optimize_for]
    if avoid_features:
        #TODO translae avoid_features into 4th param in mode - RouteFeatureType
        pass
        #params['avoid[features]'] = avoid_features

    # V7 only params
    params['singlecomponent'] = 'false' #This differs from how I previously ran catchments
    #TODO params['requestId'] = Used to trace request through the system

    response = requests.get('https://isoline.route.ls.hereapi.com/routing/7.2/calculateisoline.json', params=params)
    response_json = response.json()['response']

    if (response.status_code != 200) or ('isoline' not in response_json):
        print(f'Error: Reponse: {response.status_code}',response_json)
        return gpd.GeoDataFrame(),response
    isolines = response_json['isoline']
    polygons_per_isoline = [len(isoline['component']) for isoline in isolines]
    if max(polygons_per_isoline) > 1:
        print("ERROR: An isoline has more than one polygon.")
    # ranges = [isoline['range'] for isoline in isolines]
    # names = [r['value'] for r in ranges]
    names = [isoline['range'] for isoline in isolines]
    if isolines[0]['component'] == []:
        # Handle Error where no polygon is returned by returning just the point
        print('Error',isolines,params,response_json)
        the_point = Point(float(point[1]),float(point[0]))
        isochrones = gpd.GeoDataFrame(names,crs='epsg:4326',columns=['range'],geometry=[Polygon([the_point,the_point,the_point])])
    else:
        polygons = [Polygon([(float(p[1]),float(p[0])) for p in [point.split(',') for point in isoline['component'][0]['shape']]]) for isoline in isolines]    
        isochrones = gpd.GeoDataFrame(names,geometry=polygons,crs='epsg:4326',columns=['range'])
    # Get `Mapped Position` of input point snapped to a road.
    #print(response_json)
    snap_point = response_json[snap_point_label]['mappedPosition'] #Dict with {'latitude':,'longitude':} #NEW
    isochrones['snap_lat'] = snap_point['latitude']
    isochrones['snap_lon'] = snap_point['longitude']
    return isochrones, response



def isoline_version_request(requestId=None):
    if requestId == None:
        requestId = str(uuid.uuid4())
    params = {'X-Request-ID':requestId}
    response = requests.get('https://isoline.router.hereapi.com/v8/version?', params=params)
    response.raise_for_status()
    return response.json()


def map_catchments(catchments,start_loc = None):
    '''Requires that `range` be an identifier for each catchment row.'''
    if start_loc is None:
        start_loc = (catchments.iloc[0].snap_lat,catchments.iloc[0].snap_lon)

    m = folium.Map(
        location=start_loc,
        tiles='Stamen Toner',
        zoom_start=12
    )

    for range_value in catchments.range[::-1]:
        folium.features.GeoJson(
            catchments[catchments['range'] == range_value],
            style_function=lambda feature: {
                'fillColor': 'red',#feature['properties']['fillColor'],
                'opacity': 1,#feature['properties']['opacity'],
                'fillOpacity': .2,#feature['properties']['fillOpacity'],
                'color': 'red',#feature['properties']['color'],
                'weight': 3,#feature['properties']['weight']
            },
            name = str(range_value/60)
        ).add_to(m)

    folium.Circle(
        radius=50,
        location=start_loc,
        popup=f'Location: {start_loc}',
        color='black',
        fill=False,
    ).add_to(m)

    folium.TileLayer('cartodbpositron').add_to(m)
    folium.TileLayer('OpenStreetMap').add_to(m)
    folium.LayerControl().add_to(m)
    

    return m




def isochrone_batch_request(
    point,
    time_ranges='600',
    oord='origin',
    heretime='2020-01-29T09:00:00',
    transport_mode='car', #car,truck,pedestrian
    routing_mode='fast', #fast,short,
    optimize_for = 'quality',#quality,balanced,performance
    max_points = None,
    avoid_features=None,#"tollRoad,controlledAccessHighway,ferry,carShuttleTrain,tunnel,dirtRoad,difficultTurns",
    api_key=None,
    ):
    ''' DEPRECATED - Requires global `hereApiKey`
    
    Not Currently Used, single request at a time is made from app.py in order to track progress.
    '''
    print(point,time_ranges,oord,heretime,transport_mode,routing_mode,optimize_for,max_points,avoid_features)
    
    isochrone_list = []
    response_list = []
    for time_range in time_ranges.split(','):
        isochrone, response = isochrone_request(point,time_range=time_range,oord=oord,heretime=heretime,transport_mode=transport_mode,optimize_for = optimize_for, max_points = max_points, avoid_features=avoid_features,api_key = api_key)
        isochrone_list.append(isochrone)
        response_list.append(response)

    isochrones = pd.concat(isochrone_list)
    responses = response_list
    versionJson = isoline_version_request()
    return isochrones, responses, versionJson


def isochrone_group_request(
    point,
    time_ranges='600',
    oord='origin',
    heretime='2020-01-29T09:00:00',
    transport_mode='car', #car,truck,pedestrian
    routing_mode='fast', #fast,short,
    optimize_for = 'balance',#quality,balanced,performance
    max_points = None,
    avoid_features=None,#"tollRoad,controlledAccessHighway,ferry,carShuttleTrain,tunnel,dirtRoad,difficultTurns",
    api_key=None,
    ):
    """ DEPRECATED     
    Now using isochrone_batch_request as requesting many time ranges at once provides less fidelity on smaller rings.
    """

    print(point,time_ranges,oord,heretime,transport_mode,routing_mode,optimize_for,max_points,avoid_features)
    params = {'apiKey': api_key, 'range[type]': 'time'}

    if oord=='destination':
        params['destination'] =  str(point[0]) + ',' + str(point[1])
        params['arrivalTime'] = heretime
    else:
        params['origin'] = str(point[0]) + ',' + str(point[1])
        params['departureTime'] = heretime

    params['transportMode'] = transport_mode
    params['routingMode'] = routing_mode
    params['range[values]'] =  time_ranges
    if max_points:
        params['shape[maxPoints]'] = str(max_points)
    params['optimizeFor'] = optimize_for
    if avoid_features:
        params['avoid[features]'] = avoid_features

    response = requests.get('https://isoline.router.hereapi.com/v8/isolines?', params=params)


    if response.status_code != 200:
        print(f'Error: Reponse: {response.status_code}',response.json())
        return gpd.GeoDataFrame(),response
    isolines = response.json()['isolines']
    polygons_per_isoline = [len(isoline['polygons']) for isoline in isolines]
    if max(polygons_per_isoline) > 1:
        print("ERROR: An isolines has more than one polygon.")
    ranges = [isoline['range'] for isoline in isolines]
    names = [r['value'] for r in ranges] 
    #TODO add in location and orignalLocatino from request
    polygons = [Polygon([(p[1],p[0]) for p in fp.decode(isoline['polygons'][0]['outer'])]) for isoline in isolines]    
    isochrones = gpd.GeoDataFrame(names,geometry=polygons,crs='epsg:4326',columns=['range'])
    return isochrones, response