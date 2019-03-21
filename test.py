#-*-coding:utf-8-*-
'''

A test.py

'''

import sys
import os
import arcpy
from extract import *

def test_expansion():
    # output shp
    output_path = 'extracted_1.shp'# output shp
    test = expansion.Expansion(workspace_path, road, lines, lines_level, areas, areas_level, max_level, weight_field, pt_path, output_path)
    zip_path = test.processing()

def test_frame():
    output_path = 'extracted_2.shp'# output shp
    test = frame.Frame(workspace_path, road, lines, lines_level, areas, areas_level, max_level, weight_field, pt_path, output_path)
    zip_path = test.processing()

def test_raster():
    output_path = 'extracted_3'# output shp, not contain .shp
    test = raster.Raster(workspace_path, road, lines, lines_level, areas, areas_level, max_level, weight_field, pt_path, output_path)
    zip_path = test.processing()
    
def test_poi_corrcet(extracted_area,poi_region,out_path):
    #arcpy.Intersect_analysis([extracted_area,poi_region], 'temp.shp')
    arcpy.MakeFeatureLayer_management(poi_region,'selected_area')
    arcpy.SelectLayerByLocation_management('selected_area','CROSSED_BY_THE_OUTLINE_OF',extracted_area)
    arcpy.Erase_analysis('selected_area', extracted_area, 'temp.shp')
    arcpy.Union_analysis([extracted_area,'temp.shp'],'temp_1.shp')
    arcpy.Dissolve_management('temp_1.shp','temp_2')
    if os.path.isfile(workspace_path +'\\'+out_path):
        print('File exists.Overwrite the original shp')
        arcpy.Delete_management(out_path)
    arcpy.Erase_analysis('temp_2.shp', '\\data\\waterregion.shp', out_path)
    arcpy.Delete_management('temp.shp')
    arcpy.Delete_management('temp_1.shp')
    arcpy.Delete_management('temp_2.shp')
    
if __name__ == '__main__':
    # set the max iteration
    sys.setrecursionlimit(10000000)
    # set the workspace
    workspace_path = 'C:\\Users\\LYC\\Desktop\\extract_v4\\test_data'
    arcpy.env.workspace = workspace_path
    # input shp
    road = 'road_test.shp'
    lines = []
    lines_level = []
    lines.append('waterline.shp')
    lines_level.append(1)
    areas = []
    areas_level = []
    areas.append('waterregion.shp')
    areas_level.append(1)
    pt_path = 'test_pts.shp'# the test pt shp
    # parameter
    max_level = 2# set the weight level
    weight_field = 'weight'#the name of weight field
    #First
    #test_expansion()
    #Second
    #test_frame()
    #Third
    test_raster()
