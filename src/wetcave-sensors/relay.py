import asyncio
import RPi.GPIO as GPIO
from datetime import datetime,timezone,timedelta
import json
from copy import deepcopy
class Relay:
    def __init__(self,name,gpiopin):
        self.pin=gpiopin
        self.topic=f"relay/{name}"
        GPIO.setup(self.pin, GPIO.OUT,initial=GPIO.HIGH)
        #boolean to keep track of state
        self.isoff=True
        self.messages=[]
        self.subscribetopic=self.topic+"/task"
        self.qos=1
        #default plan is invalid (no on time scheduled)
        self.plan_start=datetime.max
        self.plan_stop=datetime.min
        self.plan_active=False


    def on(self):
        if self.isoff:
            print(f"{self.topic} switching relay to ON")
            GPIO.output(self.pin,GPIO.LOW)
            self.isoff=False
            self.messages.append((self.topic+"/event",{"on":datetime.now(timezone.utc)},self.qos,False))

    
    def off(self):
        if not self.isoff:
            print(f"{self.topic} switching relay to OFF")
            GPIO.output(self.pin,GPIO.HIGH)
            self.isoff=True
            self.messages.append((self.topic+"/event",{"off":datetime.now(timezone.utc)},self.qos,False))

    def setplan(self,start,stop):
        print(f"setting up relay plan {start} - {stop}")
        self.messages.append((self.topic+"/plan",{"start":start,"stop":stop},self.qos,False))
        self.plan_start=start
        self.plan_stop=stop
        self.plan_active=True

    async def getmessages(self):
        
        if len(self.messages) == 0:
            await asyncio.sleep(10)
            return []
        else:
            messagescopy=deepcopy(self.messages)
            self.messages=[]
            return messagescopy

    async def start_loop(self):
        """ Run a loop to check whether the relay needs to be switched on"""
        print(f"starting relay listener {self.topic}")
        while True:
            if not self.plan_active:
                #just sleep before trying again
                await asyncio.sleep(10)
                continue
            else:
                #ok check if the plan has commenced
                now=datetime.now(timezone.utc)

                if self.plan_start < now and now <= self.plan_stop:
                    # plan has started
                    self.on()
                elif self.plan_stop < now:
                    #plan has stopped 
                    print(f"End of plan for {self.topic}")
                    self.plan_active=False
                    self.off()
                else:                
                    #make sure it's offf (probably a superflous statement)
                    self.off()

                #check back every second while a plan is active
                await asyncio.sleep(1)







    def task_handler(self,message):
        action=json.loads(message.payload)
        for ky,val in action.items():
            if ky == "duration":
                #plan a period where the relay is on
                duration=val
                start=datetime.now(timezone.utc)
                stop=start+timedelta(seconds=duration)
                self.setplan(start,stop)
            else:
                print(f"Don't know what to do with {ky}, ignoring")
    
    def subscribe(self):
        return (self.subscribetopic,self.qos)
    
