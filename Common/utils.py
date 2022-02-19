import random
import os
import shutil
import pickle
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
        self.remark = None
    # def check(self):
    #     with self.lock:
    #         ret = self.flag
    #     return ret
    # def rst(self):
    #     with self.lock:
    #         self.flag = False
    def check_and_rst(self):
        with self.lock:
            ret = self.flag
            self.flag = False
        return ret
    def set(self, remark = None):
        with self.lock:
            self.flag = True
            self.remark = remark

def safe_dump(file_name, dump_dict):
    print_log("pickle", "start saving state for " + file_name)
    if os.path.isfile(file_name):
        shutil.copy2(file_name, file_name + "_backup" )
    with open(file_name, "wb+") as f:
        pickle.dump(dump_dict, f)
    if os.path.isfile(file_name + "_backup"):
        os.remove(file_name + "_backup")
    print_log("pickle", "state saved!")

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

def genPickleName(id, content, remark=None):
    if (remark == None):
        return "{}_{}.pickle".format(content, id[0:5])
    return "{}_{}_{}.pickle".format(content, id[0:5], remark)

def genBlockFileName(new_block):
    return "{}_{}_{}.b".format(new_block.index, new_block.hash[:5], new_block.miner[:5])

def cleanDir(dirPath):
    for file in os.scandir(dirPath):
        os.remove(file.path)

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

def dumpBlock_pub(path, new_block):
    os.makedirs(path, exist_ok=True)
    file_name = genBlockFileName(new_block)
    if os.path.isfile(path + file_name):
        return file_name
    with open(path + file_name, "wb+") as f:
        pickle.dump(new_block, f)
    return file_name

def loadBlock_pub(path, file_name):
    with open(path + file_name, "rb") as f:
        my_block = pickle.load(f)
    return my_block