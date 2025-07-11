import asyncio
import RPi.GPIO as GPIO
from datetime import datetime,timezone,timedelta
import json
from copy import deepcopy
from messagelogging import logger

class Relay:
    def __init__(self,name,gpiopin,longname="Relais",icon="mdi:toggle-switch",root=""):
        self.pin=gpiopin
        self.roottopic=root
        self.topic=f"{root}/relay/{name}"
        GPIO.setup(self.pin, GPIO.OUT,initial=GPIO.HIGH)
        #boolean to keep track of state
        self.isoff=True
        self.messages=[]
        self.subscribetopic=self.topic+"/task"
        self.statetopic=self.topic+"/state"
        self.qos=1
        #default plan is invalid (no on time scheduled)
        self.plan_start=datetime.max
        self.plan_stop=datetime.min
        self.plan_active=False
        self.icon=icon
        self.name=name
        self.longname=longname

        self.messages.append((self.statetopic,{"status":"OFF","since":datetime.now(timezone.utc)},self.qos,False))

    def on(self):
        if self.isoff:
            logger.info(f"{self.topic} switching relay to ON")
            GPIO.output(self.pin,GPIO.LOW)
            self.isoff=False
            # self.messages.append((self.topic+"/event",{"on":datetime.now(timezone.utc)},self.qos,False))

            self.messages.append((self.statetopic,{"status":"ON","since":datetime.now(timezone.utc)},self.qos,False))
         
    def off(self):
        if not self.isoff:
            logger.info(f"{self.topic} switching relay to OFF")
            GPIO.output(self.pin,GPIO.HIGH)
            self.isoff=True
            # self.messages.append((self.topic+"/event",{"status":datetime.now(timezone.utc)},self.qos,False))

            self.messages.append((self.statetopic,{"status":"OFF","since":datetime.now(timezone.utc)},self.qos,False))
    
    def setplan(self,start,stop):
        logger.info(f"setting up relay plan {start} - {stop}")
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
        logger.info(f"starting relay listener {self.topic}")
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
                    logger.info(f"End of plan for {self.topic}")
                    self.plan_active=False
                    self.off()
                else:                
                    #make sure it's offf (probably a superflous statement)
                    self.off()

                #check back every second while a plan is active
                await asyncio.sleep(1)







    def task_handler(self,message):
        try:
            action=json.loads(message.payload)
        except:
            logger.warning("ignoring after parsing error of {message.payload}")
            return
        try:
            if action['switch'] == 'OFF':
                #force siwtch off regardless of plan
                logger.info(f"Forcing shutdown for {self.topic}")
                self.plan_active=False
                self.off()
            elif action['switch'] == "ON":
                if 'duration' in action:
                    duration=action['duration']

                    start=datetime.now(timezone.utc)
                    stop=start+timedelta(seconds=duration)
                else:
                    start=datetime.fromisoformat(action['start'])
                    stop=datetime.fromisoformat(action['end'])
                self.setplan(start,stop)
        except:
            logger.warning(f"Don't know what to do with {message.payload}, ignoring")
    
    def subscribe(self):
        return (self.subscribetopic,self.qos)
    
    def hass_discovery(self):
        #generate the discovery dictionary
        hadict={
             "~":self.roottopic,
            "p": "switch",
            "device_class":"outlet",
            "name":self.longname,
            "command_template":'{"switch": "{{value}}","duration":60}',
            "command_topic":self.subscribetopic.replace(self.roottopic,'~'),
            "value_template":"{{value_json.status}}",
            "unique_id":self.name+"_001",
            "icon":self.icon,
            "state_topic":self.statetopic.replace(self.roottopic,'~'),
            "qos":1
            }
        return hadict

