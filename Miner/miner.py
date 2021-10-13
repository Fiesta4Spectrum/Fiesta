import sys
from threading import Thread
import requests
import json
import time
from flask import Flask, request

import DecentSpec.Common.config as CONFIG
from DecentSpec.Common.utils import genName, genTimestamp, log, Intrpt
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
    myPara = extract_para_from_dict(seed)
    myChain.create_genesis_block(myPara)
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

    new_block = extract_block_from_dict(request.get_json())
    if not myChain.valid_then_add(new_block):
        log("new_block", "new outcoming block get discarded")
        return "rejected", 400
    
    # if this new comer is accepted
    powIntr.raise_intr()                                       # reset my pow
    log("new_block", "new outcoming block accepted")
    myPool.remove(new_block.local_list)                  # remove the used local in the new block

    return "added", 200

if __name__ == '__main__':
    miner.run(host='0.0.0.0', port=int(myPort))

# register thread setup ============================
def register():
    global myPeers
    global myPara
    global myChain

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
            myPara = extract_para_from_dict(resp)
            myChain.create_genesis_block(myPara)
    else:
        # TODO when http get fails
        pass


def register_thread():
    while True:
        time.sleep(CONFIG.MINER_REG_INTERVAL)
        register()

register() # doing one fresh register first to make sure we have genisis block
regThread = Thread(target=register_thread)
regThread.setDaemon(True)
regThread.start()

# pow thread setup =================================

def mine():
    global myPool
    global myChain

    while True:
        time.sleep(CONFIG.BLOCK_GEN_INTERVAL)
        if myChain.difficulty < 1:
            log("mine", "difficulty not set")
            continue

        if myPool.size >= CONFIG.POOL_MINE_THRESHOLD:
            log("mine", "enough local model, start pow")
            new_block = gen_candidate_block(myPool.get_pool_list())
            if new_block:
                if i_am_the_longest_chain():
                    myChain.valid_then_add(new_block)
                    myPool.remove(new_block.local_list)
                    announce_new_block(myChain.last_block())
                    log("mine", "new block #{} is mined".format(new_block.index))
                else:
                    log("mine", "get a longer chain from else where")
            else:
                log("mine", "mine abort")

def gen_candidate_block(local_list):
    global powIntr
    global myChain
    global myPara
    global myName
    
    new_block = Block(
        local_list,
        myChain.last_block().hash,
        genTimestamp(),
        myChain.size(),
        myPara,
        myName
    )

    # proof of work
    cur_hash = new_block.compute_hash()
    difficulty = myChain.difficulty
    while not cur_hash.startswith('0' * difficulty):
        new_block.nonce += 1
        cur_hash = new_block.compute_hash()
        if powIntr.check_and_rst():
            log('pow', 'interrupted!')
            return None
    new_block.hash = cur_hash

    return new_block

def i_am_the_longest_chain():
    global myPeers
    global myChain

    i_am = True
    max_len = myChain.size()

    for peer in myPeers:
        resp = requests.get(peer + CONFIG.API_GET_CHAIN_SIMPLE).json()  # get the short version
        if resp['length'] > max_len:
            resp = requests.get(peer + CONFIG.API_GET_CHAIN).json()     # get the full version
            new_chain = list(map(
                lambda x: extract_block_from_dict(x), 
                resp['chain']
                ))
            if valid_chain(new_chain):
                myChain.replace(new_chain)
                myPool.flush()                                          # flush my pool
                i_am = False
                max_len = resp['length']
    return i_am

def announce_new_block(new_block):
    global myPeers
    for peer in myPeers:
        requests.post(
            url = peer + CONFIG.API_POST_BLOCK,
            json = new_block.get_block_dict(shrank=CONFIG.FAST_HASH_AND_SHARE, with_hash=True)
        )

powThread = Thread(target = mine)
powThread.setDaemon(True)
powThread.start()

# helper methods ===================================

def extract_para_from_dict(resp):
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

def extract_block_from_dict(resp):
    global myPara

    template = Block(
        [],
        resp['prev_hash'],
        resp['time_stamp'],
        resp['index'],
        myPara,
        resp['miner']
    )
    template.hash = resp['hash']
    template.nonce = resp['nonce']
    template.difficulty = resp['difficulty']
    template.seed_name = resp['seed_name']
    template.local_hash = resp['local_hash']
    template.base_global = resp['base_global']
    template.new_global = resp['new_global']

    return template

def valid_resp(resp):
    return resp.status_code == requests.codes.ok

def valid_seed(new_seed):
    # TODO validate the new seed
    return True

def valid_model(new_local):
    # TODO validate the new model from an edge device
    return True

def valid_hash(new_block):
    return (new_block.compute_hash() == new_block.hash) and \
            (new_block.hash.startswith('0' * new_block.difficulty))

def valid_chain(new_chain):
    global myPara
    # valid it is a good chain
    # and compatible with our para
    if new_chain[0].seed_name != myPara.seed_name:
        log("chain validation", "outcoming chain from a different seed")
        return False

    prev_hash = CONFIG.GENESIS_HASH
    for block in new_chain:
        if (not prev_hash == block.hash) or (valid_hash(block)):
            log("chain validation", "wrong hash for block #" + block.index)
            return False
        prev_hash = block.hash
    return True