from os.path import isfile, isdir
from os import makedirs
from datetime import datetime
import csv
import logging


logger = logging.getLogger(__name__)

class CSVWriter:


    SAVE_LOCATION = "logs/"

    def __init__(self, sensorName):
        if not isdir(CSVWriter.SAVE_LOCATION):
            makedirs(CSVWriter.SAVE_LOCATION)
        self.outFilePath = self.__getOutFileName(sensorName)
        self.outFile = open(self.outFilePath, "w", newline='', encoding='utf-8')
        self.csv_writer = csv.writer(self.outFile, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        #logger.info("saving data from sensor " + sensorName + " to " + self.outFilePath)


    def __getOutFileName(self, sensorName):
        ext = ".csv"
        temp = CSVWriter.SAVE_LOCATION + datetime.now().strftime("%Y-%m-%d-%H-%M")+ "_"+sensorName    
        temp2 = temp + ext
        counter=0
        while isfile(temp2):
            counter+=1
            temp2 = temp + "_" + str(counter) + ext
        return temp2

    def prepare(self, dataFields):
        self.csv_writer.writerow(dataFields)

    def saveSample(self, sampleDict):
        data = sampleDict.values()
        #logger.info("saving sample")
        self.csv_writer.writerow(data)
        self.outFile.flush() # kind of a hack, idealy we would not flush each time
                             # and properly close the file at the end, but for now
                             # we don't hava a way to gracefully close the sensors'
                             # threads

    def end(self):
        if not self.outFile.closed:
            self.outFile.close()

class DBWriter:

    def __init__(self, host, user, password):
        pass

    def prepare(self, dataFields):
        raise NotImplementedError
    
    def saveSample(self, sample):
        raise NotImplementedError
    
    def end(self):
        raise NotImplementedError