#!/usr/bin/env python

import os
import yaml
from datalogger import DataLogger
import asyncio

def readconfig(ymlfile=None):
    if ymlfile is None:
        ymlfile=os.path.expanduser('~/wetcave-config.yml')
    with open(ymlfile,'rt') as fid:
        config=yaml.safe_load(fid)

    return config
    




def main():
    config=readconfig()
    dlogger=DataLogger(config)

    dlogger.list()    
    asyncio.run(dlogger.start_logger())



if __name__ == "__main__":
    main()
