#!/usr/bin/env python
import RPi.GPIO as GPIO
from sensorbase import SensorBase
import asyncio
from datetime import datetime,timezone
from copy import deepcopy
class TippingBucket(SensorBase):
    def __init__(self,sampling,gpiopin,mm_tip):
        super().__init__("tippingbucket",sampling)
        print(f"Starting {self.topic}")        
        self.pin=gpiopin
        GPIO.setup(self.pin, GPIO.IN,pull_up_down = GPIO.PUD_DOWN)
        GPIO.add_event_detect(self.pin,GPIO.RISING,callback=self.addtip,bouncetime=333)
        # add standard mm_tip value to the messages
        self.messages.append((self.topic+"/mm_tip",mm_tip))
    
    def addtip(self,pin):
        #add a tipping event to the message (this function will be called on an intterupt)
        self.messages.append((self.topic+"/tip",{"time":datetime.now(timezone.utc)}))
    

