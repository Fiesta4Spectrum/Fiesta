import sys
from threading import Thread
import requests
import json
import time
from flask import Flask, request

import DecentSpec.Common.config as CONFIG
from DecentSpec.Common.utils import genName, log, Intrpt
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
powIntr = Intrpt('pow interrupt')

myPeers = None      # peer miner list
myPara = None       # mother copy of parameters
                    # not directly referenceds only used for duplication

# flask api setup ========================================

@miner.route(CONFIG.API_UPDATE_SEED, methods=['POST'])
def reseed():
    global myPool
    global myChain
    global myPara
    
    seed = request.get_json()
    if not valid_seed(seed):
        log("reseed", "invalid seed")
        return "invalid", 400
    myPool.flush()
    myChain.flush()
    myPara = extract_para(seed)
    # TODO init the new block chain
    return "reseeded", 201

@miner.route(CONFIG.API_POST_LOCAL, methods=['POST'])
def new_local(): 
    global myPool

    SPREAD_FLAG = 'plz_spread'
    resp = request.get_json()
    if not valid_model(resp):
        log('new_local', 'invalid local model received')
        return "Invalid local model", 400
    if SPREAD_FLAG in resp:
        resp.pop(SPREAD_FLAG)                               # avoid useless repeat spread
        thread = Thread(target=spread_to_peers, args=[resp])
        thread.start()
    myPool.add(resp)
    return "new local model received", 201

def spread_to_peers(local_model):
    global myPeers
    
    log("new_local", "gonna share this local model")
    for peer in myPeers:
        requests.post(
            url = peer + CONFIG.API_POST_LOCAL,
            json = local_model
        )

@miner.route(CONFIG.API_GET_POOL, methods=['GET'])
def get_pool():
    global myPool

    return json.dumps(myPool.get_pool_list())

@miner.route(CONFIG.API_GET_GLOBAL, methods=['GET'])
def get_global():
    global myChain

    latest = myChain.last_block()
    para = latest.para
    data = {    'weight' : latest.get_global(),
                'preprocPara' : para.preproc,
                'trainPara' : para.train,
                'layerStructure' : para.nn_structure,
                }
    return json.dumps(data)

@miner.route(CONFIG.API_GET_CHAIN, methods=['GET'])
def get_chain():
    global myChain

    data = {
        'length' : myChain.size,
        'chain' : myChain.get_chain_list(),
    }
    return json.dumps(data)

@miner.route(CONFIG.API_GET_CHAIN_SIMPLE, methods=['GET'])
def get_chain_simple():
    global myChain
    data = {
        'length' : myChain.size,
        'latest_block' : myChain.last_block().get_block_dict(),
    }
    return json.dumps(data)

@miner.route(CONFIG.API_POST_BLOCK, methods=['POST'])
def new_block(): 
    global myChain
    global myPool
    global powIntr

    new_block = extract_block(request.get_json())
    if not myChain.valid_then_add(new_block):
        log("new_block", "new outcoming block get discarded")
        return "rejected", 400
    
    # if this new comer is accepted
    powIntr.set()                                       # reset my pow
    log("new_block", "new outcoming block accepted")
    myPool.remove(new_block.local_list)                  # remove the used local in the new block

    return "added", 200

if __name__ == '__main__':
    miner.run(host='0.0.0.0', port=int(myPort))

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
    if valid_resp(resp):
        myPeers = set(resp.json()['list'])
        myPeers.remove(myAddr)
        if myPara == None:
            myPara = extract_para(resp)
    else:
        # TODO when http get fails
        pass


def register_thread():
    while True:
        register()
        time.sleep(CONFIG.MINER_REG_INTERVAL)

regThread = Thread(target=register_thread)
regThread.setDaemon(True)
regThread.start()

# pow thread setup =================================

def proof_of_work():
    pass

    # TODO using multithreading / multiprocess to pow

# helper methods ===================================

def extract_para(resp):
    # extract para from a json
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

def extract_block(resp):
    # TODO extract block object from a json 
    return Block()

def valid_resp(resp):
    return resp.status_code == requests.codes.ok

def valid_seed(new_seed):
    # TODO validate the new seed
    return True

def valid_model(new_local):
    # TODO validate the new model from an edge device
    return True