import time as tim
import base64
import tempfile

import streamlit as st
from streamlit_folium import folium_static
import numpy as np
import pandas as pd 
# import geopandas as gpd 

#import matplotlib.pyplot as plt
#import plotly_express as px 

# import os
# import shutil
import zipfile
import isolines

from datetime import time, date, timedelta, datetime
import json

# import pathlib

# import pickle
import pprint
st.set_page_config(layout="wide",page_title="Isoline Calculation",page_icon=":world_map:",initial_sidebar_state="collapsed")
here_api_key = st.secrets['here_api_key']


# Code for google login
import io
import os
import asyncio

# For Gooogle Authentication
from httpx_oauth.clients.google import GoogleOAuth2

# For download button
import re
import uuid

def create_coordinate_column(df):
    st.header("Select Coordinate Columns")
    st.info("Select latitude and longitude columns")
    latitude = st.selectbox("Select Latitude Column", df.columns.tolist())
    longitude = st.selectbox("Select Longitude Column", df.columns.tolist(),1)
    st.info("Example correct coordinates: 37.792408,-122.404735")  
    df["latlon"] =  df[latitude].str.strip()+ ',' + \
                df[longitude].str.strip()
    return df

def add_label_column(df):
    label_col = st.selectbox("Select Label Column", df.columns.to_list()[:-1])
    return label_col

def select_quality():
    st.header("Select Quality of Isoline Request")
    line_quality = st.select_slider("Quality",options=['Quality','Balanced','Performance'], value='Quality')
    if st.checkbox('Select Max Points',value=False):
        max_points = st.number_input('Max Request Points',min_value=31,max_value=4294967295,value=4294967295)
    else:
        max_points = None
    return line_quality.lower(), max_points

def select_transport_mode():
    st.header("Select Transport Mode")
    mode = st.radio("Mode",options=['Car','Truck','Pedestrian'],index=0)
    return mode.lower()

def select_routing_mode():
    st.header("Select Routing Mode")
    mode = st.radio("Mode",options=['Fast','Short'],index=0)
    return mode.lower()

def select_origin_or_destination():
    st.header("Select Origin or Destination")
    oord = st.radio("Origin or Destination",options=['Origin','Destination'],index=1)
    return oord.lower()
    
def select_date():
    # Select Date to use to Simulate Traffic
    #st.header("Select Traffic Date")
    st.info("Based on exploring the HERE API previously, a date too far in the past or too recent will give generic numbers. Aim for a couple weeks ago, but within the last 6 months.")
    ic = (date.today() - timedelta(weeks=3)).isocalendar()
    
    target_date = datetime.strptime(f'{ic[0]} {ic[1]} 3', '%G %V %u')
    
    day = st.date_input("Date", value=target_date, min_value=date.today() - timedelta(weeks=53), max_value=date.today())
    return day

def select_tod():
    #st.header("Select Traffic Time of Day")
    st.info("Select Time of Day to run catchments.")
    tod = st.time_input('Time of Day', time.fromisoformat('08:30:00'))
    return tod

def select_time_rings():
    st.header("Select Time Rings")
    st.info("Select Time Rings (in minutes), separated by commas. (Max 540 mins)")
    time_rings = st.text_input("e.g. 5,10,15,30",value='5')         
    time_range_secs = ','.join([str(int(float(x)*60)) for x in time_rings.split(',')])
    time_range_wp = ','.join([str(int(float(x)*6/5)) for x in time_rings.split(',')])
    st.write("In Seconds: " + time_range_secs)
    st.write("WP Minutes: " + time_range_wp)
    return time_range_secs


# def download_shapefile(df, settings_dict, shp_name):
#     print(settings_dict)
#     shp_name = f'{shp_name}-hereApi-isochrones-{date.today().strftime("%Y%m%d")}'
#     if os.path.exists(shp_name) and os.path.isdir(shp_name):
#         shutil.rmtree(shp_name)
#     os.mkdir(shp_name)

#     # Geodataframe to Shapefile
#     df.to_file(f"{shp_name}/{shp_name}.shp")

