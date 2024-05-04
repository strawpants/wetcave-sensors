#!/usr/bin/env python
import RPi.GPIO as GPIO
from sensorbase import SensorBase
import asyncio
from datetime import datetime,timezone
import time
from copy import deepcopy
from messagelogging import logger


class TippingBucket(SensorBase):
    def __init__(self,sampling,gpiopin,mm_tip):
        super().__init__("tippingbucket",sampling)
        self.pin=gpiopin
        GPIO.setup(self.pin, GPIO.IN,pull_up_down = GPIO.PUD_DOWN)
        GPIO.add_event_detect(self.pin,GPIO.RISING,callback=self.addtip,bouncetime=200)
        # add standard mm_tip value to the messages
        self.messages.append((self.topic+"/mm_tip",mm_tip,self.qos,False))

    def addtip(self,pin):
        #add a tipping event to the message (this function will be called on an intterupt)
        
        # wait for a short duration and then check for high on the input to make sure it was a valid tip
        time.sleep(100e-3)

        if GPIO.input(pin):
            #check if it still high during the duration of the pulse
            self.messages.append((self.topic+"/tip",{"time":datetime.now(timezone.utc),"valid":1},self.qos,False))
            time.sleep(100e-3)
        else:
            logger.warning("Spurious tip ignored")

    

