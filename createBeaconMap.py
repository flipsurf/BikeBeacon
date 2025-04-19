# -*- coding: utf-8 -*-
"""
Created on Fri Jan 24 23:30:52 2020

@author: philipp

"""

# %%
# initialize imports & functions

# imports

import os
import json
import time
import requests
import pandas as pd
import folium
from folium.plugins import HeatMap, GroupedLayerControl
from folium.map import Marker, Template
import numpy as np
import datetime

# functions

def lightUpToken():
    
    # load data if available
    if os.path.exists('client.json'):
        with open('client.json') as json_file:
            client_data = json.load(json_file)
    else:
        raise Exception('File missing: client.json')

    if os.path.exists('access_refresh.json'):
        with open('access_refresh.json') as json_file:
            accessRefresh = json.load(json_file)
    else:
        raise Exception('File missing: access_refresh.json')

    # access token still valid?
    if accessRefresh['expires_at'] < time.time():
        # token expired
        print('Fetching a new token ...')
        # retrieve new accessToken with refresh_token
        url = 'https://www.strava.com/oauth/token?client_id={}&client_secret={}&grant_type=refresh_token&refresh_token={}'.format(client_data['id'], client_data['secret'], accessRefresh['refresh_token'])
        response = requests.post(url)
        if response.status_code == 200:
            accessRefresh = response.json()
            # store new tokens
            with open('access_refresh.json', 'w') as json_file:
                json.dump(accessRefresh, json_file)
            print('ok\n')
        else:
            raise Exception('Can not refresh token')
    else:
        # token still valid
        print('Token is still hot!!\n')

    return accessRefresh


def getActivitiesFromStrava(accessToken):
    # get list of all activities of athlet from strava 

    # create an empyt list to store the activities
    activityDataFrameList = []

    # thanks Benji
    # https://medium.com/swlh/using-python-to-connect-to-stravas-api-and-analyse-your-activities-dummies-guide-5f49727aac86
    page = 1
    url = "https://www.strava.com/api/v3/activities"


    # get 'em
    while True:
        # get page of activities from Strava
        resp = requests.get(url
                            + '?access_token='
                            + accessToken
                            + '&per_page=200'
                            + '&page='
                            + str(page))
        resp = resp.json()
        if resp:
           # otherwise add new data to dataframe
            for act in resp:
                df = activityToDataFrame(act)
                activityDataFrameList.append(df)
            page+=1  # "turn the page"
        else:  # no more results
            break  # --> exit while loop
    
    # concat dataframe list
    # TODO FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
    return pd.concat(activityDataFrameList)


def activityToDataFrame(actDict):
    # converts an activity dictionary to pandas dataframe after processing some values

    # get subvalues and drop value athlete
    actDict['ath_id'] = actDict['athlete']['id']
    actDict['ath_resource_state'] = actDict['athlete']['resource_state']
    _ = actDict.pop('athlete')
    # get subvalues and drop value map
    actDict['map_id'] = actDict['map']['id']
    actDict['map_resource_state'] = actDict['map']['resource_state']
    actDict['map_summary_polyline'] = actDict['map']['summary_polyline']
    _ = actDict.pop('map')
    # convert geo data to list
    actDict['end_latlng'] = [actDict['end_latlng']]
    actDict['start_latlng'] = [actDict['start_latlng']]

    return pd.DataFrame(actDict)


def createSegmentMarker(latlng, pop='some default text', tool='segment default name', antsRunning=False, geopath=''):
    
    # define marker
    markerStyle = ['bicycle', 'blue', '#FFFFFF']
    
    # popup
    iframe = folium.IFrame(pop,  # create an iframe with html text
                           width=200,
                           height=200
                           )
    fpop = folium.Popup(iframe)  # put iFrame in a popup
    
    # create the marker
    if antsRunning:
        mrk = folium.Marker(location=latlng,
            pathCoords=geopath,  # this is the geodata of the segment for the antpath
            popup=fpop,
            tooltip=tool,
            icon=folium.Icon(icon=markerStyle[0], prefix='fa',
                color=markerStyle[1],
                icon_color=markerStyle[2]
                ),
            )        
    else:
        mrk = folium.Marker(location=latlng,
            popup=fpop,
            tooltip=tool,
            icon=folium.Icon(icon=markerStyle[0], prefix='fa',
                color=markerStyle[1],
                icon_color=markerStyle[2]
                ),
            )
        
    return mrk


