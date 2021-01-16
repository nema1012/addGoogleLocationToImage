import os
from PIL import Image
import PIL.ExifTags
import json
import pandas as pd
import numpy as np
import datetime
from GPSPhoto import gpsphoto
import sys
import time
import csv

points = []
obj = ''
fileName = ''
header = ['filename', 'locationFound']


def get_exif(filename):
    exif = Image.open(filename)._getexif()
    exif_data = {}


    if exif is not None:
        for k, v in PIL.ExifTags.TAGS.items():
            if k in exif:
                value = exif[k]
            else:
                value = None

            if len(str(value)) > 64:
                value = str(value)[:65] + "..."
            
            exif_data[v] = {"tag": k,
                            "raw": value,
                            "processed": value}

        if 'GPSInfo' in exif:
            for key in exif['GPSInfo'].keys():
                name = GPSTAGS.get(key, key)
                exif_data['GPSInfo'][name] = exif['GPSInfo'].pop(key)

    return exif_data


def month(i):
    switcher = {
        1: 'JANUARY',
        2: 'FEBRUARY',
        3: 'MARCH',
        4: 'APRIL',
        5: 'MAY',
        6: 'JUNE',
        7: 'JULY',
        8: 'AUGUST',
        9: 'SEPTEMBER',
        10: 'OCTOBER',
        11: 'NOVEMBER',
        12: 'DECEMBER'
    }
    return switcher.get(i)


def findAndReadJsonFile(exif, locationFolderPath):
    global fileName
    global obj
    dateTimeOriginal = exif['DateTimeOriginal']['raw'].replace(":", "-", 2)
    dt = pd.Series(pd.to_datetime(dateTimeOriginal,
                   format='%Y-%m-%d %H:%M:%S', exact=False))
    df = pd.DataFrame(dict(date_given=dt))
    fileNameTmp = locationFolderPath + '/' + str(df['date_given'].dt.year[0]) + '/' + \
        str(df['date_given'].dt.year[0]) + '_' + \
            month(df['date_given'].dt.month[0]) + '.json'
    if fileName == fileNameTmp:
        return obj

    fileName = fileNameTmp
    # read file
    with open(fileName, 'r') as myfile:
        data = myfile.read()

    # parse file
    obj = json.loads(data)
    return obj


def filterList(jsonData, filter):
    places = []
    for place in jsonData:
        if filter in place:
            places.append(place)

    return places


def isNearestDate(nearestObject, newObject, dateTimeOriginal):
    startTime = abs(int(nearestObject['startTimestampMs']) - dateTimeOriginal)
    endTime = abs(int(nearestObject['endTimestampMs']) - dateTimeOriginal)

    startTimeNew = abs(int(newObject['startTimestampMs']) - dateTimeOriginal)
    endTimeNew = abs(int(newObject['endTimestampMs']) - dateTimeOriginal)

    if startTimeNew < startTime and endTimeNew < endTime:
        return True

    return False


def isNearestDateToFarAway(nearestObject, dateTimeOriginal, maxPlaces):
    if maxPlaces == 1:
        return False

    startTime = abs(int(nearestObject['startTimestampMs']) - dateTimeOriginal)
    endTime = abs(int(nearestObject['endTimestampMs']) - dateTimeOriginal)

    if startTime > 43200000 and endTime > 43200000:
        return True

    return False


def findLocationPlaceVisit(exif, jsonData):
    nearestObject = {}
    dateTimeOriginal = exif['DateTimeOriginal']['raw'].replace(":", "-", 2)
    dt = pd.to_datetime(
        dateTimeOriginal, format='%Y-%m-%d %H:%M:%S', exact=False)
    milliseconds = int(round((dt.timestamp() - 1*60*60) * 1000))
    placeVisits = filterList(jsonData['timelineObjects'], 'placeVisit')

    nearestObject = placeVisits[0]

    for place in placeVisits:
        if isNearestDate(nearestObject['placeVisit']['duration'], place['placeVisit']['duration'], milliseconds):
            nearestObject = place

    if isNearestDateToFarAway(nearestObject['placeVisit']['duration'], milliseconds, len(placeVisits)):
        return None

    return nearestObject['placeVisit']['location']

def findLocationInActivity(exif, jsonData):
    nearestObject = {}
    dateTimeOriginal = exif['DateTimeOriginal']['raw'].replace(":", "-", 2)
    dt = pd.to_datetime(
        dateTimeOriginal, format='%Y-%m-%d %H:%M:%S', exact=False)
    milliseconds = int(round((dt.timestamp() - 1*60*60) * 1000))
    activityPlaces = filterList(jsonData['timelineObjects'], 'activitySegment')

    nearestObject = activityPlaces[0]

    for place in activityPlaces:
        if isNearestDate(nearestObject['activitySegment']['duration'], place['activitySegment']['duration'], milliseconds):
            nearestObject = place

    if isNearestDateToFarAway(nearestObject['activitySegment']['duration'], milliseconds, len(placeVisits)):
        return None

    return nearestObject['activitySegment']['startLocation']



def addLocation(fileName, locationData):
    photo = gpsphoto.GPSPhoto(fileName)
    longitude = locationData['longitudeE7']/1e7
    latitude = locationData['latitudeE7']/1e7
    info = gpsphoto.GPSInfo((latitude, longitude))
    photo.modGPSData(info, fileName)

def createRows(updatedFiles, filesWithoutLocation):
    rows = []
    for str in updatedFiles:
        rows.append([str, 'true'])

    for str in filesWithoutLocation:
        rows.append([str, 'false'])

    return rows


def writeCSV(header, rows):
    with open('photo-location.csv', 'wt') as f:
        csv_writer = csv.writer(f)

        csv_writer.writerow(header) # write header

        csv_writer.writerows(rows)


pictureFolderPath = './example'
locationFolderPath = './example'
startTime = time.time()
filesWithoutLocation = []
if len(sys.argv) == 2:
    pictureFolderPath = sys.argv[1]

if len(sys.argv) == 3:
    locationFolderPath = sys.argv[2]

updatedFiles = []
for r, d, f in os.walk('.'):
    for file in f:
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
            filepath = os.path.join(r, file)
            exif = get_exif(filepath)
            if exif['GPSInfo']['raw'] == None:
                jsonData = findAndReadJsonFile(exif, locationFolderPath)
                locationData = findLocationPlaceVisit(exif, jsonData)

                if locationData == None:
                    locationData = findLocationInActivity(exif, jsonData)

                if locationData == None:
                    print('No location found for ' + filepath)
                    filesWithoutLocation.append(filepath)
                    break

                addLocation(filepath, locationData)
                updatedFiles.append(filepath)

updatedFilesSize = len(updatedFiles)
filesWithoutLocationSize = len(filesWithoutLocation)
print('Finished updated files(' + str(updatedFilesSize) + '): ' + str(updatedFiles))
print('Files readed: ' + str(updatedFilesSize))
print('Files updated: ' + str(updatedFilesSize - filesWithoutLocationSize))
if (filesWithoutLocationSize > 0):
    print('Files without Location found: ' + str(filesWithoutLocationSize))

print('Needed time: ' + str((time.time() - startTime)/1000))
rows = createRows(updatedFiles, filesWithoutLocation)
writeCSV(header, rows)
