from sensorbase import SensorBase
# import asyncio
from datetime import datetime,timezone
from statistics import mean,stdev
from math import sqrt
# import RPi.GPIO as GPIO
import time
from messagelogging import logger
from ADS1x15 import ADS1115


class LevelSensor(SensorBase):
    def __init__(self,name,sampling,nsamples,**kwargs):
        super().__init__(name,sampling,**kwargs)
        self.nsamples=nsamples
        self.ADS = ADS1115(1, 0x48)
        #set ads115 gain (1)
        self.ADS.setGain(self.ADS.PGA_4_096V)
        

    def triggersample(self):
        mvolts=[]
        maxtries=4
        self.ADS.requestADC(0)
        for i in range(self.nsamples+1):
            itries=0
            while itries < maxtries:
                if self.ADS.isReady():
                    val_01 = self.ADS.readADC_Differential_0_1()
                    self.ADS.requestADC(0)
                    mvolt = self.ADS.toVoltage(val_01)*1e3
                    mvolts.append(mvolt)
                    break
                else:
                    time.sleep(0.5)
                    itries+=1
        nsamples=len(mvolts)
        if nsamples < 2:
            #don't add message if the amount of data points is below the bare minimum
            logger.warning(f"Not enough samples for the level sensor: {nsamples}")
            return

        mvoltmean=mean(mvolts)
        mvoltstd=stdev(mvolts)*sqrt(nsamples)
        now=datetime.now(timezone.utc)
        self.messages.append((self.topic,{"time":now,"value":mvoltmean,"std":mvoltstd,"nsamples":nsamples},self.qos,False))



if __name__ == "__main__":
    pin=4
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin, GPIO.IN)
    
    ADS = ADS1115(1, 0x48)
    
    # import RPi.GPIO as GPIO

    # set gain to 4.096V max
    ADS.setGain(ADS.PGA_4_096V)
    f = ADS.toVoltage()
    ADS.requestADC(0)

    while True :
        if ADS.isReady() :
            val_01 = ADS.readADC_Differential_0_1()
            #val_01 = ADS.getValue()
            ADS.requestADC(0)
            volts_01 = ADS.toVoltage(val_01)
            print(f"Analog_0-1: {val_01}\t{volts_01}V")
            breakpoint()
        time.sleep(1)

