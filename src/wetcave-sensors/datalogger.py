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
import time
import RPi.GPIO as GPIO



# signal.signal(signal.SIGTERM, sigterm_handler)

def serialize_nonstandard(item): 
    if isinstance(item, datetime): 
        return item.isoformat() 
    raise TypeError(f"{type(item)} not serializable") 

class DataLogger:
    def __init__(self,config):
        self.config=config
        
        #initialize GPIO 
        GPIO.setmode(GPIO.BCM)
    
        #initialize all sensors

        self.sensors=[]
        try:
            self.sensors.append(RangeSensor(**config["rangesounder"]))
        except:
            logger.warning("Cannot add range sensor, ignoring")
        try:   
            self.sensors.append(PressTempSensor(**config["barotemp"]))
        except:
            logger.warning("Cannot add pressure/temp sensor, ignoring")
        try:
            self.sensors.append(TippingBucket(**config["tippingbucket"]))
        except:
            logger.warning("Cannot add tipping bucket sensor, ignoring")

        self.relays=[]
        for ky,val in config["relays"].items():
            self.relays.append(Relay(name=ky,**val))

        #initiate mqtt client
        clientid=config["mqtt"]["clientid"]
        self.broker=config["mqtt"]["server"]
        user=config["mqtt"]["user"]
        passw=config["mqtt"]["password"]
        self.topicroot=config["mqtt"]["topicroot"]
        self.port=config["mqtt"]["port"]
        self.qos=config["mqtt"]["qos"]
        self.statustopic=f"{self.topicroot}/{clientid}"
        self.client = mqtt.Client(client_id=clientid,transport='tcp', protocol=mqtt.MQTTv5)
        self.client.username_pw_set(user,passw)
        self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self.client.on_connect = self.mqtt_onconnect
        self.client.on_disconnect = self.mqtt_ondisconnect
        self.client.on_connect_fail = self.mqtt_onconnectfail
        self.client.on_message = self.mqtt_onmessage
        self.client.will_set(self.statustopic+"/status", "LOST_CONNECTION", 1, True)
        self.pubcount=0
        
        self.taskhandlers={}

        self.mqttConnected=False
        #make sure to clean up stuff properly when this program is killed
        signal.signal(signal.SIGTERM, self.cleanup)
        signal.signal(signal.SIGINT, self.cleanup)
    
    def mqtt_onconnect(self,client, userdata, flags,rc,aux):
        self.mqttConnected=True    
        res=client.publish(self.statustopic+"/status", f"online since: {datetime.now(timezone.utc).isoformat()}", 1, True)
        if res[0] != 0:
            logger.error("error publishing online message")

        #subscribe to topics
        #register listeners by subscrining to sensor and relay tasks
        self.taskhandlers={}
        for dev in self.sensors + self.relays:
            topic,qos=dev.subscribe()
            # Link the device task handlers to the topic
            fulltopic=self.topicroot+"/"+topic
            self.taskhandlers[fulltopic]=dev.task_handler
            logger.info(f"Listening (subscribing) on {fulltopic}")
            client.subscribe(fulltopic,qos)
    
    def mqtt_ondisconnect(self,client, userdata, rc):
        self.mqttConnected=False
        # self.client.loop_stop()

    def mqtt_onconnectfail(self,client,userdata):
        self.mqttConnected=False
        self.client.loop_stop()
    
    def mqtt_onmessage(self,client, userdata, message):
        """Take action when a certain message is received"""
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
            topic=self.topicroot+"/"+sensor.topic

            logger.info(f"\t{topic}, sampling at {sensor.sampling} seconds")
        
        logger.info("Registered relays:")
        for relay in self.relays:
            topic=self.topicroot+"/"+relay.topic

            logger.info(f"\t{topic}, waiting for plans")
    
    async def startsensor(self,sensor):
        """Producer function: Add measurements to the queue once they become available"""
        
        logger.info(f"Acquiring samples for {sensor.topic}")
        while True:
            logger.info("calling sample")
            sensormessages=await sensor.sample()
            for message in sensormessages:
                await self.messages.put(message)
        
        logger.info(f"Ending sensor loop for {sensor.topic}")
    
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
            topic,message,qos,retain=await self.messages.get()
            #todo send to mqtt server & possibly log locally
            logger.info(f"{topic},{message}")
            self.mqtt_connect()
            
            if self.mqttConnected:
                #publish message
                topic=self.topicroot+"/"+topic
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
        #start sensor loops
        sensortasks=[]
        for sensor in self.sensors:
            sensortasks.append(asyncio.create_task(self.startsensor(sensor)))
       
        # add relays
        relaytasks=[]
        for relay in self.relays:
            relaytasks.append(asyncio.create_task(self.startrelay(relay)))

        #start processing the message queue
        await self.processMessages()
    


    def cleanup(self,*args):
        logger.info("Stopping Datalogger")
        #publish a message that this client is closing its connection
        res=self.client.publish(self.statustopic+"/status", f"offline since: {datetime.now(timezone.utc).isoformat()}", 1, True)
        if res[0] != 0:
            logger.error("error publishing message")
        
        time.sleep(10)
        self.client.disconnect()
        GPIO.cleanup()
        sys.exit(0)
