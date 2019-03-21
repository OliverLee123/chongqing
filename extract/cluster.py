#-*-coding:utf-8-*-
'''

A script to change pois to poi_clusters
DBSCAN: https://www.cnblogs.com/tiaozistudy/p/dbscan_algorithm.html

'''


import numpy as np
import math
import random
from scipy.spatial import KDTree
import arcpy
import sys
import time


__version__ = '1.5'
__author__ = 'Yicong Li'


class visitlist(object):
    def __init__(self, count=0):#correct
        self.unvisitedlist=[i for i in range(count)]# unvisitedlist记录未访问过的点
        self.visitedlist=list()# visitlist类用于记录访问列表
        self.unvisitednum=count# unvisitednum记录访问过的点数量

    def visit(self, pointId):
        self.visitedlist.append(pointId)# visitedlist记录已访问过的点
        self.unvisitedlist.remove(pointId)
        self.unvisitednum -= 1


def dbscan(dataSet, eps, minPts):
    nPoints = dataSet.shape[0]
    vPoints = visitlist(count=nPoints)
    k = -1
    C = [-1 for i in range(nPoints)]
    kd = KDTree(dataSet)#corrcet X->dataSet
    while(vPoints.unvisitednum>0):
        p = random.choice(vPoints.unvisitedlist)
        vPoints.visit(p)
        N = kd.query_ball_point(dataSet[p], eps)
        if len(N) >= minPts:
            k += 1
            C[p] = k
            for p1 in N:
                if p1 in vPoints.unvisitedlist:
                    vPoints.visit(p1)
                    M = kd.query_ball_point(dataSet[p1], eps)
                    if len(M) >= minPts:
                        for i in M:
                            if i not in N:
                                N.append(i)
                    if C[p1] == -1:
                        C[p1] = k
        else:
            C[p] = -1#corrcet p1->p
    return C

def poi_cluster(poi_path, out_path):
    desc = arcpy.Describe(poi_path)
    shapeField = desc.ShapeFieldName
    rows = arcpy.SearchCursor(poi_path)
    level_types = []
    out_data = []
    for row in rows:#can't find a good way to get the unique value
        l = row.getValue('poilevelid')
        level_types.append(str(l))
    level_types = set(level_types)
    max_flag = 0#the range of the cluster
    for level_type in level_types:
        print(level_type)
        temp = 'poi' + level_type
        sql = '"poilevelid" = '+level_type
        arcpy.MakeFeatureLayer_management(poi_path, temp)
        arcpy.SelectLayerByAttribute_management(temp, 'NEW_SELECTION', sql)
        scs = arcpy.SearchCursor(temp)
        data = []#store the x and y
        level = []#store the level of poi
        for sc in scs:
            shape = sc.getValue(shapeField)
            point = shape.getPart(0)
            l = sc.getValue('poilevelid')
            level.append(l)
            data.append([point.X,point.Y])
        data = np.array(data, dtype = float)
        #DBSCAN to cluster
        C = dbscan(data, 0.001, 10)#100 Meters search radius
        for i in range(data.shape[0]):
            if C[i] >= 0:
                out_data.append([data[i][0],data[i][1],C[i]+max_flag,level[i]])
        max_flag = max_flag + max(C) + 1
    #write the results
    sr = arcpy.SpatialReference(4326)
    fc = arcpy.CreateFeatureclass_management(workspace_path,out_path, "POINT", "", "","", sr)
    arcpy.AddField_management(out_path, "cluster", "TEXT")
    arcpy.AddField_management(out_path, "poilevelid", "TEXT")
    cursor = arcpy.InsertCursor(fc)
    for i in range(len(out_data)):
        feature = cursor.newRow()
        vertex = arcpy.CreateObject("Point")
        vertex.X = out_data[i][0]
        vertex.Y = out_data[i][1]
        feature.shape = vertex
        # Add attributes
        feature.cluster = str(out_data[i][2])
        feature.poilevelid = str(out_data[i][3])
        # write to shapefile
        cursor.insertRow(feature)
    del cursor
    del fc