#     # Save Settings
#     with open(f'{shp_name}/hereApi-settings.json','w') as f:
#         json.dump(settings_dict,f)
#     with open(f'{shp_name}/hereApi-settings.txt','a') as f:
#         f.write('Here API Settings\n')
#         f.write(pprint.pformat(settings_dict,indent=1))


#     # Zip em up
#     zip_path = "timerings.zip"
#     zipf = zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED)

#     #Write to zip file
#     for root, dirs, files in os.walk(shp_name):
#         for file in files:
#             zipf.write(os.path.join(root,file))
#     zipf.close()

#     with open(zip_path, "rb") as f:
#         bytes = f.read()
#         b64 = base64.b64encode(bytes).decode()


#     href = f'<a href="data:file/zip;base64,{b64}">Download ZIP ShapeFile</a> (right-click and save as &lt;some_name&gt;.zip)'
#     return href

def download_zipshapefile(gdf, settings_dict,shp_name):
    shp_name_full = f'{shp_name}-hereApi-isochrones-{date.today().strftime("%Y%m%d")}'
    with tempfile.TemporaryDirectory() as tmp_dir:
        gdf.to_file(os.path.join(tmp_dir, f'{shp_name_full}.shp'), driver='ESRI Shapefile')
        with open(f'{tmp_dir}/hereApi-settings.json','w') as f:
            json.dump(settings_dict,f)
        with open(f'{tmp_dir}/hereApi-settings.txt','a') as f:
            f.write('Here API Settings\n')
            f.write(pprint.pformat(settings_dict,indent=1))
    
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED, False) as zip_file:
            for file in os.listdir(tmp_dir):
                zip_file.write(os.path.join(tmp_dir, file), file)
    # b64 = base64.b64encode(zip_buffer.getvalue()).decode()
    # href = f'<a href="data:file/zip;base64,{b64}">Download ZIP ShapeFile</a> (right-click and save as &lt;some_name&gt;.zip)'
    # return href
    download_button(zip_buffer.getvalue(),f'{shp_name_full}.zip',"Download Shapefile")
    