def timeStringToSeconds(timeString):
    # convert a string representing a time to seconds

    if type(timeString) == pd._libs.tslibs.timedeltas.Timedelta:
        return timeString.seconds
    if type(timeString) == datetime.timedelta:
        return timeString.seconds
    elif type(timeString) == str:
        if timeString == 'nan':
            return np.inf
        else:
            sec = sum(x * int(t)
                      for x, t in zip([1, 60, 3600], reversed(timeString.split(":"))))
            return sec
    elif type(timeString) == float or type(timeString) == int:
        if np.isnan(timeString):
            return np.inf
        else:
            return timeString


def secondsToTimeString(secs):
    '''
    Parameters
    ----------
    secs : int
        time in seconds

    Returns
    -------
    str
        time in xx:xx format
    '''
    return str(datetime.timedelta(seconds=secs))


# %% 
# check login token and refresh if necessary
accessRefresh = lightUpToken()
accessToken = accessRefresh['access_token']

# get athlete info (logged in athlete)
athleteUrl = 'https://www.strava.com/api/v3/athlete?access_token='+accessToken
resp = requests.get(athleteUrl)
if resp.status_code == 200:
    athleteData = resp.json()
    athleteName = ' '.join([athleteData['firstname'], athleteData['lastname']])
else:
    raise Exception('Error in request status code')


# %% 
# get strava activitiy data

# get activity list
dfActivities = getActivitiesFromStrava(accessToken)

# filter activities by ride (=bike)
dfActivities = dfActivities[dfActivities['type'] == 'Ride']

# load local data if available
dataRidesFile = 'BikeBeaconRidesData.pickle'
dataEffortsFile = 'BikeBeaconEffortsData.pickle'
if os.path.exists(dataRidesFile) & os.path.exists(dataEffortsFile):
    dfRides = pd.read_pickle('BikeBeaconRidesData.pickle')
    dfEfforts = pd.read_pickle('BikeBeaconEffortsData.pickle')
    localIds = dfRides.id.unique()    
else:
    dfRides = pd.DataFrame()
    dfEfforts = pd.DataFrame()
    localIds = []


# define streams which are fetched from strava
streamTypes = ['time',
         'latlng',
         'distance',
         'altitude',
         'velocity_smooth',
         'heartrate',
         # 'cadence',
         # 'watts',
         # 'temp',
         # 'moving',
         # 'grade_smooth',
         ]

