#-*-coding:utf-8-*-
'''

RasterExpansion : The third algothrim
DataType : Raster

'''


import arcpy
import os
import numpy as np
import math
import sys
import matplotlib.pyplot as plt
import time
import zipfile


__version__ = '3.0'
__author__ = 'Li Yicong'
__affiliation__ = 'WHU'


class Raster(object):
    def __init__(self,workspace_path, road, lines, lines_level, areas, areas_level, max_level, weight_field, pt_path, output_path):
        self.workspace_path = workspace_path
        self.road = road
        self.lines = lines
        self.lines_level = lines_level
        self.output_path = output_path
        self.max_level = max_level
        self.weight_field = weight_field # the weight field--'weight'
        self.pt_path = pt_path
        self.areas = areas       
        self.areas_level = areas_level
        # Set the workspace
        arcpy.env.workspace = self.workspace_path
        # set the max iteration
        sys.setrecursionlimit(1000000000)

    def get_coord_pts(self):#get the coords of pts(float)
        desc = arcpy.Describe(self.pt_path)
        shapeField = desc.ShapeFieldName
        cursor = arcpy.SearchCursor(self.pt_path)
        coord_pts = []
        for row in cursor:
            pt_shape = row.getValue(shapeField).getPart(0)
            coord = [pt_shape.X,pt_shape.Y]
            coord_pts.append(coord)
        return coord_pts

    def shp_to_zip(self, path):
        shp_name = os.path.splitext(path)[0]
        zip_path = shp_name +'.zip'
        whole_path = self.workspace_path +'\\'+ zip_path
        if os.path.isfile(whole_path):
            print('Zip exists.Overwrite the original zip')
            os.remove(whole_path)
        azip = zipfile.ZipFile(whole_path, 'w')
        file_names = os.listdir(self.workspace_path)
        for file_name in file_names:
            if os.path.splitext(file_name)[0] == shp_name and os.path.splitext(file_name)[1] != '.zip':
                azip.write(self.workspace_path+'\\'+file_name,compress_type=zipfile.ZIP_DEFLATED)
        azip.close()
        print('Zip file to ' + whole_path)
        return whole_path
    
    def processing(self):
        coord_pts = self.get_coord_pts()
        out_arrays = self.get_area(coord_pts)
        # Choose the erase shp
        areas_erase = []
        for i,area_level in enumerate(self.areas_level):
            if area_level <= self.max_level:  # Notice <= means has the higher weight
                areas_erase.append(self.areas[i])
        areas_erase_path = 'areas_erase.shp'
        erase_output_path = 'erase_' + self.output_path + '.shp'
        if len(areas_erase) > 0:  # Erase
            if os.path.isfile(self.workspace_path +'\\'+areas_erase_path):
                arcpy.Delete_management(areas_erase_path)
            arcpy.Merge_management(areas_erase, areas_erase_path)
            if os.path.isfile(self.workspace_path +'\\'+erase_output_path):
                arcpy.Delete_management(self.workspace_path +'\\'+erase_output_path)
            arcpy.Erase_analysis(self.output_path+'.shp', areas_erase_path, erase_output_path)
            zip_path = self.shp_to_zip(erase_output_path)
            arcpy.Delete_management(erase_output_path)
            arcpy.Delete_management(areas_erase_path)
        else:
            zip_path = self.shp_to_zip(self.output_path)
        if os.path.isfile(self.workspace_path +'\\'+self.output_path+'.shp'):
            arcpy.Delete_management(self.output_path+'.shp')
        if os.path.isfile(self.workspace_path +'\\'+erase_output_path):
            arcpy.Delete_management(erase_output_path)
        print('Raster done...')
        return zip_path
        
    def get_area1d(self, row, col, array, in_array, row_max, col_max,k):#k to restrict recursion
        if (in_array[row][col] == 1 or array[row][col] == 1 or k >10000):#if the boundary or has been found
            array[row][col] = 1 # enlarge the results
            return
        else:#4-neighbour
            array[row][col] = 1
            k += 1
            if(row+1 < row_max):#up
                self.get_area1d(row+1, col, array, in_array, row_max, col_max,k)
            if(row-1 > 0):#down
                self.get_area1d(row-1, col, array, in_array, row_max, col_max,k)
            if(col+1 < col_max):#right
                self.get_area1d(row, col+1, array, in_array, row_max, col_max,k)
            if(col-1 > 0):#left
                self.get_area1d(row, col-1, array, in_array, row_max, col_max,k)
        
    def get_area1pt(self,row, col, in_array):
        array = np.zeros(in_array.shape)
        array[:] = 255#initial all to 255
        k = 0
        self.get_area1d(row, col, array, in_array, in_array.shape[0], in_array.shape[1],k)
        return array.astype(int)
    
    def get_area(self, coord_pts):
        sql = '"'+self.weight_field+'"' + '=' +"'"+str(self.max_level)+"'"
        print('Set weight...')
        for i,line in enumerate(self.lines):
            fields = arcpy.ListFields(line)
            field_names = []
            for field in fields:
                field_names.append(field.name)
            if self.weight_field not in field_names:
                arcpy.AddField_management(line,self.weight_field,'TEXT')  # Add the field 'weight'
            rows = arcpy.UpdateCursor(line)
            for row in rows:
                row.setValue(self.weight_field,str(self.lines_level[i]))  # Set the weight
                rows.updateRow(row)
        self.lines.append(self.road)
        if os.path.isfile(self.workspace_path + '\\'+'merge_all.shp'):
            arcpy.Delete_management(self.workspace_path + '\\'+'merge_all.shp')
        arcpy.Merge_management(self.lines, 'merge_all.shp')
        if os.path.exists(self.workspace_path +'\\'+self.output_path):
            arcpy.Delete_management(self.workspace_path +'\\'+self.output_path)
        temp_name = str(time.time())[:10]
        arcpy.MakeFeatureLayer_management('merge_all.shp', temp_name)
        arcpy.SelectLayerByAttribute_management(temp_name, 'NEW_SELECTION', sql)
        arcpy.FeatureToRaster_conversion(temp_name,self.weight_field,self.output_path)
        print('Searching by raster...')
        #get the propreties of raster
        x_size = float(str(arcpy.GetRasterProperties_management(self.output_path,'CELLSIZEX')))
        y_size = float(str(arcpy.GetRasterProperties_management(self.output_path,'CELLSIZEY')))
        top = float(str(arcpy.GetRasterProperties_management(self.output_path,'TOP')))
        bottom = float(str(arcpy.GetRasterProperties_management(self.output_path,'BOTTOM')))
        left = float(str(arcpy.GetRasterProperties_management(self.output_path,'LEFT')))
        right = float(str(arcpy.GetRasterProperties_management(self.output_path,'RIGHT')))
        #in raster.raster to ndarray
        in_array = arcpy.RasterToNumPyArray(self.output_path)
        #out ndarray.initial zeros
        out_arrays = []
        for coord_pt in coord_pts:
            #lng,lat to row,col
            if(coord_pt[0]<left or coord_pt[0]>right or coord_pt[1]<bottom or coord_pt[1]>top):
                print('Out of range.')
                continue
            #cal the row and col
            row = int(in_array.shape[0] - math.ceil((coord_pt[1] - bottom)/y_size))#notice
            col = int(math.ceil((coord_pt[0] - left)/x_size))
            out_array = self.get_area1pt(row, col, in_array)
            out_arrays.append(out_array)
        #out the raster
        shps_path = []
        for i,out_array in enumerate(out_arrays):        
            out_raster = arcpy.NumPyArrayToRaster(out_array, arcpy.Point(left, bottom), x_size, y_size,255)
            if os.path.isfile(self.workspace_path +'\\'+self.output_path+'_'+str(i)+'.shp'):
                arcpy.Delete_management(self.workspace_path +'\\'+self.output_path+'_'+str(i)+'.shp')
            arcpy.RasterToPolygon_conversion(out_raster, self.output_path+'_'+str(i)+'.shp', "SIMPLIFY", 'VALUE')
            shps_path.append(self.output_path+'_'+str(i)+'.shp')
            #out_raster.save(self.output_path+'_'+str(i)+'.tif')
        if os.path.isfile(self.workspace_path +'\\'+self.output_path+'.shp'):
            arcpy.Delete_management(self.workspace_path +'\\'+self.output_path+'.shp')
        arcpy.Union_analysis(shps_path, self.output_path)
        for shp_path in shps_path:
            arcpy.Delete_management(shp_path)
        arcpy.Delete_management('merge_all.shp')
        arcpy.Delete_management(self.output_path)#delete the raster
        return out_arrays   	
