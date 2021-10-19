import sys
from threading import Thread
import requests
import json
import time
from flask import Flask, request

import DecentSpec.Common.config as CONFIG
from DecentSpec.Common.utils import difficultyCheck, genName, genTimestamp, hashValue, print_log, Intrpt
from DecentSpec.Miner.blockChain import Block, BlockChain, FileLogger
from DecentSpec.Miner.pool import Pool
from DecentSpec.Miner.para import Para

# local field init ========================

'''
usage:
    python -m DecentSpec.Miner.miner {1} {2} {3}
    {1} - ip or domain with http
    {2} - port 
    {3} - POOL_MINE_THRESHOLD
'''

miner = Flask(__name__)
myPort = "8000"
myIp = "http://api.decentspec.org"
if (len(sys.argv) == 4):
    myIp = sys.argv[1]
    myPort = sys.argv[2]
    POOL_MINE_THRESHOLD = int(sys.argv[3])
else:
    print("incorrect parameter")
    print(__doc__)
    exit

myAddr = myIp + ":" + myPort
myName = genName()
print("***** NODE init, I am miner {} *****".format(myName))

myLogger = FileLogger(myName)
myLogger.calibrate()
myChain = BlockChain(myLogger)
myPool = Pool(myLogger)
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
        print_log("reseed", "invalid seed")
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
    LOCAL_HASH_FIELD = 'hash'

    resp = request.get_json()
    if not valid_model(resp):
        print_log('new_local', 'invalid local model received')
        return "Invalid local model", 400
    # add the model hash field to this local weight package
    if SPREAD_FLAG in resp:
        resp.pop(SPREAD_FLAG)                               # avoid useless repeat spread
        if not LOCAL_HASH_FIELD in resp:
            resp[LOCAL_HASH_FIELD] = hashValue(resp)
        thread = Thread(target=spread_to_peers, args=[resp])
        thread.start()
    else:
        if not LOCAL_HASH_FIELD in resp:
            resp[LOCAL_HASH_FIELD] = hashValue(resp)
    myPool.add(resp)
    return "new local model received", 201

def spread_to_peers(local_model):
    global myPeers
    
    print_log("new_local", "gonna share this local model")
    for peer in myPeers:
        try:
            requests.post(
                url = peer + CONFIG.API_POST_LOCAL,
                json = local_model
            )
        except requests.exceptions.ConnectionError:
            print_log("requests", "fails to connect to " + peer)

@miner.route(CONFIG.API_GET_POOL, methods=['GET'])
def get_pool():
    global myPool

    return json.dumps(myPool.get_pool_list())

'''test only'''
@miner.route('/test', methods=['GET'])
def get_para():
    global myChain
    return json.dumps(myChain.size)

@miner.route(CONFIG.API_GET_GLOBAL, methods=['GET'])
def get_global():
    global myChain
    global myPara

    latest = myChain.last_block
    para = myPara
    data = {    'weight' : latest.get_global(),
                'preprocPara' : para.preproc,
                'trainPara' : para.train,
                'layerStructure' : para.nn_structure,
                'seed_name' : para.seed_name,
                'generation' : myChain.size,
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
        'latest_block' : myChain.last_block.get_block_dict(shrank = True),
    }
    return json.dumps(data)

@miner.route(CONFIG.API_POST_BLOCK, methods=['POST'])
def new_block(): 
    global myChain
    global myPool
    global powIntr

    new_block = extract_block_from_dict(request.get_json())
    if not myChain.valid_then_add(new_block):
        print_log("new_block", "new outcoming block get discarded")
        if new_block.index > myChain.size and new_block.seed_name == myPara.seed_name:
            consensus()
        return "rejected", 400
    # if this new comer is accepted
    powIntr.set()                                       # reset my pow
    print_log("new_block", "new outcoming block #{} accepted".format(new_block.index))
    myPool.remove(new_block.local_list)                  # remove the used local in the new block
    powIntr.rst()
    return "added", 200

# register thread setup ============================

def register():
    global myPeers
    global myPara
    global myChain

    data = {
        'name' : myName,
        'addr' : myAddr
    }
    try:
        resp = requests.post(
            url = CONFIG.SEED_ADDR + CONFIG.API_REGISTER,
            json = data
        )
    except requests.exceptions.ConnectionError:
        print_log("requests", "fails to connect to seed")
        resp = None
    if valid_resp(resp):
        myPeers = set(resp.json()['list'])
        myPeers.remove(myAddr)
        if myPara == None:
            myPara = extract_para_from_dict(resp)
            myChain.create_genesis_block(myPara)
    else:
        # TODO when http get fails
        print_log("register", "seed server not available")
        pass


def register_thread():
    while True:
        register()
        time.sleep(CONFIG.MINER_REG_INTERVAL)

