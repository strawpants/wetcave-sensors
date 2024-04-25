from logging import getLogger,basicConfig,DEBUG,INFO,FileHandler,StreamHandler
import os

logger=getLogger("Wetcave-sensors")

def setuplogger(logfile,debug):

    dirname=os.path.dirname(logfile)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    if debug:
        level=DEBUG
    else:
        level=INFO
    
    basicConfig(handlers=[FileHandler(logfile),StreamHandler()],level=level)
