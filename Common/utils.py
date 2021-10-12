import random
import time
import string
import json
import torch
from hashlib import sha256
from threading import Lock

import DecentSpec.Common.config as CONFIG

GENESIS_HASH = "genesisHash"

class Intrpt:
    def __init__(self, desc="noDescription"):
        self.flag = False
        self.lock = Lock()
        self.desc = desc
    def check_and_rst(self):
        with self.lock:
            ret = self.flag
            self.flag = False
        return ret
    def set(self):
        with self.lock:
            self.flag = True

def log(tag, content):
    print(tag + ":" + content)

def genName(num=CONFIG.DEFAULT_NAME_LENGTH):
    salt = ''.join(random.sample(string.ascii_letters + string.digits, num))
    return salt

def genHash(content):               # generate hash from block dict
    contentDup = content.copy()     # list in python is "ref" as function argument, so 
                                    # to avoid change the original dict, we copy it
    if 'global_model' in content:
        contentDup.pop('global_model') # remove the global_model cause it is lazy generated
    if 'transactions' in content:
        contentDup.pop('transactions') # transaction is too large to hash we will use its hash to generate the block's hash
    if 'hash' in content:
        contentDup.pop('hash')         # remove the hash itself
    return hashValue(contentDup)

def hashValue(content):
    strValue = json.dumps(content, sort_keys=True)
    return sha256(strValue.encode()).hexdigest()

# store and load weights
def save_weights_into_dict(model):
    return tensor2dict(model.state_dict())

def load_weights_from_dict(model, weights):
    model.load_state_dict(dict2tensor(weights))

def genTimestamp():
    return time.time()

def dict2tensor(myDict):
    myWeight = {}
    for key in myDict.keys():
        myWeight[key] = torch.tensor(myDict[key])
    return myWeight

def tensor2dict(myWeight):
    myDict = {}
    for key in myWeight.keys():
        myDict[key] = myWeight[key].tolist()
    return myDict

def is_valid_proof(block, block_hash, difficulty):
    """
    Check if block_hash is valid hash of block 
    and satisfies the difficulty criteria.
    """
    if isinstance(block, dict):
        fresh_hash = genHash(block)         # if it is a dict block
        isGenesis = not block["index"]
    else:
        fresh_hash = block.compute_hash()   # if it is an object
        isGenesis = not block.index
    
    if isGenesis:
        return block_hash == fresh_hash     # genesis block do not have a valid nonce
    else:
        return (block_hash.startswith('0' * difficulty) and
            block_hash == fresh_hash)

def check_chain_validity(chain, difficulty): # this is an list-dict chain, not an object
    previous_hash = GENESIS_HASH

    # check the model version of the chain first
    # TODO the model version must the same with mine, before we really validate it
    for block in chain:
        block_hash = block["hash"]
        # using `compute_hash` method.
        if not is_valid_proof(block, block_hash, difficulty) or \
                previous_hash != block["previous_hash"]:
            print("badchain: block #{} is invalid".format(block["index"]))
            return False
        previous_hash = block_hash
    return True

def proof_of_work(block, difficulty, intr):
    """
    Function that tries different values of nonce to get a hash
    that satisfies our difficulty criteria.
    """
    block.nonce = 0

    computed_hash = block.compute_hash()
    while not computed_hash.startswith('0' * difficulty):
        block.nonce += 1
        computed_hash = block.compute_hash()
        if intr.checkAndRst():
            return False, "pow interrupted"
    return True, computed_hash