# pow thread setup =================================

def mine():
    global myPool
    global myChain

    while True:
        time.sleep(CONFIG.BLOCK_GEN_INTERVAL)
        if myPara == None or myChain.difficulty < 1:
            print_log("mine", "difficulty not set")
            continue

        if myPool.size >= POOL_MINE_THRESHOLD:
            print_log("mine", "enough local model, start pow")
            new_block = gen_candidate_block(myPool.get_pool_list(POOL_MINE_THRESHOLD))
            if new_block:
                if consensus():
                    if myChain.valid_then_add(new_block):
                        myPool.remove(new_block.local_list)
                        announce_new_block(myChain.last_block)
                        print_log("mine", "new block #{} is mined".format(new_block.index))
                    else:
                        print_log("mine", "self mined block #{} is discarded".format(new_block.index))
            else:
                print_log("mine", "mine abort")

def gen_candidate_block(local_list):
    global powIntr
    global myChain
    global myPara
    global myName
    
    if powIntr.check():
        print_log('pow', 'not allowed!')
        return None

    new_block = Block(
        local_list,
        myChain.last_block.hash,
        genTimestamp(),
        myChain.size,
        myPara,
        myName,
        myChain.last_block.new_global
    )

    # proof of work
    cur_hash = new_block.compute_hash()
    difficulty = myChain.difficulty
    while not difficultyCheck(cur_hash, new_block.difficulty):
        new_block.nonce += 1
        cur_hash = new_block.compute_hash()
        if powIntr.check():
            print_log('pow', 'interrupted!')
            return None
    new_block.hash = cur_hash

    return new_block

def consensus():
    global myPeers
    global myChain
    global powIntr

    i_am = True
    max_len = myChain.size

    for peer in myPeers:
        try:
            resp = requests.get(peer + CONFIG.API_GET_CHAIN_SIMPLE).json()  # get the short version
            if resp['length'] > max_len:
                resp = requests.get(peer + CONFIG.API_GET_CHAIN).json()     # get the full version
                new_chain = list(map(
                    lambda x: extract_block_from_dict(x), 
                    resp['chain']
                    ))
                if valid_chain(new_chain):
                    powIntr.set()
                    myChain.replace(new_chain)
                    print_log("consensus", "get a longer chain from else where")
                    myPool.flush()                                          # flush my pool
                    powIntr.rst()
                    i_am = False
                    max_len = resp['length']
        except requests.exceptions.ConnectionError:
            print_log("requests", "fails to connect to " + peer)
    return i_am

def announce_new_block(new_block):
    global myPeers
    for peer in myPeers:
        try:
            requests.post(
                url = peer + CONFIG.API_POST_BLOCK,
                json = new_block.get_block_dict(shrank=False)
            )
        except requests.exceptions.ConnectionError:
            print_log("requests", "fails to connect to " + peer)

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
        resp['local_list'],
        resp['prev_hash'],
        resp['time_stamp'],
        resp['index'],
        myPara,     # dummy and useless here
        resp['miner'],
        resp['base_global'],
        template=True
    )
    template.hash = resp['hash']
    template.nonce = resp['nonce']
    template.difficulty = resp['difficulty']
    template.seed_name = resp['seed_name']

    template.local_hash = resp['local_hash']
    template.new_global = resp['new_global']

    return template

def valid_resp(resp):
    if resp == None:
        return False
    return resp.status_code == requests.codes.ok

def valid_seed(new_seed):
    # TODO validate the new seed
    return True

def valid_model(new_local):
    # TODO validate the new model from an edge device
    return True

def valid_hash(new_block):
    if new_block.index == 0:
        return new_block.compute_hash() == new_block.hash
    return (new_block.compute_hash() == new_block.hash) and difficultyCheck(new_block.hash, new_block.difficulty)

def valid_chain(new_chain):
    global myPara
    # valid it is a good chain
    # and compatible with our para
    if new_chain[0].seed_name != myPara.seed_name:
        print_log("chain validation", "outcoming chain from a different seed")
        return False

    prev_hash = CONFIG.GENESIS_HASH
    for block in new_chain:
        if not prev_hash == block.prev_hash:
            print_log("chain validation", "hash link broke at block #{}".format(block.index))
            return False
        if not valid_hash(block):
            print_log("chain validation", "wrong hash value for block #{}".format(block.index))
            return False
        prev_hash = block.hash
    return True

if __name__ == '__main__':
    # threads init ==============================

    regThread = Thread(target=register_thread)
    regThread.setDaemon(True)
    regThread.start()

    powThread = Thread(target=mine)
    powThread.setDaemon(True)
    powThread.start()

    miner.run(host='0.0.0.0', port=int(myPort))
