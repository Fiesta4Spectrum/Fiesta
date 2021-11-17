import sys
import json
import requests
import time
import pickle
from flask import Flask, request
import threading
from importlib import import_module

from DecentSpec.Seed.database import MinerDB, RewardDB
from DecentSpec.Common.modelTemplate import FNNModel 
from DecentSpec.Common.utils import genPickleName, load_weights_from_dict, print_log, save_weights_into_dict, genName, tensor2dict
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
'''

seed = Flask(__name__)
SEED = None
if (len(sys.argv) == 3):
    task_type = sys.argv[1]
    # dynamic import Task seed
    if task_type == "tv":   
        SEED = getattr(import_module("DecentSpec.Common.tasks"), "TV_CHANNEL_TASK")
    elif task_type == "anom":
        SEED = getattr(import_module("DecentSpec.Common.tasks"), "ANOMALY_DETECTION_TASK")
    else:
        print("unrecognized task")
        exit()
    myPort = sys.argv[2]
else:
    print("wrong argument, check usage")
    exit()


myName = genName()  # name of this seed server
print("***** NODE init, I am seed {} *****".format(myName))
myMembers = MinerDB()

layerStructure = SEED.DEFAULT_NN_STRUCTURE
def genSeedName():
    global mySeedName
    mySeedName = SEED.NAME + "_" + genName(3)
genSeedName()
mySeedModel = FNNModel(layerStructure)

myPara = {
    'alpha' : SEED.ALPHA,
    'preprocPara' : SEED.PREPROC_PARA,
    'trainPara' : SEED.TRAIN_PARA,
    'samplePara' : SEED.SAMPLE_PARA,
    'layerStructure' : layerStructure,
    'difficulty' : SEED.DIFFICULTY,
} 

def stateSaver():
    global mySeedName
    global myName
    global mySeedModel
    global myPara
    while True:
        time.sleep(CONFIG.PICKLE_INTERVAL)
        dump_dict = {
            'seed_name' : mySeedName,
            'name' : myName,
            'seed_model' : mySeedModel,
            'para' : myPara,
        }
        with open(genPickleName(myName, CONFIG.PICKLE_SEED), "wb") as f:
            pickle.dump(dump_dict, f)

rewardRecord = RewardDB(myMembers, myPara, myName)

# register related api ===================================

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

def migrateFromDump():
    global layerStructure
    # TODO use the previous dumped global model
    ret = FNNModel(layerStructure)
    with open(CONFIG.PICKLE_GLOBAL, "rb") as f:
        expended_weight = pickle.load(f)
    # print("[migration] before:")
    # print(expended_weight)
    first_neuron_weight = expended_weight['ol.weight'][0]
    first_neuron_bias = expended_weight['ol.bias'][0]
    for i in range(0, 7):
        expended_weight['ol.weight'].append(first_neuron_weight)
        expended_weight['ol.bias'].append(first_neuron_bias)
    # print("[migration] after:")
    # print(expended_weight)
    load_weights_from_dict(ret, expended_weight)
    return ret

# ask this new seed to reseed the network
@seed.route(CONFIG.API_TV_to_MULTITV, methods=['GET'])
def flush():   
    global myMembers
    global mySeedModel
    global myPara
    global layerStructure
    global SEED

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

    mySeedModel = migrateFromDump()
    genSeedName() # change the seed name
    post_object = {
        'name' : mySeedName,
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
    return "new seed injected", 200

# another thread printing registered list periodically
def memberList():
    global myMembers
    while (True):
        print("[t1] currently members:")
        for i in range(myMembers.size):
            print(myMembers.showMember(i))
        time.sleep(5)

if __name__ == '__main__':

    # memListThread = threading.Thread(target=memberList)
    # memListThread.setDaemon(True)
    # memListThread.start()

    saveThread = threading.Thread(target=stateSaver)
    saveThread.setDaemon(True)
    saveThread.start()

    seed.run(host='0.0.0.0', port=int(myPort))



