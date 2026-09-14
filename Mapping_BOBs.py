### Author: Elisabeth A. Maxwell
### Code written with suggestions from Claude.ai
### Original development: September 2026
### Purpose: This script creates .html maps and .gif plots for visualization of 
### Buoyant Observational Buoy (BOB) deployments.

### Import packages:
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from shapely.geometry import box
import requests
from PIL import Image
from io import BytesIO
from pyproj import Transformer

### Set your variables:
## Path to csv that contains buoy data:
CSV_PATH = "C:\\Users\\elisabeth.maxwell\\Data\\buoy_report_20260911T005156.csv"
## Path to shapefile that you want to use for map:
COASTLINE_PATH = "C:\\Users\\elisabeth.maxwell\\Data\\extractedData_COASTAL\\Coastal_Coastline_line.shp"
## Select the columns that you want to include (BlueOceanGear reports contain more than we need here)
## Current script does not use all of these columns, but these might be relevant in the future
COLUMNS = ["Decode ID", "Device ID", "Transmit Date", "Status", "Latitude (deg)", 
           "Longitude (deg)", "Position Delta (meters)", "Velocity (knots)", "SOC (%)", 
           "Water Temperature (°C)", "Accel Mean (g)", "Accel Max (g)"]
## Set the Device ID (aka SN) for the buoys and set the start/end of deployment period:
# Deployment #1: 'start': '2026-08-11 12:00:00', 'end': '2026-08-12 12:00:00'
# Deployment #2: 'start': '2026-08-21 13:00:00', 'end': '2026-08-27 12:00:00'
DEVICES = {
    'bobs_1': {'id': 2345, 'start': '2026-08-11 12:00:00', 'end': '2026-08-12 12:00:00'},
    'bobs_2': {'id': 2346, 'start': '2026-08-11 12:00:00', 'end': '2026-08-12 12:00:00'},
    'bobs_3': {'id': 2350, 'start': '2026-08-11 12:00:00', 'end': '2026-08-12 12:00:00'},
}

## Color code the BOBs. This is used in the combined GIF below. White seems to work well on top of the orthoimagery layer.
COLORS = {
    'bobs_1': 'white',
    'bobs_2': 'white',
    'bobs_3': 'white'
}
## Define the bounding box for the map extent
WEST, SOUTH, EAST, NORTH = -69.55, 44.03, -69.50, 44.07

### Load BOB data and process
bobs_df = pd.read_csv(CSV_PATH)
## Convert Transmit Date to datetime so it can be filtered and sorted
bobs_df['Transmit Date'] = pd.to_datetime(bobs_df['Transmit Date'])

def process_bob(df, device_id, start=None, end=None):
        ###
        #    Filter, clean, and convert BOB data to a GeoDataFrame.
        #    Parameters:
        #        df          : full BOB dataframe loaded from CSV
        #        device_id   : integer Device ID (aka SN) of the buoy
        #        start       : start datetime string for filtering (optional)
        #        end         : end datetime string for filtering (optional)
        #    Returns:
        #        GeoDataFrame with point geometry in EPSG:4326
        ###
    mask = df['Device ID'] == device_id
    if start:
        mask &= df['Transmit Date'] >= start
    if end:
        mask &= df['Transmit Date'] <= end
    
    filtered = (df[mask] ## Necessary bc some cells might be blank
        .copy()
        .replace('', float('nan'))
        .dropna(subset=['Longitude (deg)', 'Latitude (deg)']) 
        [COLUMNS]
    )

    ## Need the BOB data returned as a GeoDataFrame so it can be mapped
    return gpd.GeoDataFrame( 
        filtered,
        geometry=gpd.points_from_xy(filtered['Longitude (deg)'], filtered['Latitude (deg)']),
        crs="EPSG:4326"  ## Standard WGS84 coordinate reference system
    )

## Apply process_bob() to each device in DEVICES and store results in a dictionary
gdfs = {name: process_bob(bobs_df, info['id'], info['start'], info['end']) 
        for name, info in DEVICES.items()}

### Save the individual interactive maps of the BOB deployment (open .html file in browser):
for name, gdf in gdfs.items():
    gdf.explore().save(f"map_{name}.html")

### Read in the shapefile for the coastline and clip to the area of interest
midcoast_maine = gpd.read_file(COASTLINE_PATH)
## Pre-filter to areas west of -69.4 longitude before clipping for efficiency
dre = midcoast_maine.cx[:-69.4, :]
## Create bounding box polygon and clip the coastline to it
bbox = gpd.GeoDataFrame(geometry=[box(WEST, SOUTH, EAST, NORTH)], crs="EPSG:4326")
clipped = gpd.clip(dre, bbox).to_crs("EPSG:26919")  ## Reproject to UTM to match orthoimagery


