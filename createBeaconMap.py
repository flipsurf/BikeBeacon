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
from folium.plugins import HeatMap
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
            access_refresh = json.load(json_file)
    else:
        raise Exception('File missing: access_refresh.json')

    # access token still valid?
    if access_refresh['expires_at'] < time.time():
        print('Fetching a new token ...')
        # retrieve new access_token with refresh_token
        url = 'https://www.strava.com/oauth/token?client_id={}&client_secret={}&grant_type=refresh_token&refresh_token={}'.format(client_data['id'], client_data['secret'], access_refresh['refresh_token'])
        response = requests.post(url)
        if response.status_code == 200:
            access_refresh = response.json()
            # store new tokens
            with open('access_refresh.json', 'w') as json_file:
                json.dump(response.json(), json_file)
            print('ok\n')
        else:
            raise Exception('Can not refresh token')
    else:
        print('Token is still hot!!\n')

    return access_refresh


def getActivitiesFromStrava(token):

    # thanks Benji
    # https://medium.com/swlh/using-python-to-connect-to-stravas-api-and-analyse-your-activities-dummies-guide-5f49727aac86
    page = 1
    url = "https://www.strava.com/api/v3/activities"
    # access_token = access_refresh['access_token']  # we get the token with function call
    # create an empyt list to store the activities
    activityDataFrameList = []
    # get 'em
    while True:
        # get page of activities from Strava
        resp = requests.get(url
                            + '?access_token='
                            + token
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
    iframe = folium.IFrame(pop,  # html style text .. next step: change font!!
                           width=200,
                           height=200
                           )
    fpop = folium.Popup(iframe)
    
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


def time2seconds(tstr):
    if type(tstr) == pd._libs.tslibs.timedeltas.Timedelta:
        return tstr.seconds
    if type(tstr) == datetime.timedelta:
        return tstr.seconds
    elif type(tstr) == str:
        if tstr == 'nan':
            return np.inf
        else:
            sec = sum(x * int(t)
                      for x, t in zip([1, 60, 3600], reversed(tstr.split(":"))))
        return sec
    elif type(tstr) == float or type(tstr) == int:
        if np.isnan(tstr):
            return np.inf
        else:
            return tstr


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
access_refresh = lightUpToken()
access_token = access_refresh['access_token']

# get athlete info (logged in athlete)
athleteUrl = 'https://www.strava.com/api/v3/athlete?access_token='+access_token
resp = requests.get(athleteUrl)
if resp.status_code == 200:
    athleteData = resp.json()
    athleteName = ' '.join([athleteData['firstname'], athleteData['lastname']])
else:
    raise Exception('Error in request status code')


# %% 
# get strava activitiy data

# get activity list
dfActivities = getActivitiesFromStrava(access_token)

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

me = dict()

# define streams
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
                  + access_token
                  )
        resp = requests.get(acturl)
        resp = resp.json()
        respd = {x: resp[x]['data'] for x in resp.keys()}  # dict with values
        singleRide = pd.DataFrame(respd)  # dataframe from dict
        
        # catch some errors
        if 'distance' not in singleRide.columns:
            print('Skip new ride "'+act['name']+'" from',str(act.start_date_local),'!!')
            continue
        
        print('Adding new ride "'+act['name']+'" from',str(act.start_date_local),'!!')
        
        # unit conversion
        singleRide.velocity_smooth = singleRide.velocity_smooth*3.6  # m/s --> km/h
        singleRide.distance = singleRide.distance/1000  # m --> km
        
        # add more infos
        singleRide['id'] = act.id
        singleRide['name'] = act['name']
        singleRide['date'] = act.start_date_local

        # add geo data
        latlnglst = list(zip(*singleRide['latlng']))
        singleRide['lat'] = latlnglst[0]
        singleRide['lng'] = latlnglst[1]

        # gear ????
        gear = requests.get('https://www.strava.com/api/v3/gear/'
                            + act.gear_id
                            + '?access_token='
                            + access_token
                            )
        gear = gear.json()
        singleRide['gear'] = gear['name']
        
        # stack new ride to df
        dfRides = pd.concat([dfRides, singleRide])

        # get activity efforts
        print('...fetching efforts')
        ''' example
        https://www.strava.com/api/v3/activities/5758953369?include_all_efforts=true"
        '''
        acteffurl = (url
                     + '/'
                     + str(act.id)
                     + '?include_all_efforts=true'
                     + '&access_token='
                     + access_token
                     )
        resp = requests.get(acteffurl)
        resp = resp.json()

        for each in resp['segment_efforts']:
            # create dict for every effort
            sid = each['id']
            me[sid] = {}
            me[sid].update(each['segment'])
            me[sid]['segment_id'] = each['segment']['id']
            me[sid]['act_id'] = each['activity']['id']
            me[sid]['athlete_name'] = athleteName
            me[sid]['elapsed_time'] = time2seconds(each['elapsed_time'])
            me[sid]['moving_time'] = time2seconds(each['moving_time'])
            me[sid]['rank'] = 0
            me[sid]['start_date'] = each['start_date'] # TODO
            me[sid]['start_date_local'] = each['start_date_local']