# fetch data of new activities
for act in dfActivities.iterrows():
    act = act[1]
    if act.id not in localIds:

        # get each activity stream which is not already local available 
        ''' example   
        https://www.strava.com/api/v3/activities/5295899978/streams?keys=time,distance,latlng,altitude,velocity_smooth,heartrate&key_by_type=true
        '''
        url = "https://www.strava.com/api/v3/activities"
        
        acturl = (url
                  + '/'
                  + str(act.id)
                  + '/streams?keys='
                  + ','.join(streamTypes)
                  + '&key_by_type=true'
                  + '&access_token='
                  + accessToken
                  )
        resp = requests.get(acturl)
        resp = resp.json()
        respd = {x: resp[x]['data'] for x in resp.keys()}  # dict with values
        singleRide = pd.DataFrame(respd)  # dataframe from dict
        
        # catch some errors
        if 'distance' not in singleRide.columns:
            print('No distance, skipping new ride "'+act['name']+'" from',str(act.start_date_local),'!!')
            continue
        
        print('Adding new ride "'+act['name']+'" from',str(act.start_date_local),'!!')
        
        # unit conversion
        singleRide.velocity_smooth = singleRide.velocity_smooth*3.6  # m/s --> km/h
        singleRide.distance = singleRide.distance/1000  # m --> km
        
        # add specific activity data to dataframe
        singleRide['id'] = act.id
        singleRide['name'] = act['name']
        singleRide['date'] = act.start_date_local

        # add geo data
        latlnglst = list(zip(*singleRide['latlng']))
        singleRide['lat'] = latlnglst[0]
        singleRide['lng'] = latlnglst[1]

        # get gear name of activity
        gear = requests.get('https://www.strava.com/api/v3/gear/'
                            + act.gear_id
                            + '?access_token='
                            + accessToken
                            )
        gear = gear.json()
        singleRide['gear'] = gear['name']
        
        # stack new ride to rides df
        dfRides = pd.concat([dfRides, singleRide])

        # get activity segment efforts
        print('... fetching segment efforts')
        ''' example
        https://www.strava.com/api/v3/activities/5758953369?include_all_efforts=true"
        '''
        actEffortsUrl = (url
                         + '/'
                         + str(act.id)
                         + '?include_all_efforts=true'
                         + '&access_token='
                         + accessToken
                         )
        resp = requests.get(actEffortsUrl)
        resp = resp.json()
        
        myEfforts = dict()
        for each in resp['segment_efforts']:
            # create a sub-dict for every effort in myEfforts dict
            segmentId = each['id']
            myEfforts[segmentId] = {}
            myEfforts[segmentId].update(each['segment'])
            myEfforts[segmentId]['segment_id'] = each['segment']['id']
            myEfforts[segmentId]['act_id'] = each['activity']['id']
            myEfforts[segmentId]['athlete_name'] = athleteName
            myEfforts[segmentId]['elapsed_time'] = timeStringToSeconds(each['elapsed_time'])
            myEfforts[segmentId]['moving_time'] = timeStringToSeconds(each['moving_time'])
            myEfforts[segmentId]['rank'] = 0
            myEfforts[segmentId]['start_date'] = each['start_date'] # TODO
            myEfforts[segmentId]['start_date_local'] = each['start_date_local']


# store up-to-date rides data
dfRides.to_pickle('BikeBeaconRidesData.pickle')

# add new segment data if available
if 'myEfforts' in globals():
    # convert dict data in myEfforts to dataframe
    newEffortsDataframe = pd.DataFrame(index=myEfforts.keys(), data=myEfforts.values())
    # convert time columns in dataframe
    newEffortsDataframe['start_date'] = pd.to_datetime(newEffortsDataframe.start_date, utc=True)
    newEffortsDataframe['start_date_local'] = pd.to_datetime(newEffortsDataframe.start_date_local, utc=True)
    # stack new efforts to existing dataframe
    dfEfforts = pd.concat([dfEfforts, newEffortsDataframe])


# Theoretically here we have the same data whether started fresh or from local data
# As getting data is rate limited, we probably can not get all data at once at fresh start


# get stream data if missing from former run (e.g. as of rate limit drops)
mask = dfEfforts['stream_latlng'].isna()
missing_seg_geodata_id = dfEfforts.loc[mask, 'id'].unique()

for ctr, sid in enumerate(missing_seg_geodata_id):
    print(f'\r{ctr+1:~>3} of {len(missing_seg_geodata_id)}', end='')
   
    # get segment stream geodata
    '''
    "https://www.strava.com/api/v3/segments/8641856/streams?keys=latlng&key_by_type=true" -H "accept: application/json"
    '''
    segstreamurl = ('https://www.strava.com/api/v3/segments/'
                    # + '/'
                    + str(int(sid))
                    + '/streams?keys=latlng&key_by_type=true'
                    + '&access_token='
                    + accessToken
                    )
    resp = requests.get(segstreamurl)
    resp = resp.json()
    # possible faults:
    # resource not found
    # rate limit reached
    # ...
    matchid = dfEfforts['id'] == sid
    if 'message' in resp.keys():
        if resp['message'] == 'Resource Not Found':
            print('Ressource not found')
            dfEfforts.loc[matchid,'stream_latlng'] = ''
            continue
        # dfEfforts.loc[matchid,'stream_latlng'] = ''  # TODO ?!?
        # continue
    else:
        stream_latlng =  resp['latlng']['data']
        # write segment geo data to df @ matching segment id
        dfEfforts.loc[matchid,'stream_latlng'] = dfEfforts.apply(lambda x: stream_latlng, axis=1)

