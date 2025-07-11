import asyncio
from datetime import datetime,timezone,timedelta
import json
from copy import deepcopy
from messagelogging import logger

class Number:
    def __init__(self,name,description="Number",icon="mdi:numeric",root="",unit='',value=0,devclass="None"):
        self
        self.roottopic=root
        self.topic=f"{root}/param/{name}"
        self.messages=[]
        self.subscribetopic=self.topic+"/set"
        self.valuetopic=self.topic+"/value"
        self.qos=1
        self.icon=icon
        self.name=name
        self.longname=description
        self.unit=unit
        self.devclass=devclass
        self.setValue(value)

    def setValue(self,value):
        self.value=value
        self.messages.append((self.valuetopic,self.value,self.qos,True))

    async def getmessages(self):
        
        if len(self.messages) == 0:
            await asyncio.sleep(10)
            return []
        else:
            messagescopy=deepcopy(self.messages)
            self.messages=[]
            return messagescopy


    def task_handler(self,message):
        try:
            self.value=float(message.payload)
        except:
            logger.warning(f"Don't know what to do with the number payload {message.payload}, ignoring")

    def subscribe(self):
        return (self.subscribetopic,self.qos)
    
    def hass_discovery(self):
        #generate the discovery dictionary
        hadict={
             "~":self.roottopic,
             "p": "number",
            "device_class":self.devclass,
            "name":self.longname,
            "command_topic":self.subscribetopic.replace(self.roottopic,'~'),
            "unique_id":self.name+"_0x1",
            "icon":self.icon,
            "state_topic":self.valuetopic.replace(self.roottopic,'~'),
            "retain":"true",
            "unit_of_measurement":self.unit,
            "qos":1,
            "min":-1000,
            "max":1000,
            "step":0.001
            }
        return hadict

