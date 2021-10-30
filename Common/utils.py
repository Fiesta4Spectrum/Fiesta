import random
import time
from datetime import datetime
import string
import json
import torch
from hashlib import sha256
from threading import Lock

import DecentSpec.Common.config as CONFIG

class Intrpt:
    def __init__(self, desc="noDescription"):
        self.flag = False
        self.lock = Lock()
        self.desc = desc
    def check(self):
        with self.lock:
            ret = self.flag
        return ret
    def rst(self):
        with self.lock:
            self.flag = False
    def check_and_rst(self):
        with self.lock:
            ret = self.flag
            self.flag = False
        return ret
    def set(self):
        with self.lock:
            self.flag = True

def print_log(tag, content):
    print("[{}] {}".format(tag, content))

def genName(num=CONFIG.DEFAULT_NAME_LENGTH):
    salt = ''.join(random.sample(string.ascii_letters + string.digits, num))
    return salt

def genTimestamp():
    return time.time()

def curTime():
    return str(datetime.fromtimestamp(genTimestamp()))

def hashValue(content):
    strValue = json.dumps(content, sort_keys=True)
    return sha256(strValue.encode()).hexdigest()

def difficultyCheck(hash, difficulty):
    if CONFIG.POW_ENABLE:
        return hash.startswith("0" * difficulty)
    else:
        return True

# store and load weights
def save_weights_into_dict(model):
    return tensor2dict(model.state_dict())

def load_weights_from_dict(model, weights):
    model.load_state_dict(dict2tensor(weights))

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
