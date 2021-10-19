import sys
import json
import requests
import time
from flask import Flask, request
import threading

from DecentSpec.Seed.database import MinerDB, RewardDB
from DecentSpec.Common.model import SharedModel # TODO 
from DecentSpec.Common.utils import print_log, save_weights_into_dict, genName
import DecentSpec.Common.config as CONFIG

seed = Flask(__name__)

myPort = "5000"
if (len(sys.argv) == 2):
    myPort = sys.argv[1]

myName = genName()  # name of this seed server
print("***** NODE init, I am seed {} *****".format(myName))
myMembers = MinerDB()

layerStructure = CONFIG.DEFAULT_NN_STRUCTURE
seedName = "TV_Channel_regression_v1"    # name of this seed
seedModel = SharedModel(layerStructure)

preprocPara = {
    'avg' : [43.07850074790703, -89.3982621182465, -58.52785514280172],
    'std' : [0.026930841086101193, 0.060267757907425355, 7.434576197607559],
}

trainPara = {
    'batch' : 10,
    'lr'    : 0.001,
    'opt'   : 'Adam',
    'epoch' : 10,                            # local epoch Num
    'loss'  : 'MSE',
}

Para = {
    'alpha' : CONFIG.ALPHA,
    'preprocPara' : preprocPara,
    'trainPara' : trainPara,
    'layerStructure' : layerStructure,
    'difficulty' : CONFIG.DIFFICULTY,
} 

rewardRecord = RewardDB(myMembers, Para)

# register related api ===================================

@seed.route(CONFIG.API_GET_MINER, methods=['GET'])
def get_peers():
    global myMembers
    return json.dumps({'peers' : myMembers.getList()})

@seed.route(CONFIG.API_REGISTER, methods=['POST'])
def reg_miner():
    global myMembers
    global Para
    reg_data = request.get_json()
    myMembers.regNew(reg_data["name"], reg_data["addr"])
    ret = {
        'name' : seedName,
        'from' : myName,
        'seedWeight' : save_weights_into_dict(seedModel),
        'para' : Para,
        'list' : myMembers.getList(),
    }
    # print(ret)
    # print("reged a new node")
    # print(ret["para"])
    return json.dumps(ret)

# ask this new seed to reseed the network
# TODO change the consensus to seed prioritized instead of length preferred
# TODO currently is GET, change to POST later
@seed.route('/new_seed', methods=['GET'])
def flush():   
    global myMembers
    global seedModel
    global Para
    seedModel = SharedModel(layerStructure)
    globalWeight = save_weights_into_dict(seedModel)
    post_object = {
        'name' : seedName,
        'from' : myName,
        'seedWeight' : globalWeight,
        'para' : Para,
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

    seed.run(host='0.0.0.0', port=int(myPort))