def get_isolines(coord_series,time_range_secs, oord='origin', heretime='2020-01-29T09:00:00',transport_mode='car',routing_mode='fast',optimize_for='balanced',max_points=None, api_version="v7"):
    """point,
    time_ranges='600',
    oord='origin',
    heretime='2020-01-29T09:00:00',
    transport_mode='car', #car,truck,pedestrian
    routing_mode='fast', #fast,short,
    optimize_for = 'balance',#quality,balanced,
    max_points = None,
    avoid_features=None,#"tollRoad,controlledAccessHighway,ferry,carShuttleTrain,tunnel,dirtRoad,difficultTurns"
    """
    catchment_list = []
    catchment_responses = []
    catchment_snap_points = []
    progress_bar = st.progress(0.0)
    progress_text = st.empty()
    start = tim.time()
    isochrone_times = np.array([])
    time_ranges = time_range_secs.split(',')
    number_of_requests = coord_series.shape[0]*len(time_ranges)
    print('Number of requests to Here API Expected:',number_of_requests)
    request_counter = 0
    time_remaining = 'Calculating...'
    #TODO: Add UUID to use in all requests here
    apiVersionJson = isolines.isoline_version_request()
    for idx, value in coord_series.str.split(',').iteritems():
        iter_start = tim.time()
        #isochrone_df, responses = isolines.isochrone_batch_request(value, time_range_secs, oord=oord, heretime=heretime,transport_mode=transport_mode,optimize_for=optimize_for,max_points=max_points)
        # Moving above code into here to track progress
        isochrone_list = []
        responses = []     
        for _, time_range in enumerate(time_ranges):
            if api_version == "v7":
                isochrone, response = isolines.isochrone_request_v7(value,time_range=time_range,oord=oord,heretime=heretime,transport_mode=transport_mode,routing_mode=routing_mode,optimize_for = optimize_for, max_points = max_points, avoid_features=None,api_key=here_api_key)
            elif api_version == "v8":
                isochrone, response = isolines.isochrone_request(value,time_range=time_range,oord=oord,heretime=heretime,transport_mode=transport_mode,routing_mode=routing_mode,optimize_for = optimize_for, max_points = max_points, avoid_features=None,api_key=here_api_key)
            request_counter += 1
            isochrone_list.append(isochrone)
            responses.append(response)
            # Update Progress
            progress_bar.progress(request_counter/number_of_requests)
            progress_text.write(f'Isochrone {request_counter} of {number_of_requests}. Time remaining: {time_remaining}')
        isochrone_df = pd.concat(isochrone_list)
        #isochrone_df, responses = isolines.isochrone_group_request(value, time_range_secs, oord=oord, heretime=heretime,transport_mode=transport_mode,optimize_for=optimize_for,max_points=max_points)
        
        catchment_list.append(isochrone_df)
        catchment_responses.append(responses)

        # Update Progress
        progress_bar.progress((idx+1)/coord_series.shape[0])
        isochrone_times = np.append(isochrone_times,(tim.time()-iter_start))
        if idx%100==0:
            print('Time and shape:',isochrone_times.mean(),idx,coord_series.shape[0])
        time_remain = round(isochrone_times.mean()*(coord_series.shape[0]-idx-1))
        time_remaining = ''
        if time_remain > 3600:
            time_remaining += str(time_remain//3600) + ' hours '
            time_remain = time_remain%3600
        if time_remain > 60:
            time_remaining += str(time_remain//60) + ' minutes '
            time_remain = time_remain%60
        time_remaining += str(time_remain) + ' seconds'
        progress_text.write(f'Isochrone {request_counter} of {number_of_requests}. Time remaining: {time_remaining}')
    return catchment_list, catchment_responses, apiVersionJson

def combine_isoline_dfs(coord_series,df_list,label_series=None):
    latlon_list = coord_series.str.split(',').to_list()
    if label_series is not None:
        label_list = label_series.to_list()
    for i, geodf in enumerate(df_list):
        geodf['inputrow'] = i
        if label_series is not None:
            geodf['label'] = label_list[i]
        geodf['latitude'] = latlon_list[i][0]
        geodf['longitude'] = latlon_list[i][1]
    combined_list = pd.concat(df_list)
    combined_list['time_ring'] = combined_list['range']/60
    col_order = ['inputrow','latitude','longitude','range','time_ring','snap_lat','snap_lon','geometry']
    if label_series is not None:
        col_order.insert(1,'label')
    return combined_list[col_order]

def main(user_id, user_email):

    st.write(f"You're logged in as {user_email}")
    # Original Code
    _,center,_ = st.columns([1,8,2])
    st.sidebar.title('Isochrone (Time Ring) Creation')
    apiVersion = st.sidebar.radio('Here API Version:',['v7','v8'],0)
    with center:
        # st.title("Isochrone (Time Ring) Creation - Here Isoline Routing API v8")
        st.markdown("Upload a CSV File with coordinate columns (Latitude & Longitude)")
        file = st.file_uploader("Choose a file") #width=25
    if file is not None:
        file.seek(0)
        with center:        
            with st.spinner('Reading CSV File...'):
                df = pd.read_csv(file, low_memory=False, dtype=str)
            st.success('Done!')
            st.write(df.head())
            st.write(df.shape)

        # Create column layout
        
        col1, _, col2 = st.columns([2,.2, 4]) 

        # Select correct Coordinates
        with col1:            
            df_coords = create_coordinate_column(df)
            st.write(df_coords["latlon"].rename('coordinates').head())

        # Ask for label column
        label_series = None
        with col1:
            if st.checkbox('Would you like to choose a column to use for labels?'):
                label_series = df[add_label_column(df)]
                

        # Select Time Rings Wanted
        with col2:
            time_range_secs = select_time_rings()
            
        # Select More Info
        with col1:
            line_quality, max_points = select_quality()
            transport_mode = select_transport_mode()
            routing_mode = select_routing_mode()
            oord = select_origin_or_destination()
            st.header("Select Traffic Date and Time")
            day = select_date()
            tod = select_tod()  

        heretime = day.strftime("%Y-%m-%d") + "T" + tod.strftime("%H:%M:%S")
        
        # Ask for shapefile name #TODO move this down below the creation
        with col2:
            shp_name = st.text_input("Shapefile Name",'shapefile')
            if shp_name != '':
                st.write(f'{shp_name}-hereApi-isochrones-{date.today().strftime("%Y%m%d")}')

        # Allow running of catchments on first point only
        col2.header("Preview First Isoline")
        preview = col2.checkbox("Preview on first point only", value=True)

        submit_button = col2.button("Submit")
        if submit_button:                      
            #Select all points or just first for preview
            if preview:
                coords = df_coords['latlon'].loc[0:0]
            else:
                coords = df_coords['latlon']
            with col2:
                point_catchment_list, point_response_list, apiVersionJson = get_isolines(coords, time_range_secs, oord, heretime,transport_mode=transport_mode,routing_mode=routing_mode,optimize_for=line_quality, max_points=max_points,api_version=apiVersion)
            # st.write(type(point_catchment_list[0]),point_catchment_list[0])
            # st.write(point_catchment_list.index)
            settings_dict = {
                'coords': coords.to_list(),
                'time_ranges_in_seconds': time_range_secs,
                'origin_destination': oord,
                'date_tod':heretime,
                'transport_mode':transport_mode,
                'routing_mode':routing_mode,
                'request_quality': line_quality,
                'max_points': max_points,
                'apiVersionInfo':apiVersionJson
            }

            # Preview catchments from first point
            isochrone_df = point_catchment_list[0]
            
            with col2:
                st.header("Displaying Time Rings for first point")
                st.write(df_coords.head(1))
                # st.write(isochrone_df)
                folium_static(isolines.map_catchments(isochrone_df,start_loc=(coords.loc[0].split(','))))                
                
                with st.spinner('Saving Data and Generating Download File...'):
                    # Combine Catchments
                    
                    combined_catchments = combine_isoline_dfs(df_coords['latlon'],point_catchment_list,label_series)
                    # st.write(combined_catchments)
                    # num_points_list = combined_catchments.geometry.exterior.apply(lambda x: len(x.xy[0]) if x else 1)
                    # st.write(num_points_list)
                    # st.write(num_points_list.sum())

                    #Temporary Save for Safety
                    #save_temp(combined_catchments, settings_dict, point_response_list)

                    #Download Shapefiles
                    st.header("Download")
                    download_zipshapefile(combined_catchments, settings_dict, shp_name)
                    #st.markdown(download_zipshapefile(combined_catchments, settings_dict, shp_name), unsafe_allow_html=True)
            

            #TODO: Show Response Info here
            with col2:                
                with st.beta_expander("See response to first request."):
                    st.json(point_response_list[0][0].json())

# def save_temp(df, settings, responses):
#     # Save Settings
#     with open(f'tmp_save/tmp-hereApi-settings.json','w') as f:
#         json.dump(settings,f)
#     with open(f'tmp_save/tmp-hereApi-settings.txt','a') as f:
#         f.write('Here API Settings')
#         for k,v in settings.items():
#             f.write(f"{k}: {v}\n")
#     df.to_pickle('tmp_save/tmp_df.pickle')
#     with open(f'tmp_save/tmp_responses.pickle','wb') as f:
#         pickle.dump(responses,f)        

def download_button(
    object_to_download, download_filename, button_text  # , pickle_it=False
):
    """
    Generates a link to download the given object_to_download.
    
    From: https://discuss.streamlit.io/t/a-download-button-with-custom-css/4220
    Params:
    ------
    object_to_download:  The object to be downloaded.
    download_filename (str): filename and extension of file. e.g. mydata.csv,
    some_txt_output.txt download_link_text (str): Text to display for download
    link.
    button_text (str): Text to display on download button (e.g. 'click here to download file')
    pickle_it (bool): If True, pickle file.
    Returns:
    -------
    (str): the anchor tag to download object_to_download
    Examples:
    --------
    download_link(your_df, 'YOUR_DF.csv', 'Click to download data!')
    download_link(your_str, 'YOUR_STRING.txt', 'Click to download text!')
    """
    # if pickle_it:
    #     try:
    #         object_to_download = pickle.dumps(object_to_download)
    #     except pickle.PicklingError as e:
    #         st.write(e)
    #         return None

    # else:
    #     if isinstance(object_to_download, bytes):
    #         pass

    #     elif isinstance(object_to_download, pd.DataFrame):
    #         object_to_download = object_to_download.to_csv(index=False)

    #     # Try JSON encode for everything else
    #     else:
    #         object_to_download = json.dumps(object_to_download)

    try:
        # some strings <-> bytes conversions necessary here
        b64 = base64.b64encode(object_to_download.encode()).decode()
    except AttributeError as e:
        b64 = base64.b64encode(object_to_download).decode()

    button_uuid = str(uuid.uuid4()).replace("-", "")
    button_id = re.sub("\d+", "", button_uuid)

    custom_css = f""" 
        <style>
            #{button_id} {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                background-color: rgb(255, 255, 255);
                color: rgb(38, 39, 48);
                padding: .25rem .75rem;
                position: relative;
                text-decoration: none;
                border-radius: 4px;
                border-width: 1px;
                border-style: solid;
                border-color: rgb(230, 234, 241);
                border-image: initial;
            }} 
            #{button_id}:hover {{
                border-color: rgb(246, 51, 102);
                color: rgb(246, 51, 102);
            }}
            #{button_id}:active {{
                box-shadow: none;
                background-color: rgb(246, 51, 102);
                color: white;
                }}
        </style> """

    dl_link = (
        custom_css
        + f'<a download="{download_filename}" id="{button_id}" href="data:file/txt;base64,{b64}">{button_text}</a><br><br>'
    )
    # dl_link = f'<a download="{download_filename}" id="{button_id}" href="data:file/txt;base64,{b64}"><input type="button" kind="primary" value="{button_text}"></a><br></br>'

    st.markdown(dl_link, unsafe_allow_html=True)   

# Google Login

async def write_authorization_url(client,
                                  redirect_uri):
    authorization_url = await client.get_authorization_url(
        redirect_uri,
        scope=["profile", "email"],
        extras_params={"access_type": "offline"},
    )
    return authorization_url


async def write_access_token(client,
                             redirect_uri,
                             code):
    token = await client.get_access_token(code, redirect_uri)
    return token


async def get_email(client,
                    token):
    user_id, user_email = await client.get_id_email(token)
    return user_id, user_email

if __name__ == '__main__':
    client_id = st.secrets['client_id']
    client_secret = st.secrets['client_secret']
    redirect_uri = st.secrets['redirect_uri']

    client = GoogleOAuth2(client_id, client_secret)
    authorization_url = asyncio.run(
        write_authorization_url(client=client,
                                redirect_uri=redirect_uri)
    )
    print(authorization_url)
    if 'token' not in st.session_state:
        st.session_state.token=None

    if st.session_state.token is None:
        try:
            code = st.experimental_get_query_params()['code']
        except:
            st.write(f'''<h1>
                <a target="_blank"
                href="{authorization_url}">Login</a></h1>''',
                     unsafe_allow_html=True)
            # st.write(f"[Login]({authorization_url})")

        else:
            # Verify token is correct:
            try:
                token = asyncio.run(
                    write_access_token(client=client,
                                       redirect_uri=redirect_uri,
                                       code=code))
            except:
                st.write(f'''<h1>
                    This account is not allowed or page was refreshed.
                    Please try again: <a target="_blank"
                    href="{authorization_url}">Login</a></h1>''',
                         unsafe_allow_html=True)
            else:
                # Check if token has expired:
                if token.is_expired():
                    if token.is_expired():
                        st.write(f'''<h1>
                        Login session has ended: <a target="_blank" href="{authorization_url}">
                        Login</a></h1>
                        ''')
                else:
                    st.session_state.token = token
                    user_id, user_email = asyncio.run(
                        get_email(client=client,
                                  token=token['access_token'])
                    )
                    st.session_state.user_id = user_id
                    st.session_state.user_email = user_email
                    main(user_id=st.session_state.user_id,
                         user_email=st.session_state.user_email)
    else:
        main(user_id=st.session_state.user_id,
             user_email=st.session_state.user_email)