# store up-to-date efforts data
dfEfforts.sort_values('elapsed_time', inplace=True)
dfEfforts.to_pickle('BikeBeaconEffortsData.pickle')    



# %%
# create HTML HeatMap

# activate ants trace for markers?
antPathActive = True


# define map with styles
geoStart = [52.5172, 13.3024]
beaconMap = folium.Map(
    location=geoStart,
    zoom_start=7,
    # tiles='OpenStreetMap'
    # tiles='CartoDB dark_matter'
    # tiles='CartoDB positron',
    tiles=None
    )

folium.raster_layers.TileLayer(
    tiles='CartoDB positron',
    name='Light map',
    overlay=False,
    control=True,
    show=True,  # as this is true this is activated when map is opened
    ).add_to(beaconMap)

folium.raster_layers.TileLayer(
    tiles='CartoDB dark_matter',
    name='Dark map',
    overlay=False,
    control=True,
    show=False,
    ).add_to(beaconMap)

folium.raster_layers.TileLayer(
    tiles='OpenStreetMap',
    name='OpenStreetMap',
    overlay=False,
    control=True,
    show=False,
    ).add_to(beaconMap)


# add full screen button
folium.plugins.Fullscreen().add_to(beaconMap)


# add lat lng popup
beaconMap.add_child(folium.LatLngPopup())


if antPathActive:
    #### Modify Marker template to include the onClick event
    click_template = """{% macro script(this, kwargs) %}
        var {{ this.get_name() }} = L.marker(
            {{ this.location|tojson }},
            {{ this.options|tojson }}
        ).addTo({{ this._parent.get_name() }}).on('click', onClick);
    {% endmacro %}"""
    
    #### Change template to custom template
    Marker._template = Template(click_template)


## add the layercontrol in the map

# heatmap entries in layercontrol
featureGroupHeatmapDens = folium.FeatureGroup(name='point density')
featureGroupHeatmapDens.add_to(beaconMap)
featureGroupHeatmapPoly = folium.FeatureGroup(name='polylines')
featureGroupHeatmapPoly.add_to(beaconMap)
featureGroupHeatmapHidden = folium.FeatureGroup(name='hidden')
featureGroupHeatmapHidden.add_to(beaconMap)

# markergroups in layercontrol
segmentMarkerCluster = folium.plugins.MarkerCluster(
    name='Segment Markers',
    overlay=True,
    control=True,
    show=True,  # When changing this control box later you will show/hide all markers in subgroups of this!
    # disableClusteringAtZoom=10
    )
segmentMarkerCluster.add_to(beaconMap)

# sub groups for the marker cluster
segmentMarkerSubGroup1 = folium.plugins.FeatureGroupSubGroup(
    segmentMarkerCluster,  # this is the parent MarkerCluster
    name='segmentMarkerCluster sub1',
    show=True,  # True - activated at start
    control=False)  # True - show in controls (this is False as it is the only one atm.)
segmentMarkerSubGroup1.add_to(beaconMap)
# segmentMarkerSubGroup2 = folium.plugins.FeatureGroupSubGroup(segmentMarkerCluster, name='segmentMarkerCluster sub2')
# segmentMarkerSubGroup2.add_to(beaconMap)
# segmentMarkerSubGroup3 = folium.plugins.FeatureGroupSubGroup(segmentMarkerCluster, name='segmentMarkerCluster sub3')
# segmentMarkerSubGroup3.add_to(beaconMap)


# now, add the layercontrol itself
# all items added to beaconMap will be shown in the layercontrol
folium.map.LayerControl(collapsed=False).add_to(beaconMap)

# this group is added after the layercontrol itself to place it below the global layercontrol
GroupedLayerControl(
    groups={'Heatmap Style': [featureGroupHeatmapDens, featureGroupHeatmapPoly, featureGroupHeatmapHidden]},
    collapsed=False
).add_to(beaconMap)



