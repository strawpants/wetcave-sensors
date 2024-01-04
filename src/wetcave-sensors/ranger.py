from sensorbase import SensorBase
import asyncio
from datetime import datetime,timezone
from statistics import mean,stdev
from math import sqrt
import RPi.GPIO as GPIO
import time

usleep = lambda x: time.sleep(x*1e-6)

class RangeSensor(SensorBase):
    def __init__(self,sampling,gpiopin,nsamples,speedofsound):
        super().__init__("range",sampling)
        print(f"Starting {self.topic}")        
        self.nsamples=nsamples
        self.pin=gpiopin
        self.outlierbounds=[800,12000]
        #default speed of sound
        self.speedofsound=speedofsound
        # add standard speed of sound to the messages
        self.messages.append((self.topic+"/speedofsound",speedofsound))
   
    def sampleRangeSingle(self):
        #To initiate a measurement start by sending a pulse to the pin as output 
        GPIO.setup(self.pin, GPIO.OUT)
        
        GPIO.output(self.pin,GPIO.LOW)
        usleep(2)
        GPIO.output(self.pin,GPIO.HIGH)
        usleep(10)
        GPIO.output(self.pin,GPIO.LOW)
        
        #turn the pin in an input pin and wait for a pulse (and compute the length of the pulse)
        GPIO.setup(self.pin, GPIO.IN,pull_up_down = GPIO.PUD_DOWN)
        
        riseDetected=GPIO.wait_for_edge(self.pin, GPIO.RISING,timeout=100)
        if not riseDetected:
            return None

        t1=time.time()

        fallDetected=GPIO.wait_for_edge(self.pin, GPIO.FALLING,timeout=100)
        
        if not fallDetected:
            return None
        t2=time.time()

        traveltime=t2-t1
        return traveltime*1e6

    def triggersample(self):
        dtlist=[]
        for i in range(self.nsamples+1):
            dt=self.sampleRangeSingle()
            if dt == None:
                #try again
                continue
            if dt < self.outlierbounds[0] or dt > self.outlierbounds[1]:
                #outlier don't use in the computation of the mean
                continue
            dtlist.append(dt)
        nsamples=len(dtlist)
        if nsamples < 2:
            #don't add message if the amount of data points is below the bare minimum
            print(f"Not enough samples for the range: {nsamples}")
            return
        dtmean=mean(dtlist)
        dtstd=stdev(dtlist)*sqrt(nsamples)
        #update outlierbounds (20 cm +/- of previous estimate)
        bound=(20e-2/self.speedofsound)*1e6
        self.outlierbounds[0]=dtmean-bound
        self.outlierbounds[1]=dtmean+bound

        now=datetime.now(timezone.utc)
        self.messages.append((self.topic+"/traveltime",{"time":now,"value":dtmean,"std":dtstd}))
