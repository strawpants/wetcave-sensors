from messagelogging import logger
from datetime import datetime,timezone
import paho.mqtt.client as mqtt
import os
import signal
import sys
import asyncio
import ssl
import json
from ranger import RangeSensor
from baro import PressTempSensor
from tippingbucket import TippingBucket
from relay import Relay
from number import Number
import time
import RPi.GPIO as GPIO



# signal.signal(signal.SIGTERM, sigterm_handler)

def serialize_nonstandard(item): 
    if isinstance(item, datetime): 
        return item.isoformat() 
    raise TypeError(f"{type(item)} not serializable") 

class HADataLogger:
    def __init__(self,config):
        self.config=config
        
        # #initialize GPIO 
        GPIO.setmode(GPIO.BCM)
    
        # try:   
            # self.sensors.append(PressTempSensor(**config["barotemp"]))
        # except:
            # logger.warning("Cannot add pressure/temp sensor, ignoring")
        # try:
            # self.sensors.append(TippingBucket(**config["tippingbucket"]))
        # except:
            # logger.warning("Cannot add tipping bucket sensor, ignoring")


        # #initiate mqtt client
        clientid=config["mqtt"]["clientid"]
        self.broker=config["mqtt"]["server"]
        user=config["mqtt"]["user"]
        passw=config["mqtt"]["password"]
        self.topicroot=config["mqtt"]["topicroot"]
        self.port=config["mqtt"]["port"]
        self.qos=config["mqtt"]["qos"]
        self.unique_id=config['hass']['unique_id']
        self.hw_id=config['hass']['hw_id']
        self.builder_id=config['hass']['builder_id']
        self.hass_deviceroot=f"{self.topicroot}/device/{self.unique_id}"
        self.devicestatustopic=f"{self.hass_deviceroot}/state"
        self.disc_topic=self.hass_deviceroot+"/config"
        self.hass_status=self.topicroot+"/status"

        #regsiter relays
        self.relays=[]
        for ky,val in config["relays"].items():
            self.relays.append(Relay(name=ky,root=self.hass_deviceroot,**val))
        
        #register device numbers (parameters)
        self.numbers=[]
        for ky,val in config["numbers"].items():
            self.numbers.append(Number(name=ky,root=self.hass_deviceroot,**val))
        
        # #initialize all sensors

        self.sensors=[]
        try:
            name='rangesounder'
            self.sensors.append(RangeSensor(name=name,root=self.hass_deviceroot,**config[name]))
        except Exception as exc:
            breakpoint()
            logger.warning("Cannot add range sensor, ignoring")

        self.client = mqtt.Client(client_id=clientid,transport='tcp', protocol=mqtt.MQTTv5)
        self.client.username_pw_set(user,passw)
        self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self.client.on_connect = self.mqtt_onconnect
        self.client.on_disconnect = self.mqtt_ondisconnect
        self.client.on_connect_fail = self.mqtt_onconnectfail
        self.client.on_message = self.mqtt_onmessage
        self.client.will_set(self.devicestatustopic, "offline", 1, True)
        self.pubcount=0
        

        self.mqttConnected=False
        # #make sure to clean up stuff properly when this program is killed
        signal.signal(signal.SIGTERM, self.cleanup)
        signal.signal(signal.SIGINT, self.cleanup)
    
    def mqtt_onconnect(self,client, userdata, flags,rc,aux):
        self.mqttConnected=True
        res=client.publish(self.devicestatustopic, "online", 1, False)
        if res[0] != 0:
            logger.error("error publishing online message")

        #publish the current discovery message
        self.publish_discovery()

        #subscribe to homeassistant status
        client.subscribe(self.hass_status,0)



        # #subscribe to topics
        # #register listeners by subscrining to sensor and relay tasks
        self.taskhandlers={}
        for dev in self.sensors + self.relays + self.numbers:
            topic,qos=dev.subscribe()
            # Link the device task handlers to the topic
            self.taskhandlers[topic]=dev.task_handler
            logger.info(f"Listening (subscribing) on {topic}")
            client.subscribe(topic,qos)

    def mqtt_ondisconnect(self,client, userdata, rc):
        self.mqttConnected=False
        # # self.client.loop_stop()

    def mqtt_onconnectfail(self,client,userdata):
        self.mqttConnected=False
        self.client.loop_stop()
    
    def mqtt_onmessage(self,client, userdata, message):
        """Take action when a certain message is received"""
        if message.topic == self.hass_status and message.payload == 'online':
            #republish discovery when Home assistant comes online again
            self.publish_discovery()
    
        if message.topic in self.taskhandlers:
            #execute task handler function
            self.taskhandlers[message.topic](message)
        else:
            logger.warning(f"ignoring {message.topic}")


    def mqtt_connect(self):
        if self.mqttConnected:
            return
        try:
            self.client.connect(self.broker,port=self.port,keepalive=60);
            self.client.loop_start()
            time.sleep(5)
        except:
            logger.warning("Failed to resolve broker, continuing")
            self.mqttConnected=False

        
    def list(self):
        logger.info("Registered sensors:")
        for sensor in self.sensors:
            topic=sensor.topic

            logger.info(f"\t{topic}, sampling at {sensor.sampling} seconds")
        
        logger.info("Registered relays:")
        for relay in self.relays:
            topic=relay.topic

            logger.info(f"\t{topic}, waiting for plans")
        
        logger.info("Registered numbers:")
        for number in self.numbers:
            topic=number.topic

            logger.info(f"\t{topic}, waiting for value updates")
    
    async def startsensor(self,sensor):
        """Producer function: Add measurements to the queue once they become available"""
        
        logger.info(f"Acquiring samples for {sensor.topic}")
        while True:
            logger.info("calling sample")
            sensormessages=await sensor.sample()
            for message in sensormessages:
                await self.messages.put(message)
        
        logger.info(f"Ending sensor loop for {sensor.topic}")

    async def startnumber_listeners(self,number):

        logger.info("Check for number messages")
        while True:
            numbermessages=await number.getmessages()
            for message in numbermessages:
                await self.messages.put(message)

    async def startrelay(self,relay):
        """Producer function: Start the relay loop"""
        
        logger.info(f"Starting relay loop {relay.topic}")
        looptask=asyncio.create_task(relay.start_loop())
        logger.info("Check for relay messages")
        while True:
            relaymessages=await relay.getmessages()
            for message in relaymessages:
                await self.messages.put(message)
        logger.info(f"Ending relay loop for {relay.topic}")
    
    async def processMessages(self):
        """Consumer function: process messages"""
        logger.info("waiting for messages")
        self.mqtt_connect()
        while True:
            await asyncio.sleep(5)
            topic,message,qos,retain=await self.messages.get()
            #todo send to mqtt server & possibly log locally
            logger.info(f"{topic},{message}")
            self.mqtt_connect()
            
            if self.mqttConnected:
                #publish message
                # topic=self.topicroot+"/"+topic
                logger.info(f"Publishing message on {topic} count {self.pubcount}")
                if type(message) == dict:
                    payload=json.dumps(message,default=serialize_nonstandard)
                else:
                    payload=message

                res=self.client.publish(topic,payload,qos=qos,retain=retain)
                if res[0] != 0:
                    logger.error("error publishing message")

                self.pubcount+=1

            else:
                logger.error("error connecting to mqtt server,continuing")
            self.messages.task_done()
        logger.info("ending message processing loop")
    
    async def start_logger(self):
        self.messages=asyncio.Queue()
        # #start sensor loops
        sensortasks=[]
        for sensor in self.sensors:
            sensortasks.append(asyncio.create_task(self.startsensor(sensor)))
       
        # # add relays
        relaytasks=[]
        for relay in self.relays:
            relaytasks.append(asyncio.create_task(self.startrelay(relay)))
        # add number listeners
        numberlisteners=[]
        for number in self.numbers:
            numberlisteners.append(asyncio.create_task(self.startnumber_listeners(number)))
        # #start processing the message queue
        await self.processMessages()
   
    def publish_discovery(self):
        """
        create device discovery message for use with home assistant
        """
        discpayload={
                "dev": {
                    "ids": "wetcave-01",
                    "name": "Wetcave",
                    "mf": self.builder_id,
                    "sn": self.hw_id,
                    "hw": self.hw_id
                    },
                "o": {
                    "name":"wetcave-sensors",
                    "sw": "2.0",
                    "url": "https://github.com/strawpants/wetcave-sensors/issues"
                    },
                "cmps":{},
                "state_topic":self.devicestatustopic,
                "qos": self.qos
                }

        #add relay components
        for relay in self.relays:
            discpayload['cmps'][relay.name]=relay.hass_discovery()
        
        #add numbers
        for number in self.numbers:
            discpayload['cmps'][number.name]=number.hass_discovery()
        
        #add sensors
        for sensor in self.sensors:
            discpayload['cmps'][sensor.name]=sensor.hass_discovery()

        message=json.dumps(discpayload)
        res=self.client.publish(self.disc_topic, message, 1, False)
        if res[0] != 0:
            logger.error("error publishing hass discovery message")

    def cleanup(self,*args):
        logger.info("Stopping HADatalogger")
        # #publish a message that this client is closing its connection
        res=self.client.publish(self.devicestatustopic, "offline", 1, False)
        if res[0] != 0:
            logger.error("error publishing state message")
        
        time.sleep(10)
        self.client.disconnect()
        GPIO.cleanup()
        sys.exit(0)