def cluster_centroid_radius(cluster):#2-d point
    cen =  np.mean(cluster, axis=0)
    rad = cluster - cen
    radius = max(np.sqrt(rad[:,0]*rad[:,0] + rad[:,1]*rad[:,1]))#the furthest distance away from the centroid as the radius
    return [cen,radius]


def cluster_to_polygon(poi_cluster,out_path):
    desc = arcpy.Describe(poi_cluster)
    shapeField = desc.ShapeFieldName
    rows = arcpy.SearchCursor(poi_cluster)
    level_types = []
    out_data = []
    for row in rows:#can't find a good way to get the unique value
        l = row.getValue('poilevelid')
        level_types.append(str(l))
    level_types = set(level_types)
    for level_type in level_types:
        temp_level = 'poi_cluster_' + level_type
        sql_level = '"poilevelid" = ' + "'" +level_type+"'"
        arcpy.MakeFeatureLayer_management(poi_cluster, temp_level)
        arcpy.SelectLayerByAttribute_management(temp_level, 'NEW_SELECTION', sql_level)
        scs = arcpy.SearchCursor(temp_level)
        cluster_types = []
        for sc in scs:
            c = sc.getValue('cluster')
            cluster_types.append(str(c))
        cluster_types = set(cluster_types)
        for cluster_type in cluster_types:
            temp_cluster = 'poi_cluster_' + level_type+'_'+cluster_type
            data = []
            sql_cluster = '"poilevelid" = '+"'" +level_type+"'"  +' AND ' + '"cluster" = '+ "'" +cluster_type+"'"
            print(sql_cluster)
            arcpy.MakeFeatureLayer_management(poi_cluster, temp_cluster)
            arcpy.SelectLayerByAttribute_management(temp_cluster, 'NEW_SELECTION', sql_cluster)
            scs = arcpy.SearchCursor(temp_cluster)
            for sc in scs:
                shape = sc.getValue(shapeField)
                point = shape.getPart(0)
                data.append([point.X,point.Y])
            data = np.array(data, dtype = float)#2-d point
            [cen,rad] = cluster_centroid_radius(data)
            if(rad > 0):
                out_data.append([cen[0],cen[1],rad*1.5*10000,cluster_type,level_type])#rad*10000 to Meters
                print(level_type,cluster_type,cen[0],cen[1],rad)
    #write the results
    sr = arcpy.SpatialReference(4326)
    fc = arcpy.CreateFeatureclass_management(workspace_path,'poi_test_cluster_cen.shp', "POINT", "", "","", sr)
    arcpy.AddField_management('poi_test_cluster_cen.shp', "bufdis", "TEXT")
    arcpy.AddField_management('poi_test_cluster_cen.shp', "cluster", "TEXT")
    arcpy.AddField_management('poi_test_cluster_cen.shp', "poilevelid", "TEXT")
    cursor = arcpy.InsertCursor(fc)
    for i in range(len(out_data)):
        feature = cursor.newRow()
        vertex = arcpy.CreateObject("Point")
        vertex.X = out_data[i][0]
        vertex.Y = out_data[i][1]
        feature.shape = vertex
        # Add attributes
        feature.bufdis = str(out_data[i][2]) 
        feature.cluster = str(out_data[i][3])
        feature.poilevelid = str(out_data[i][4])
        # write to shapefile
        cursor.insertRow(feature)
    del cursor
    del fc
    arcpy.Buffer_analysis('poi_test_cluster_cen.shp', out_path, 'bufdis')
    arcpy.Delete_management('poi_test_cluster_cen.shp')

if __name__ == '__main__':
    print(time.asctime(time.localtime(time.time())))
    sys.setrecursionlimit(10000000)
    workspace_path = 'C:\\Users\\LYC\\Desktop\\extract_v3\\expansion_3'
    arcpy.env.workspace = workspace_path
    #poi_cluster('data\\poi_test.shp','data\\poi_test_cluster.shp')
    cluster_to_polygon('data\\poi_test_cluster.shp','poi_test_region.shp')
    print('Done')
    print(time.asctime(time.localtime(time.time())))
