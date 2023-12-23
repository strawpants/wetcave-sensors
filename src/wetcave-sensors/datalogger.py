from logging import getLogger
from datetime import datetime
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
import time
import RPi.GPIO as GPIO

logger = getLogger(__name__)

def sigterm_handler(signal, frame):
    # save the state here or do whatever you want
    logger.info("Stopping Datalogger")
    GPIO.cleanup()
    sys.exit(0)

signal.signal(signal.SIGTERM, sigterm_handler)

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
        self.sensors.append(RangeSensor(**config["rangesounder"]))
        self.sensors.append(PressTempSensor(**config["barotemp"]))
        self.sensors.append(TippingBucket(**config["tippingbucket"]))

        #initiate mqtt client
        clientid=config["mqtt"]["clientid"]
        self.broker=config["mqtt"]["server"]
        user=config["mqtt"]["user"]
        passw=config["mqtt"]["password"]
        self.topicroot=config["mqtt"]["topicroot"]
        self.port=config["mqtt"]["port"]
        self.client = mqtt.Client(client_id=clientid,transport='tcp', protocol=mqtt.MQTTv5)
        self.client.username_pw_set(user,passw)
        self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self.client.on_connect = self.mqtt_onconnect
        self.client.on_disconnect = self.mqtt_ondisconnect
        self.mqttConnected=False
        self.pubcount=0

    def mqtt_onconnect(self,client, userdata, flags,rc,aux):
        self.mqttConnected=True    
    def mqtt_ondisconnect(self,client, userdata, rc):
        self.mqttConnected=False

    def mqtt_connect(self):
        if self.mqttConnected:
            return
        try:
            self.client.connect(self.broker,port=self.port,keepalive=60);
            self.client.loop_start()
            time.sleep(5)
        except:
            print("Failed to resolve broker, continuing")
            self.mqttConnected=False

        
    def list(self):
        print("Registered sensors:")
        for sensor in self.sensors:
            topic=self.topicroot+"/"+sensor.topic

            print(f"\t{topic}, sampling at {sensor.sampling} seconds")
    
    async def startsensor(self,sensor):
        """Producer function: Add measurements to the queue once they become available"""
        
        #note: some sensor may need to run their own asyncio loop so this can be implemented in the start function (default just returns without doing anything
        # sensortask=asyncio.create_task(sensor.start())
        print(f"Acquiring samples for {sensor.topic}")
        while True:
            print("calling sample")
            sensormessages=await sensor.sample()
            # print("Queuing messages")
            for topic,message in sensormessages:
                await self.messages.put((topic,message))
    
    
    async def processMessages(self):
        """Consumer function: process messages"""
        print("waiting for messages")
        while True:
            topic,message=await self.messages.get()
            #todo send to mqtt server & possibly log locally
            print(f"{topic},{message}")
            if not self.mqttConnected:
                self.mqtt_connect()
            
            if self.mqttConnected:
                #publish message
                topic=self.topicroot+"/"+topic
                print(f"Publishing message on {topic} count {self.pubcount}")
                if type(message) == dict:
                    payload=json.dumps(message,default=serialize_nonstandard)
                else:
                    payload=message

                res=self.client.publish(topic,payload)
                if res[0] != 0:
                    print("error publishing message")
                
                self.pubcount+=1

            else:
                print("error connecting to mqtt server,continuing")
            self.messages.task_done()

    async def start_logger(self):
        self.messages=asyncio.Queue()
        #start sensor loops
        sensortasks=[]
        for sensor in self.sensors:
            sensortasks.append(asyncio.create_task(self.startsensor(sensor)))
        
        #start processing the message queue
        await self.processMessages()