### Call orthoimagery from Maine GIS ImageServer:
## The service is in EPSG:26919 (UTM Zone 19N), so we need to reproject our bounding box
transformer = Transformer.from_crs("EPSG:4326", "EPSG:26919", always_xy=True)
WEST_UTM, SOUTH_UTM = transformer.transform(WEST, SOUTH)
EAST_UTM, NORTH_UTM = transformer.transform(EAST, NORTH)

## Build the export URL using our bounding box in the service's native CRS
ORTHO_URL = (
    "https://gis.maine.gov/image/rest/services/Coastal/orthoCoastalMidcoast2023/ImageServer/exportImage"
    f"?bbox={WEST_UTM},{SOUTH_UTM},{EAST_UTM},{NORTH_UTM}"
    "&bboxSR=26919"
    "&imageSR=26919"      ## Keep in native CRS
    "&size=1000,1000"     ## Pixel dimensions of the returned image
    "&format=png"
    "&f=image"
)

## Fetch and load the image once, outside the animation loop
response = requests.get(ORTHO_URL)
ortho_img = Image.open(BytesIO(response.content))


### Create a GIF figure for 1 BOB:
# Select which BOB to plot
SINGLE_BOB = 'bobs_1'
## Reproject to UTM to match orthoimagery
single_gdf = gdfs[SINGLE_BOB].to_crs("EPSG:26919").sort_values('Transmit Date')
fig, ax = plt.subplots(figsize=(10, 8))

def update_single(frame):
    ax.clear()
    ## Plot orthoimagery as the base layer, positioned using our lat/lon bounding box
    ax.imshow(ortho_img, extent=[WEST_UTM, EAST_UTM, SOUTH_UTM, NORTH_UTM], aspect='auto', zorder=0)
    #clipped.plot(ax=ax, color='black', linewidth=1) ##This is the coastal shapefile. Comment out if you don't want it displayed on gif
    single_gdf.iloc[:frame+1].plot(ax=ax, color=COLORS[SINGLE_BOB], markersize=5, zorder=2) ## Tracks so far
    single_gdf.iloc[[frame]].plot(ax=ax, color='yellow', markersize=10, marker='o', zorder=3) ## Current position
    ax.set_title(f"Transmit Date: {single_gdf.iloc[frame]['Transmit Date']}", pad=20)
    ax.text(0.5, 1.02, "Deployment #1", transform=ax.transAxes,ha='center', fontsize=10, color='black')
    ax.set_xlim(WEST_UTM, EAST_UTM)
    ax.set_ylim(SOUTH_UTM, NORTH_UTM)

ani_single = animation.FuncAnimation(fig, update_single, frames=len(single_gdf), interval=200)
## fps controls playback speed; increase to speed up the animation
ani_single.save(f"{SINGLE_BOB}_deploy1.gif", writer="pillow", fps=5)
plt.close()

### Create a GIF for all of the BOBs on one figure:
## Match CRS to coastline and sort each GDF chronologically
bob_gdfs = {name: gdf.to_crs("EPSG:26919").sort_values('Transmit Date')
            for name, gdf in gdfs.items()}

fig, ax = plt.subplots(figsize=(10, 8))

def update_all(frame):
    ##Draw one frame of the all-BOBs animation. Called once per frame by FuncAnimation.
    ax.clear()
    ## Plot orthoimagery as the base layer, positioned using our lat/lon bounding box
    ax.imshow(ortho_img, extent=[WEST_UTM, EAST_UTM, SOUTH_UTM, NORTH_UTM], aspect='auto', zorder=0)
    #clipped.plot(ax=ax, color='black', linewidth=1, zorder=1) ##This is the coastal shapefile. Comment out if you don't want it displayed on gif
    
    for name, gdf in bob_gdfs.items():
        # Plot up to current frame, or all points if frame exceeds this BOB's length
        plot_frame = min(frame, len(gdf) - 1)
        gdf.iloc[:plot_frame+1].plot(ax=ax, color=COLORS[name], markersize=5, label=name, zorder=2) ## Tracks so far
        gdf.iloc[[plot_frame]].plot(ax=ax, color='yellow', markersize=10, marker='o', zorder=3) ## Current track

    ## Use the longest track as the reference for the timestamp
    ref_gdf = max(bob_gdfs.values(), key=len)
    ax.set_title(f"Transmit Date: {ref_gdf.iloc[min(frame, len(ref_gdf)-1)]['Transmit Date']}", pad=20)
    ax.text(0.5, 1.02, "Deployment #1", transform=ax.transAxes,ha='center', fontsize=10, color='black')
    ax.legend(loc='upper left')
    ax.set_xlim(WEST_UTM, EAST_UTM)
    ax.set_ylim(SOUTH_UTM, NORTH_UTM)

## Run the animation until the longest track is complete
max_frames = max(len(gdf) for gdf in bob_gdfs.values())

ani_all = animation.FuncAnimation(fig, update_all, frames=max_frames, interval=200)
ani_all.save("bobs_allbuoys_deploy1.gif", writer="pillow", fps=5)
plt.close()