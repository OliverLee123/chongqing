# -*-coding:utf-8-*-
'''

expansion : The first algorithm

'''

import arcpy
import os
import numpy as np
import zipfile
import time


__version__ = '3.0'
__author__ = 'Li Yicong'
__affiliation__ = 'WHU'


class Expansion(object):
    # Shp generated during processing
    __arc_path = 'Arc_Join.shp'  # The arc shp that contains lane
    __area_path = 'Polygon.shp'  # The polygon for exacting

    def __init__(self, workspace_path, road, lines, lines_level, areas, areas_level, max_level, weight_field, pt_path, output_path):
        self.workspace_path = workspace_path
        self.road = road
        self.lines = lines
        self.lines_level = lines_level
        self.output_path = output_path
        self.max_level = max_level
        self.weight = weight_field # the weight field--'weight'
        self.pt_path = pt_path
        self.areas = areas       
        self.areas_level = areas_level
        self.coverage_folder = self.workspace_path + '\\coverage'  # Coverage generated during processing
        # Set the workspace
        arcpy.env.workspace = self.workspace_path

    def pre_processing(self):
        print('Pre-processing...')
        for i,line in enumerate(self.lines):
            fields = arcpy.ListFields(line)
            field_names = []
            for field in fields:
                field_names.append(field.name)
            if self.weight not in field_names:
                arcpy.AddField_management(line,self.weight,'TEXT')  # Add the field 'weight'
            rows = arcpy.UpdateCursor(line)
            for row in rows:
                row.setValue(self.weight,str(self.lines_level[i]))  # Set the weight
                rows.updateRow(row)
        self.lines.append(self.road)
        if not os.path.isfile(self.workspace_path + '\\'+'merge_all.shp'):
            arcpy.Merge_management(self.lines, 'merge_all.shp')
        if not os.path.isfile(self.workspace_path +'\\'+'streets_polygon.shp'):  # Roads: lines to polygons 
            arcpy.FeatureToPolygon_management('merge_all.shp', 'streets_polygon.shp')
        if not os.path.exists(self.coverage_folder):  # Roads: poltgons to coverage to get topo
            arcpy.FeatureclassToCoverage_conversion([['streets_polygon.shp','POLYGON']],self.coverage_folder)
        if not os.path.isfile(self.workspace_path + '\\' + 'arc.shp'):  # To get topo
            arcpy.FeatureClassToFeatureClass_conversion(self.coverage_folder + '\\arc', self.workspace_path, 'arc')
        if not os.path.isfile(self.workspace_path + '\\'+self.__area_path):  # Coverage to polygons
            arcpy.FeatureClassToFeatureClass_conversion(self.coverage_folder + '\\polygon', self.workspace_path, self.__area_path)
        if not os.path.isfile(self.workspace_path + '\\'+self.__arc_path):
            # Create field mappings
            # Get weights for arc
            fld_mappings = arcpy.FieldMappings()
            fld_mappings.addTable('arc.shp')
            fld_map = arcpy.FieldMap()
            fld_map.addInputField('merge_all.shp',self.weight)
            fld_mappings.addFieldMap(fld_map)
            # Spatial join to get the weights
            arcpy.SpatialJoin_analysis('arc.shp', 'merge_all.shp', self.__arc_path, 
            	'JOIN_ONE_TO_ONE', 'KEEP_ALL', fld_mappings, 'CLOSEST')
        arcpy.Delete_management('arc.shp')
        arcpy.Delete_management('merge_all.shp')
        arcpy.Delete_management('streets_polygon.shp')
        print('Pre-processing done...')

    def create_topo(self):
        # Make sure the field's name are right(leftPG, rightPG and weights)
        # Different version of arcgis causes different field's name
        fields_array = ['F_LEFTPOLY','F_RIGHTPOL',self.weight]
        arc_count = int((arcpy.GetCount_management(self.__arc_path)).getOutput(0))
        area_count = int((arcpy.GetCount_management(self.__area_path)).getOutput(0))
        pg_pl_topo = []  # Polylines that a polygon contains
        pl_pg_topo = []  # The left and right polygon that a polyline has
        pl_pg_topo.append([-1,-1])  # Arc index starts from 1
        # Init pl to pg topo and pg to pl topo,notice the index of area statrs from 2.so init 0 and 1 with empty
        for i in range(0,area_count+2):
            pg_pl_topo.append([])
        arc_index = 0
        for topo in arcpy.da.SearchCursor(self.__arc_path, fields_array):
            # Arc index starts from 1
            arc_index = arc_index + 1
            l = int(topo[0])  # The index of the left polygon
            r = int(topo[1])  # The index of the right polygon
            pl_pg_topo.append([l,r])  # Create pl_pg_topo
            if(topo[2] == ' '):
                lane = 999  # Default to maximum weight
            else:
                lane = int(topo[2])
            if l > 1 and [arc_index,lane] not in pg_pl_topo[l]:
                pg_pl_topo[l].append([arc_index,lane])
            if r > 1 and [arc_index,lane] not in pg_pl_topo[r]:
                pg_pl_topo[r].append([arc_index,lane])
        return arc_count,area_count,pg_pl_topo,pl_pg_topo

    def get_func_area1r(self,pg_pl_topo, pl_pg_topo, area_id, area_type_id, func_area_pgs, arc_search_flag, area_search_flag):
        for arc in pg_pl_topo[area_id]:
            # Notice the dirction of the inequlity.weight 1,2,3..weight 3,2,1
            if arc_search_flag[arc[0]] < 1 and arc[1] > self.max_level:  # If an arc hasn't chosen and the lane-level satisfying
                arc_search_flag[arc[0]] = 1  # Set this arc chosen
                search = 0
                if(pl_pg_topo[arc[0]][0] == area_id):  # Choose another side of polyline for searching
                    search = pl_pg_topo[arc[0]][1]
                else:
                    search = pl_pg_topo[arc[0]][0]
                # If search < 2 or area_search_flag[search] > 0:# if get the border then return
                if search < 2:
                    return
                if area_search_flag[search] < 1:
                    func_area_pgs.append([search, area_type_id])
                area_search_flag[search] = 1
                self.get_func_area1r(pg_pl_topo,pl_pg_topo,search,area_type_id,func_area_pgs,arc_search_flag,area_search_flag)
                
    def get_func_area(self, pg_pl_topo, pl_pg_topo, arc_count, area_count):
        print('Extracting area...')
        func_area_pgs = []  # The result polygon
        whole_pgs = []  # The whole origin polygon
        # Notice id starts from 2
        whole_pgs.append([])
        whole_pgs.append([])
        # Store the whole area that not seleted
        field_obs = arcpy.ListFields(self.__area_path)
        fields = []
        for field in field_obs:
            fields.append(field.name)
        fields[1] += '@'  # Get the PolygonGeometry
        for r in arcpy.da.SearchCursor(self.__area_path, fields):
            whole_pgs.append(r)
        # Get origin seleted area that contains pt
        temp_name = str(time.time())  # Use current time as the temp shp to avoid duplication 
        arcpy.MakeFeatureLayer_management(self.__area_path,temp_name)
        arcpy.SelectLayerByLocation_management(temp_name,'COMPLETELY_CONTAINS',self.pt_path)
        # Output result that have not been merged
        if os.path.isfile(self.workspace_path +'\\'+self.output_path):
            print('File exists.Overwrite the original shp')
            arcpy.Delete_management(self.output_path)
        arcpy.CopyFeatures_management(temp_name,self.output_path)
        # Because the default area_id equals to 0.so update the area id of the result set
        area_flag = 1  # Cluster id starts from 1 
        with arcpy.da.UpdateCursor(self.output_path,'id') as cursor:
            for row in cursor:
                row[0] = area_flag
                cursor.updateRow(row)
                area_flag += 1
        # Iteration to get the whole area
        # Make sure the attribute
        for r in arcpy.da.SearchCursor(self.output_path, ['COVERAGE_','ID']):
            area_search_id = int(r[0])
            area_type_id = int(r[1])
            arc_search_flag = np.zeros(arc_count+1)  # 0 means haven't chosen in an epoch
            area_search_flag = np.zeros(area_count+2)  # 0 means haven't chosen in an epoch
            self.get_func_area1r(pg_pl_topo, pl_pg_topo, area_search_id, area_type_id, func_area_pgs, arc_search_flag, area_search_flag)
        # Insert the result
        total = len(func_area_pgs)
        total_per = [int(x*total/10) for x in range(1,10,1)]  # A trick to cal the progress
        count = 0.
        for f in func_area_pgs:
            count += 1
            if count in total_per:
                print('Extracted areas : '+str(round(count/total*100)) + '%')  # Show the progress
            area_id = int(f[0])
            area_type_id = int(f[1])
            ic = arcpy.da.InsertCursor(self.output_path,fields)
            whole_pgs[area_id] = list(whole_pgs[area_id])
            whole_pgs[area_id][len(whole_pgs[area_id])-1] = area_type_id  # Replace the area id because the default area id is o
            ic.insertRow(whole_pgs[area_id])
            del ic
        print('Extract area done...')
        return func_area_pgs

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
        self.pre_processing()
        arc_count,area_count,pg_pl_topo,pl_pg_topo = self.create_topo()
        func_area_pgs = self.get_func_area(pg_pl_topo,pl_pg_topo,arc_count,area_count)
        # Dissolve
        dissolve_output_path = 'dissolve_' + self.output_path
        if os.path.isfile(self.workspace_path +'\\'+dissolve_output_path):
            arcpy.Delete_management(self.workspace_path +'\\'+dissolve_output_path)
        arcpy.Dissolve_management(self.output_path,dissolve_output_path,'id')
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
            arcpy.Erase_analysis(dissolve_output_path, areas_erase_path, erase_output_path)
            zip_path = self.shp_to_zip(erase_output_path)
        else:
            zip_path = self.shp_to_zip(dissolve_output_path)
        # Delete process results
        if os.path.isfile(self.workspace_path +'\\'+areas_erase_path):
            arcpy.Delete_management(areas_erase_path)
        arcpy.Delete_management(self.__arc_path)
        arcpy.Delete_management(self.__area_path)
        arcpy.Delete_management(self.coverage_folder)
        arcpy.Delete_management(self.output_path)
        if os.path.isfile(self.workspace_path +'\\'+erase_output_path):
            arcpy.Delete_management(erase_output_path)
        arcpy.Delete_management(dissolve_output_path)
        print('Expansion done...')
        return zip_path
