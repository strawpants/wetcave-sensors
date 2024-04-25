from sensorbase import SensorBase
import asyncio
from datetime import datetime,timezone
from hp206c import hp206c
from statistics import mean,stdev
from math import sqrt
from messagelogging import logger

class PressTempSensor(SensorBase):
    def __init__(self,sampling,nsamples):
        super().__init__("barotemp",sampling)
        self.nbarosamples=nsamples
        self.pres_temp=hp206c()
        ret=self.pres_temp.isAvailable()
        if self.pres_temp.OK_HP20X_DEV == ret:
            logger.info("Barometer is available.")
        else:
            logger.error("Barometer isn't availablei, disabling")
            self.pres_temp=None

   
    def triggersample(self):
            pres=None
            temp=None
            presstd=None
            tempstd=None
            if self.pres_temp:
                preslist=[]
                templist=[]
                for i in range(self.nbarosamples+1):
                    p=self.pres_temp.ReadPressure()
                    if (p < 600):
                        #sometimes the first measurement is wrong
                        continue
                    t=self.pres_temp.ReadTemperature()
                    
                    preslist.append(p)
                    templist.append(t)
                
                error_scale=1.0/sqrt(len(preslist)) 
                pres=mean(preslist)
                temp=mean(templist)
                presstd=stdev(preslist)*error_scale
                tempstd=stdev(templist)*error_scale
            
            now=datetime.now(timezone.utc)
            self.messages.append((self.topic+"/pressure",{"time":now,"value":pres,"std":presstd},self.qos,False))
            self.messages.append((self.topic+"/temp",{"time":now,"value":temp,"std":tempstd},self.qos,False))
