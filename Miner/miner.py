import sys
from threading import Thread
import requests
import json
import time
from flask import Flask, request

import DecentSpec.Common.config as CONFIG
from DecentSpec.Common.utils import genName
from DecentSpec.Miner.blockChain import Block, BlockChain
from DecentSpec.Miner.pool import Pool
from DecentSpec.Miner.para import Para

miner = Flask(__name__)

myPort = "8000"
myIp = "http://api.decentspec.org"
if (len(sys.argv) == 3):
    myIp = sys.argv[1]
    myPort = sys.argv[2]
else:
    print("incorrect parameter")
    exit
myAddr = myIp + ":" + myPort
myName = genName()

# local field and lock init ========================
myChain = BlockChain()
myPool = Pool()

myPeers = None
myPara = None

# api setup ========================================

@miner.route(CONFIG.API_UPDATE_SEED, methods=['POST'])
def reseed():
    pass

@miner.route(CONFIG.API_POST_LOCAL, methods=['POST'])
def new_local(): 
    pass

@miner.route(CONFIG.API_GET_POOL, methods=['GET'])
def get_pool():
    pass

@miner.route(CONFIG.API_GET_GLOBAL, methods=['GET'])
def get_global():
    pass

@miner.route(CONFIG.API_GET_CHAIN, methods=['GET'])
def get_chain():
    pass

@miner.route(CONFIG.API_GET_CHAIN_PRINT, methods=['GET'])
def get_chain_print():
    pass

@miner.route(CONFIG.API_POST_BLOCK, methods=['POST'])
def new_block(): 
    pass

# register thread setup ============================
def register():
    global myPeers
    global myPara

    data = {
        'name' : myName,
        'addr' : myAddr
    }
    resp = requests.post(
        url = CONFIG.SEED_ADDR + CONFIG.API_REGISTER,
        json = data
    )
    if valid(resp):
        myPeers = set(resp.json()['list'])
        myPeers.remove(myAddr)
        myPara = extract_para(resp)

def register_thread():
    while True:
        register()
        time.sleep(CONFIG.MINER_REG_INTERVAL)

regThread = Thread(target=register_thread)
regThread.setDaemon(True)
regThread.start()

# pow thread setup =================================

if __name__ == '__main__':
    miner.run(host='0.0.0.0', port=int(myPort))

# helper methods ===================================

def valid(resp):
    return resp.status_code == requests.codes.ok

def extract_para(resp):
    para = resp.json()['para']
    return Para(
        preproc=para['preprocPara'],
        train=para['trainPara'],
        alpha=para['alpha'],
        difficulty=para['difficulty'],
        seeder=resp.json()['from'],
        seed_name=resp.json()['name'],
        init_weight=resp.json()['seedWeight'],
        nn_structure=para['layerStructure']
    )