# store up-to-date data
dfRides.to_pickle('BikeBeaconRidesData.pickle')

if me:
    df_me_new = pd.DataFrame(index=me.keys(), data=me.values())
    df_me_new['start_date'] = pd.to_datetime(df_me_new.start_date, utc=True)
    df_me_new['start_date_local'] = pd.to_datetime(df_me_new.start_date_local, utc=True)
    dfEfforts = pd.concat([dfEfforts, df_me_new])
dfEfforts.sort_values('elapsed_time', inplace=True)  


# Theoretically here we have the same data whether started fresh or from local data
# As getting data is rate limited, we probably can not get all data at once at fresh start


# get stream data if missing from former run
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
                    + access_token
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

# store up-to-date data
dfEfforts.to_pickle('BikeBeaconEffortsData.pickle')    



# %%
# create HTML HeatMap

# activate ants trace for markers?
antPathActive = True


# define map with styles
geo_start = [52.5172, 13.3024]
beaconMap = folium.Map(
    location=geo_start,
    zoom_start=7,
    # tiles='OpenStreetMap'
    # tiles='CartoDB dark_matter'
    # tiles='CartoDB positron',
    tiles=None
    )

mapstyle_0 = folium.raster_layers.TileLayer(
    tiles='CartoDB positron',
    name='light',
    overlay=False,
    control=True,
    show=True,  # as this is true this is activated when map is opened
    )
mapstyle_0.add_to(beaconMap)

mapstyle_1 = folium.raster_layers.TileLayer(
    tiles='CartoDB dark_matter',
    name='dark',
    overlay=False,
    control=True,
    show=False,
    )
mapstyle_1.add_to(beaconMap)

mapstyle_2 = folium.raster_layers.TileLayer(
    tiles='OpenStreetMap',
    name='OpenStreetMap',
    overlay=False,
    control=True,
    show=False,
    )
mapstyle_2.add_to(beaconMap)


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

# heatmap entry in layercontrol
cl0 = folium.FeatureGroup(name='Heatmap!')
cl0.add_to(beaconMap)


# markergroups in layercontrol
mc = folium.plugins.MarkerCluster(
    name='Segment Markers',
    overlay=True,
    control=True,
    show=True,
    # disableClusteringAtZoom=10
    )
mc.add_to(beaconMap)


# cl1 = folium.plugins.FeatureGroupSubGroup(mc, name='Segment Rank 1-10')
# cl1.add_to(beaconMap)
# cl2 = folium.plugins.FeatureGroupSubGroup(mc, name='Segment Rank 11-100')
# cl2.add_to(beaconMap)
cl3 = folium.plugins.FeatureGroupSubGroup(
    mc,
    name='- Segment Markers sub1',
    #show=True,
    control=False)  # False --> deactivated on start
cl3.add_to(beaconMap)


# the layercontrol itself
lc = folium.map.LayerControl(collapsed=False)
lc.add_to(beaconMap)


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


### add geo marker of each strava segment to the FeatureGroupSubGroup
for segmentId, segmentData in dfEfforts.groupby('segment_id'):

    # get segment name like it is called @ strava
    segmentLabel = list(segmentData.name)[0]
    
    # sort segment data by time
    segmentData = segmentData.sort_values('elapsed_time')

    # get all times of this segment in nice format
    segmentData['elapsed_time_str'] = segmentData['elapsed_time'].apply(secondsToTimeString)  # time
    segmentData['start_date_str'] = segmentData['start_date'].str[0:10]  # date
    
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
    mrk.add_to(cl3)


# Add leaflet antpath plugin cdn link
link = folium.JavascriptLink("https://cdn.jsdelivr.net/npm/leaflet-ant-path@1.3.0/dist/leaflet-ant-path.js")
beaconMap.get_root().html.add_child(link)  
    

#### create HeatMap
rad = 3
blu = 2.5
dataLimit = 100000  # max points for heatmap. As these are reduced random & global this should not change coloring
dataFraction = min(1, max(0.001, dataLimit / len(dfRides['latlng'])))
geoData = dfRides['latlng'].sample(frac=dataFraction)

HeatMap(
    geoData,
    radius=rad,
    blur=blu,
    gradient={'0.6': 'red', '0.8': 'yellow', '0.9': 'white'},
    # gradient={.4: “blue”, .6: “cyan”, .7: “lime”, .8: “yellow”, 1: “red”},  # this is the default
    ).add_to(cl0)

print('done')


# %%
# save HTML map

beaconMap.save('BikeBeaconMap.html')

