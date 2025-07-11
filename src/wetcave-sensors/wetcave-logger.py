#!/usr/bin/env python

import os
import yaml
from datalogger import HADataLogger
from messagelogging import setuplogger
import asyncio
import argparse
import sys

def readconfig(ymlfile=None):
    if ymlfile is None:
        ymlfile=os.path.expanduser('~/wetcave-config.yml')
    with open(ymlfile,'rt') as fid:
        config=yaml.safe_load(fid)

    
    return config
    




def main():
    parser = argparse.ArgumentParser(prog='wetcave-logger',description="Log data from wetcave to a mqtt server")

    parser.add_argument('-c','--config', nargs='?', type=str, help='Specify config file to load')
    
    # parser.add_argument('--hass', action='store_true', help='Use home assistant setup')
    args=parser.parse_args(sys.argv[1:]) 
    config=readconfig(ymlfile=args.config)

    #setup message logging
    setuplogger(logfile=config['logging']['file'],debug=config['logging']['debug'])
    dlogger=HADataLogger(config)

    dlogger.list()    
    asyncio.run(dlogger.start_logger())



if __name__ == "__main__":
    main()
