#-*-coding:utf-8-*-
'''

Frame : The second algorithm

'''

import arcpy
import os
import time
import zipfile

__version__ = '3.0'
__author__ = 'Li Yicong'
__affiliation__ = 'WHU'


class Frame(object):
    def __init__(self, workspace_path, road, lines, lines_level, areas, areas_level, max_level, weight_field, pt_path, output_path):
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

    def make_pg(self):
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
        print('Make polygons...')
        all_attr = []#all the attributes of attr
        pg_frames = []#the name list of output polygon
        for l in arcpy.da.SearchCursor('merge_all.shp', self.weight_field):
            all_attr.append(str(l[0]))
        unique_attr = set(all_attr)#unique attributes of attr
        #make polygon according to attr
        for a in unique_attr:
            if a >= self.max_level:
                temp_name = str(time.time())
                sql = '"'+self.weight_field+'"' + '=' +"'"+str(a)+"'"+' OR '+ '"'+self.weight_field+'"'+ '=' + "'"+str(self.max_level)+"'"#notice choose current line and the max level line together
                selected_feature = str(a)+'_'+temp_name[:10] 
                pg_frames.append(selected_feature)
                arcpy.MakeFeatureLayer_management('merge_all.shp', selected_feature)
                #selcet the attr to make the polygon
                arcpy.SelectLayerByAttribute_management(selected_feature, 'NEW_SELECTION', sql)
                arcpy.FeatureToPolygon_management(selected_feature,selected_feature)
        arcpy.Delete_management('merge_all.shp')
        return pg_frames             

    def get_pg(self, pg_frames):
        pg_frames_select = []
        for i,pg_frame in enumerate(pg_frames):
            seleted_area = str(i)+'s_' + str(time.time())[:10]
            pg_frames_select.append(seleted_area+'.shp')
            arcpy.MakeFeatureLayer_management(pg_frame + '.shp',seleted_area)
            arcpy.SelectLayerByLocation_management(seleted_area,'COMPLETELY_CONTAINS',self.pt_path)
            arcpy.CopyFeatures_management(seleted_area,seleted_area)
            arcpy.Delete_management(pg_frame+'.shp')
        if os.path.isfile(self.workspace_path +'\\'+self.output_path):
            arcpy.Delete_management(self.workspace_path +'\\'+self.output_path)
        arcpy.Union_analysis(pg_frames_select, self.output_path)
        for pg_frame_select in pg_frames_select:
            arcpy.Delete_management(pg_frame_select) 
        return pg_frames_select

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
        pg_frames = self.make_pg()
        self.get_pg(pg_frames)
        # Choose the erase shp
        areas_erase = []
        for i,area_level in enumerate(self.areas_level):
            if area_level <= self.max_level:  # Notice <= means has the higher weight
                areas_erase.append(self.areas[i])
        areas_erase_path = 'areas_erase.shp'
        erase_output_path = 'erase_' + self.output_path
        if len(areas_erase) > 0:  # Erase
            if os.path.isfile(self.workspace_path +'\\'+areas_erase_path):
                arcpy.Delete_management(areas_erase_path)
            arcpy.Merge_management(areas_erase, areas_erase_path)
            if os.path.isfile(self.workspace_path +'\\'+erase_output_path):
                arcpy.Delete_management(self.workspace_path +'\\'+erase_output_path)
            arcpy.Erase_analysis(self.output_path, areas_erase_path, erase_output_path)
            zip_path = self.shp_to_zip(erase_output_path)
            arcpy.Delete_management(erase_output_path)
            arcpy.Delete_management(areas_erase_path)
        else:
            zip_path = self.shp_to_zip(self.output_path)
        arcpy.Delete_management(self.output_path)
        print('Frame done...')
        return zip_path


    
    	
