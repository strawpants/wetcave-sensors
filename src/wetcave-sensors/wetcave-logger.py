#!/usr/bin/env python

import os
import yaml
from datalogger import DataLogger
from messagelogging import setuplogger
import asyncio

def readconfig(ymlfile=None):
    if ymlfile is None:
        ymlfile=os.path.expanduser('~/wetcave-config.yml')
    with open(ymlfile,'rt') as fid:
        config=yaml.safe_load(fid)

    
    return config
    




def main():
    config=readconfig()

    #setup message logging
    setuplogger(logfile=config['logging']['file'],debug=config['logging']['debug'])

    
    dlogger=DataLogger(config)

    dlogger.list()    
    asyncio.run(dlogger.start_logger())



if __name__ == "__main__":
    main()
