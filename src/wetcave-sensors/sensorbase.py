import asyncio
from datetime import datetime,timedelta,timezone
from copy import deepcopy
import json

class SensorBase():
    def __init__(self,topic,sampling):
        self.topic="sensor/"+topic
        self.t0=datetime.now(timezone.utc)
        self.lastsample=self.t0
        self.messages=[self.uptime()]  
        self.subscribetopic="sensor/"+topic+"/task"
        self.qos=1
        self.setsampling(sampling)
    
    def uptime(self):
        return (self.topic+"/uptime",{"start":self.t0,"sec":(datetime.now(timezone.utc)-self.t0).seconds})

    def disconnect_msg(self):
        #message 0 means regular (client initiated) disconnect 
        return (self.topic+"/disconnect",{"time":datetime.now(timezone.utc)})

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
        print(f"change sampling of {self.topic} to {sampling}sec")
        self.sampling=timedelta(seconds=sampling)
        self.messages.append((self.topic+"/sampling",sampling))
    
    def subscribe(self):
        return (self.subscribetopic,self.qos)

    def task_handler(self,message):
        action=json.loads(message.payload)
        for ky,val in action.items():
            if ky == "setsampling":
                #change the sampling
                self.setsampling(val)
