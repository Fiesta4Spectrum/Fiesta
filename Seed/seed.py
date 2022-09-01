import sys
from werkzeug import serving
import re
import os
import json
import requests
import time
import pickle
from flask import Flask, request
import threading
from importlib import import_module

from DecentSpec.Seed.database import MinerDB, RewardDB
from DecentSpec.Common.modelTemplate import FNNModel 
from DecentSpec.Common.utils import genPickleName, load_weights_from_dict, print_log, safe_dump, save_weights_into_dict, genName, tensor2dict
import DecentSpec.Common.config as CONFIG

# from DecentSpec.Common.tasks import TV_CHANNEL_TASK as SEED
# from DecentSpec.Common.tasks import ANOMALY_DETECTION_TASK as SEED

'''
usage:
    python -m DecentSpec.Seed.seed {1} {2} 
    {1} - task type:
            "tv"    : tv channel regression
            "anom"  : anomaly detection
    {2} - int, port number

    python -m DecentSpec.Seed.seed {1}
    {1} - pickle file of states

    python -m DecentSpec.Seed.seed {1} {2} {3}
    {1} - task type:
            "tv"    : tv channel regression
            "anom"  : anomaly detection
    {2} - int, port number
    {3} - pickle file of weights

'''

seed = Flask(__name__)
SEED = None

        # dump_dict = {
        #     'local' : { 'name' : myName,
        #                 'task' : task_type, 
        #                 'port' : myPort},
        #     'seed_name' : mySeedName,
        #     'seed_model' : mySeedModel,
        #     'para' : myPara,
        # }
        
RECOVERY_FLAG = False
WEIGHT_FROM_PICKLE = False

if (len(sys.argv) == 2):
    # state recover
    RECOVERY_FLAG = True
    with open(sys.argv[1],"rb") as f:
        last_state = pickle.load(f)
    task_type = last_state['local']['task']
    myName = last_state['local']['name']
    myPort = last_state['local']['port']
elif (len(sys.argv) == 3):
    task_type = sys.argv[1]
    # dynamic import Task seed
    myPort = sys.argv[2]
    myName = genName()  # name of this seed server
elif (len(sys.argv) == 4):
    task_type = sys.argv[1]
    # dynamic import Task seed
    myPort = sys.argv[2]
    myName = genName()  # name of this seed server
    weightSource = sys.argv[3]
    WEIGHT_FROM_PICKLE = True
else:
    print("wrong argument, check usage")
    exit()

if task_type == "tv":   
    SEED = getattr(import_module("DecentSpec.Common.tasks"), "TV_CHANNEL_TASK")
elif task_type == "anom":
    SEED = getattr(import_module("DecentSpec.Common.tasks"), "ANOMALY_DETECTION_TASK")
elif task_type == "mtv":
    SEED = getattr(import_module("DecentSpec.Common.tasks"), "MULTI_TV_CHANNEL_TASK")
else:
    print("unrecognized task")
    exit()

print("***** NODE init, I am seed {} *****".format(myName))
myMembers = MinerDB()

layerStructure = SEED.DEFAULT_NN_STRUCTURE
def genSeedName():
    global mySeedName
    mySeedName = SEED.NAME + "_" + genName(3)
def migrate_from_dump(globalName, extendOutput=0):
    global layerStructure

    # TODO use the previous dumped global model
    ret = FNNModel(layerStructure)  # actually you should make sure layerstructure consistent with extendOutput
    
    with open(globalName, "rb") as f:
        expended_weight = pickle.load(f)
    # print("[migration] before:")
    # print(expended_weight)
    first_neuron_weight = expended_weight['ol.weight'][0]
    first_neuron_bias = expended_weight['ol.bias'][0]
    for i in range(0, extendOutput):
        expended_weight['ol.weight'].append(first_neuron_weight)
        expended_weight['ol.bias'].append(first_neuron_bias)
    # print("[migration] after:")
    # print(expended_weight)
    load_weights_from_dict(ret, expended_weight)
    return ret

if (not RECOVERY_FLAG):
    genSeedName()
    if WEIGHT_FROM_PICKLE:
        mySeedModel = migrate_from_dump(weightSource)
    else:
        mySeedModel = FNNModel(layerStructure)
    myPara = {
        'alpha' : SEED.ALPHA,
        'preprocPara' : SEED.PREPROC_PARA,
        'trainPara' : SEED.TRAIN_PARA,
        'samplePara' : SEED.SAMPLE_PARA,
        'layerStructure' : layerStructure,
        'difficulty' : SEED.DIFFICULTY,
    } 
