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
DEVICES = {
    'bobs_1': {'id': 2345, 'start': '2026-08-11 12:00:00', 'end': '2026-08-12 12:00:00'},
    'bobs_2': {'id': 2346, 'start': '2026-08-11 12:00:00', 'end': '2026-08-12 12:00:00'},
    'bobs_3': {'id': 2350, 'start': '2026-08-11 12:00:00', 'end': '2026-08-12 12:00:00'},
}
## Color code the BOBs. This is used in the combined GIF below
COLORS = {
    'bobs_1': 'blue',
    'bobs_2': 'green',
    'bobs_3': 'purple'
}
## Define the bounding box for the map extent
west, south, east, north = -69.55, 44.03, -69.50, 44.07

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
bbox = gpd.GeoDataFrame(geometry=[box(west, south, east, north)], crs=dre.crs)
clipped = gpd.clip(dre, bbox)

### Create a GIF figure for 1 BOB:
# Select which BOB to plot
SINGLE_BOB = 'bobs_1'
## Match CRS to coastline and sort chronologically
single_gdf = gdfs[SINGLE_BOB].to_crs(clipped.crs).sort_values('Transmit Date')
fig, ax = plt.subplots(figsize=(10, 8))

def update_single(frame):
    ax.clear()
    clipped.plot(ax=ax, color='black', linewidth=1)
    single_gdf.iloc[:frame+1].plot(ax=ax, color=COLORS[SINGLE_BOB], markersize=5)
    single_gdf.iloc[[frame]].plot(ax=ax, color='red', markersize=10, marker='*')
    ax.set_title(f"Transmit Date: {single_gdf.iloc[frame]['Transmit Date']}")
    ax.set_xlim(west, east)
    ax.set_ylim(south, north)

ani_single = animation.FuncAnimation(fig, update_single, frames=len(single_gdf), interval=200)
## fps controls playback speed; increase to speed up the animation
ani_single.save(f"{SINGLE_BOB}_track.gif", writer="pillow", fps=5)
plt.close()

### Create a GIF for all of the BOBs on one figure:
## Match CRS to coastline and sort each GDF chronologically
bob_gdfs = {name: gdf.to_crs(clipped.crs).sort_values('Transmit Date') 
            for name, gdf in gdfs.items()}

fig, ax = plt.subplots(figsize=(10, 8))

def update_all(frame):
    ##Draw one frame of the all-BOBs animation. Called once per frame by FuncAnimation.
    ax.clear()
    clipped.plot(ax=ax, color='black', linewidth=1) ## Coastline base layer
    
    for name, gdf in bob_gdfs.items():
        if frame < len(gdf):  ## Skip if this BOB has fewer frames than the longest track
            gdf.iloc[:frame+1].plot(ax=ax, color=COLORS[name], markersize=5, label=name) ## Track so far
            gdf.iloc[[frame]].plot(ax=ax, color=COLORS[name], markersize=10, marker='*') ## Current position

    ## Use the longest track as the reference for the timestamp
    ref_gdf = max(bob_gdfs.values(), key=len)
    ax.set_title(f"Transmit Date: {ref_gdf.iloc[min(frame, len(ref_gdf)-1)]['Transmit Date']}")
    ax.legend(loc='upper left')
    ax.set_xlim(west, east) ## Lock extent so map doesn't rescale between frames
    ax.set_ylim(south, north)

## Run the animation until the longest track is complete
max_frames = max(len(gdf) for gdf in bob_gdfs.values())

ani_all = animation.FuncAnimation(fig, update_all, frames=max_frames, interval=200)
ani_all.save("bobs_track_all.gif", writer="pillow", fps=5)
plt.close()