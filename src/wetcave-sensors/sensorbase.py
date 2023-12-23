import asyncio
from datetime import datetime,timedelta,timezone
from copy import deepcopy

class SensorBase():
    def __init__(self,topic,sampling):
        self.topic="sensor/"+topic
        self.sampling=timedelta(seconds=sampling)
        self.t0=datetime.now(timezone.utc)
        self.lastsample=datetime.now(timezone.utc)-self.sampling
        self.messages=[self.uptime()]  
    
    def uptime(self):
        return (self.topic+"/uptime",{"start":self.t0,"sec":(datetime.now(timezone.utc)-self.t0).seconds})

    async def start(self):
        """Default does nothing, derived classes may implement this if needed"""
        return

    def triggersample(self):
        #default does nothing
        return
    
    async def sample(self):
        self.triggersample()
        messagescopy=deepcopy(self.messages)
        self.messages=[]
        await asyncio.sleep(self.sampling.total_seconds())
        return messagescopy

    

