# spark-submit kmeans.py data/iris_small.dat 4 10

# imports
import numpy
import datetime
import random
import sys

from pyspark.mllib.random import RandomRDDs
from pyspark import SparkContext
import matplotlib.pyplot as plt

# methods
def customSplit(row):
    values = row[0]
    index = row[1]
    dataItems = values.split(',')
    for i in range(len(dataItems) - 1):
        dataItems[i] = float(dataItems[i])
    return (index, dataItems)

def loadData(path):
    dataFromText = sc.textFile(path)
    data = dataFromText.filter(lambda x: x is not None).filter(lambda x: x != "")
    dataZipped = data.zipWithIndex()
    return dataZipped.map(lambda x: customSplit(x))

#Random is not efficient!
def initCentroidsRandom(data, numClusters):
    sample = sc.parallelize(data.takeSample(False, numClusters))
    centroids = sample.map(lambda point : point[1][:-1])
    return centroids.zipWithIndex().map(lambda point : (point[1], point[0]))

def initCentroids(data, numClusters):
    sample = sc.parallelize(data.takeSample(False, numClusters))
    centroids = sample.map(lambda point : point[1][:-1])
    return centroids.zipWithIndex().map(lambda point : (point[1], point[0]))

def assignToCluster(data, centroids): 
    cartesianData = centroids.cartesian(data)
    cartesianDataDistances = cartesianData.map(lambda (centroid, dataPoint): calculateDistance(centroid, dataPoint))
    dataMinDistance = cartesianDataDistances.groupByKey().map(lambda x: (x[0], list(x[1]))).map(lambda row: minDist(row))
    return dataMinDistance

def calculateDistance(centroid, dataPoint):
    list1 = centroid[1]
    list2 = dataPoint[1][:-1]
    array1 = numpy.array(list1)
    array2 = numpy.array(list2)
    dist = numpy.linalg.norm(array1-array2)
    return (dataPoint[0], (centroid[0], dist))

def minDist(row):
    index = row[0]
    myList = row[1]
    minValue = -1
    minPoint = None
    minCentroidIndex = -1
    for element in myList:
        centroidIndex = element[0]
        distance = element[1]
        if (minValue == -1) or (distance < minValue):
            minValue = distance
            minCentroidIndex = centroidIndex
            minPoint = (minCentroidIndex, minValue)
    return (index, minPoint)

def plot2DResult(data, centroids):
    colors = ['r', 'b', 'g', 'c', 'm']
    fig, ax = plt.subplots( nrows=1, ncols=1 )  # create figure & 1 axis
    for element in data:
        cluster = element[0]
        values = element[1]
        pointsX = []
        pointsY = []
        for value in values:
            pointsValues = value[0]
            distance = value[1]
            pointsX.append(pointsValues[0])
            pointsY.append(pointsValues[1])
        ax.scatter(pointsX, pointsY, color=colors[cluster], marker='+')
        
    for element in centroids:
        cluster = element[0]
        values = element[1]
        centroidsX = [values[0]]
        centroidsY = [values[1]]
        ax.scatter(centroidsX, centroidsY, color=colors[cluster], marker='o', linewidths=0.5, edgecolor='black')
    
    fileName = 'iter2-' +str(iterations)
    ax.set_title(fileName)
    fig.savefig(fileName +  '.png') 

def computeCentroids(dataMinDistance, oldCentroids):
    dataByCluster = dataMinDistance.join(data).map(lambda (iPoint, ((iCentroid, dist), data)): (iCentroid, (data, dist)))
    dataByCluster = dataByCluster.groupByKey().map(lambda (key, resultIterator): (key, list(resultIterator)))
    newCentroids = dataByCluster.map(lambda (iCentroid, clusterItems): reCalculating(iCentroid, clusterItems))
    plot2DResult(dataByCluster.collect(), oldCentroids.collect())   
    return newCentroids

def reCalculating(iCentroid, clusterItems):
    allLists = []
    for element in clusterItems:
        # element = ([5.4, 3.7, 1.5, 0.2, u'Iris-setosa'], 0.6999999999999994)
        allLists.append(element[0][:-1])
    averageArray = list(numpy.average(allLists, axis = 0))
    newCentroid = (iCentroid, averageArray)
    return newCentroid

def hasConverged(centroids, newCentroids):
    centroidsData = centroids.join(newCentroids)
    centroidsDataBool = centroidsData.map(lambda (cluster, (centroidValues1, centroidValues2)): numpy.array_equal(centroidValues1, centroidValues2))
    containsFalseValue = centroidsDataBool.filter(lambda b: b == False).count() > 0
    return not containsFalseValue

def computeIntraClusterDistance(data):
    assignedClusters = data.map(lambda x : x[1])
    countAssignedClusters = assignedClusters.map(lambda x: (x[0], 1)).reduceByKey(lambda a, b : a + b)
    sumValuesAssignedClusters = assignedClusters.reduceByKey(lambda x, y: x + y)
    averageDistances = sumValuesAssignedClusters.join(countAssignedClusters).map(lambda (index, (sum, count)): sum/count)
    result = averageDistances.sum()
    return result

if len(sys.argv) != 4:
    print("3 additional arguments are needed :")
    print(" * name of the file containing the points e.g. data/iris_small.dat")
    print(" * number of clusters e.g. 4")
    print(" * max number of iterations e.g. 10\n")
    print("Try executing the following command : spark-submit kmeans.py data/iris_small.dat 4 10")
    exit(0)

# inputs
path = sys.argv[1]  # file name of the points
numClusters = int(sys.argv[2]) # number of clusters
maxIterations = int(sys.argv[3]) # maximum number of iterations

sc = SparkContext("local", "generator") # spark context

data = loadData(path)
centroids = initCentroids(data, numClusters)

iterations = 0
startTime = datetime.datetime.now()
while iterations != maxIterations:
    iterations += 1
    dataMinDistance = assignToCluster(data, centroids)
    newCentroids = computeCentroids(dataMinDistance, centroids)
    intraClusterDistances = computeIntraClusterDistance(dataMinDistance)
    print('iter #' + str(iterations) + ': ' + str(intraClusterDistances))

    if hasConverged(centroids, newCentroids):
        break;
    # To break the lineage and make the algorithm more efficient,
    # we created a new RDD from the newCentroidsList instead of using the old one.
    centroids = sc.parallelize(newCentroids.collect())
    
endTime = datetime.datetime.now()

centroids.collect()
print("Elapsed time: " + str(endTime - startTime))
print("Number of iterations: " + str(iterations))
print("Final distance: " + str(intraClusterDistances))