if antPathActive:
    #### Create the onClick listener function as a branca element and add to the map html
    map_id = beaconMap.get_name()
    click_js = f"""function onClick(e) {{                
                        
                                     
                     var coords = e.target.options.pathCoords;
                     //var coords = JSON.stringify(coords);
                     //alert(coords);
                     var ant_path = L.polyline.antPath(coords, {{
                    "delay": 1500,
                    "dashArray": [
                        10,
                        20
                    ],
                    "weight": 5,
                    "color": "#0000FF",
                    "pulseColor": "#FFFFFF",
                    "paused": false,
                    "reverse": false,
                    "hardwareAccelerated": true
                    }}); 
                    
                    {map_id}.eachLayer(function(layer){{
                       if (layer instanceof L.Polyline)
                          {{ {map_id}.removeLayer(layer) }}
                          }});
                         
                    ant_path.addTo({map_id});
                     }}"""
                     
    e = folium.Element(click_js)
    html = beaconMap.get_root()
    html.script.add_child(e)


# add geo marker of each strava segment to the segmentMarkerSubGroup
# if there are conditions for different segmentMarkerSubGroup1/2/3/.. use them here to separate markers in diff. groups
for segmentId, segmentData in dfEfforts.groupby('segment_id'):

    # get segment name like it is called @ strava
    segmentLabel = list(segmentData.name)[0]
    
    # sort segment data by time
    segmentData = segmentData.sort_values('elapsed_time')

    # get all times of this segment in nice format
    segmentData['elapsed_time_str'] = segmentData['elapsed_time'].apply(secondsToTimeString)  # time
    segmentData['start_date_str'] = segmentData['start_date'].astype('string').str[0:10]
    
    # combine times and dates to list of time@date strings
    segmentTimesAtDate = [f'{z[0]} ({z[1]})' for z in zip(segmentData['elapsed_time_str'], segmentData['start_date_str'])]
    segmentTimesHtml = '<br>'.join(segmentTimesAtDate)  # "convert" to html compatible list

    # html popup text
    # segmentId = segmentData.loc[segmentData.index[0],'id']  # skipped as this is the same as the Id from groupby
    segmentUrl = '<a href="https://www.strava.com/segments/'+str(segmentId)+'" target="_blank">'+segmentLabel+'</a>'
    markerPopupText= ('{}<br><br>'      # link to segment on strava page
        '<b>rides:</b> {}<br>'          # number of times segment was ridden
        '<b>times:</b><br>{}'           # list of elapsed times
        ).format(segmentUrl,
            len(segmentTimesAtDate),
            segmentTimesHtml
            )
    
    # get geo data
    segmentGeoStart = list(segmentData['start_latlng'])[0]
    antPathGeo = list(segmentData['stream_latlng'])[0]
    antPathGeo = antPathGeo[::10]  # 'resample' to every 10th point
    
    # create marker and add to map
    mrk = createSegmentMarker(segmentGeoStart, markerPopupText, segmentLabel, antPathActive, antPathGeo)
    mrk.add_to(segmentMarkerSubGroup1)


# Add leaflet antpath plugin cdn link
link = folium.JavascriptLink("https://cdn.jsdelivr.net/npm/leaflet-ant-path@1.3.0/dist/leaflet-ant-path.js")
beaconMap.get_root().html.add_child(link)  
    

#### create density HeatMap
rad = 3
blu = 2.5
dataLimit = 100000  # max points for heatmap. As these are reduced random & global this should not change coloring
dataFraction = min(1, max(0.001, dataLimit / len(dfRides['latlng'])))
geoData = dfRides['latlng'].sample(frac=dataFraction)

HeatMap(
    geoData,
    radius=rad,
    blur=blu,
    gradient={'0.4': 'red', '0.6': 'yellow', '0.9': 'white'},
    # gradient={.4: “blue”, .6: “cyan”, .7: “lime”, .8: “yellow”, 1: “red”},  # this is the default
    min_opacity=0.3,
    ).add_to(featureGroupHeatmapDens)


#### create polyline heatmap
for actiId, actiData in dfRides.groupby('id'):

    folium.vector_layers.PolyLine(
        actiData['latlng'],
        smooth_factor=2,  # simplify at zooming
        weight=1.2,  # default 1
        opacity=0.4,
        color='red',
        ).add_to(featureGroupHeatmapPoly)

print('done')


# %%
# save HTML map

beaconMap.save('BikeBeaconMap.html')


# %%