else:
    mySeedName = last_state['seed_name']
    print("My seed name: ", mySeedName)
    mySeedModel = last_state['seed_model']
    myPara = last_state['para']

def stateSaver():
    global mySeedName
    global myName
    global mySeedModel
    global myPara
    os.makedirs(CONFIG.PICKLE_DIR, exist_ok=True)
    # only dump once 
    dump_dict = {
        'local' : { 'name' : myName,
                    'task' : task_type, 
                    'port' : myPort},
        'seed_name' : mySeedName,
        'seed_model' : mySeedModel,
        'para' : myPara,
    }
    safe_dump(CONFIG.PICKLE_DIR + genPickleName(myName, CONFIG.PICKLE_SEED), dump_dict)

rewardRecord = RewardDB(myMembers, myPara, myName)

# register related api ===================================

@seed.route(CONFIG.API_GET_REWARD, methods=['GET'])
def get_reward():
    global rewardRecord
    id = request.args.get('id', default="null", type=str)
    category, uploads, reward = rewardRecord.query(id)
    ret = { "id" : id,
            "role" : category,
            "uploads" : uploads,
            "reward" : reward
            }
    return json.dumps(ret)

@seed.route(CONFIG.API_GET_MINER, methods=['GET'])
def get_peers():
    global myMembers
    return json.dumps({'peers' : myMembers.getList()})

@seed.route(CONFIG.API_REGISTER, methods=['POST'])
def reg_miner():
    global myMembers
    global myPara
    global mySeedName

    reg_data = request.get_json()
    myMembers.regNew(reg_data["name"], reg_data["addr"])
    ret = {
        'seed_name' : mySeedName,
        'from' : myName,
        'seedWeight' : save_weights_into_dict(mySeedModel),
        'para' : myPara,
        'peers' : myMembers.getList(),
    }
    # print(ret)
    # print("registered a new node")
    # print(ret["para"])
    return json.dumps(ret)

# ask this new seed to reseed the network
@seed.route(CONFIG.API_TV_TO_MULTITV, methods=['GET'])
def flush():   
    global myMembers
    global mySeedModel
    global myPara
    global layerStructure
    global SEED
    global myName

    SEED = getattr(import_module("DecentSpec.Common.tasks"), "MULTI_TV_CHANNEL_TASK")

    layerStructure = SEED.DEFAULT_NN_STRUCTURE

    myPara = {
        'alpha' : SEED.ALPHA,
        'preprocPara' : SEED.PREPROC_PARA,
        'trainPara' : SEED.TRAIN_PARA,
        'samplePara' : SEED.SAMPLE_PARA,
        'layerStructure' : layerStructure,
        'difficulty' : SEED.DIFFICULTY,
    }

    mySeedModel = migrate_from_dump(CONFIG.PICKLE_DIR + genPickleName(myName, CONFIG.PICKLE_GLOBAL), 7)
    genSeedName() # change the seed name
    post_object = {
        'seed_name' : mySeedName,
        'from' : myName,
        'seedWeight' : save_weights_into_dict(mySeedModel),
        'para' : myPara,
        'peers' : myMembers.getList(),
    }
    for addr in myMembers.getList():
        try: 
            requests.post(addr+"/seed_update",
                        json=post_object)
        except requests.exceptions.ConnectionError:
            print_log("requests", "fails to connect to " + addr)
    stateSaver() # plz save the new seed!!!!!!!!
    return "new seed injected", 200

# another thread printing registered list periodically
def memberList():
    global myMembers
    while (True):
        print("[t1] currently members:")
        for i in range(myMembers.size):
            print(myMembers.showMember(i))
        time.sleep(5)


##### log filter

disabled_endpoints = [CONFIG.API_GET_MINER]

parent_log_request = serving.WSGIRequestHandler.log_request

def log_request(self, *args, **kwargs):
    if not any(re.match(f"{de}", self.path) for de in disabled_endpoints):
        parent_log_request(self, *args, **kwargs)

serving.WSGIRequestHandler.log_request = log_request

#####

if __name__ == '__main__':

    # memListThread = threading.Thread(target=memberList)
    # memListThread.setDaemon(True)
    # memListThread.start()

    stateSaver()
    # seed only dump once

    seed.run(host='0.0.0.0', port=int(myPort))



