import asyncio
from datetime import datetime,timedelta,timezone
from copy import deepcopy
import json
from messagelogging import logger
class SensorBase():

    def __init__(self,name,sampling,root="",icon="mdi:gauge",longname="",unit="null",devclass="",stateclass="MEASUREMENT"):
        self.roottopic=root
        self.topic=f"{root}/sensor/{name}"
        logger.info(f"Starting {self.topic}")        
        self.t0=datetime.now(timezone.utc)
        self.lastsample=self.t0
        self.qos=1
        self.subscribetopic=self.topic+"/task"
        self.messages=[self.uptime()]  
        self.setsampling(sampling)
        self.name=name
        self.icon=icon
        self.devclass=devclass
        self.longname=longname
        self.stateclass=stateclass
        self.unit=unit

    def uptime(self):
        return (self.topic+"/uptime",{"start":self.t0,"sec":(datetime.now(timezone.utc)-self.t0).seconds},self.qos,False)

    def disconnect_msg(self):
        #message 0 means regular (client initiated) disconnect 
        return (self.topic+"/disconnect",{"time":datetime.now(timezone.utc)},self.qos,False)

    async def start(self):
        """Default does nothing, derived classes may implement this if needed"""
        return

    def triggersample(self):
        #default does nothing
        return
    
    async def sample(self):
        now=datetime.now(timezone.utc)
        #align waiting period so that sampling period takes into account processing time
        # waitfor=(self.lastsample+self.sampling)-now
        # if waitfor.total_seconds() <= 0.8* self.sampling.total_seconds():
            # #make sure to wait in this case and prevent race conditions
            # waitfor=self.sampling
        # print(f"wait for {waitfor.total_seconds()}")
        await asyncio.sleep(self.sampling.total_seconds())

        self.triggersample()
        messagescopy=deepcopy(self.messages)
        self.messages=[]
        self.lastsample=now
        return messagescopy
    
    def setsampling(self,sampling):
        logger.info(f"change sampling of {self.topic} to {sampling}sec")
        self.sampling=timedelta(seconds=sampling)
        self.messages.append((self.topic+"/sampling",sampling,self.qos,True))
    
    def subscribe(self):
        return (self.subscribetopic,self.qos)

    def task_handler(self,message):
        action=json.loads(message.payload)
        for ky,val in action.items():
            if ky == "setsampling":
                #change the sampling
                self.setsampling(val)
                
    def hass_discovery(self):
        #generate the discovery dictionary
        hadict={
            "~":self.roottopic,
            "p": "sensor",
            "device_class":self.devclass,
            "name":self.longname,
            "command_topic":self.subscribetopic.replace(self.roottopic,'~'),
            "unit_of_measurement":self.unit,
            "value_template":"{{value_json.value}}",
            "unique_id":self.name+"_0y1",
            "icon":self.icon,
            "state_topic":self.topic.replace(self.roottopic,'~'),
            "state_class":self.stateclass,
            "json_attributes_topic":self.topic.replace(self.roottopic,'~'),
            "json_attributes_template": "{{ value_json  | tojson }}",
            "qos":1
            }
        return hadict

