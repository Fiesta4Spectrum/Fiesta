import sys
from time import sleep
import requests
import random

import torch
import torch.nn as nn
import torch.optim as optim

from DecentSpec.Common.utils import curTime, print_log, save_weights_into_dict, load_weights_from_dict, genName, genTimestamp, sincos_encode
from DecentSpec.Common.modelTemplate import FNNModel
import DecentSpec.Common.config as CONFIG
'''
usage:
    python -m DecentSpec.EdgeSim.edge {0} {1} {2} {3} {4} {opt-5}
    {0} - seed node address
    {1} - mode: test or training
    {2} - file path (train or test)
    {3} - size per round / "0" refers to full set
    {4} - round nums
    {5} - gen_text.py script will not gen this para,
            it is only for manual experiment
            (1) reachable minerlist 
                R0 : full minerlist
                Rn : first n miners
                R-n : last n mines
            (2) async set tsundere value
                Tn : tsundere = n
'''

DATA_PARALLEL = 8
SIMPLE_PRINT = True
LR_DECAY = 1

myName = genName()

def string2floatList(raw_string, tail_dup):
    ret = list( map(float, raw_string.split(" ")))
    if tail_dup == 0:
        return ret
    tail = ret[-1]
    for i in range(0, tail_dup):
        ret.append(tail)
    return ret
    

class DataFeeder:                   # emulate each round dataset feeder
    def __init__(self, filePath, tail_dup = 0):
        self.st_avg = []
        self.st_dev = []
        f = open(filePath, "r")
        rawList = f.readlines()
        f.close()
        print(f"file {filePath} is read into memory")
        print(f"totally {len(rawList)} lines")
        self.fullList = list(map(   lambda x : string2floatList(x, tail_dup), 
                                    rawList))
        self.ctr = 0
    def setPreProcess(self, para):
        # set the pre-process para
        # check the data format compatibility
        # for key in para.keys():
        #     self.st_avg.append(para[key][0])    # average
        #     self.st_dev.append(para[key][1])    # std deviation
        self.st_avg = para["avg"].copy()    # average
        self.st_dev = para["std"].copy()    # std deviation
    def _preproc(self, partialList):
        st_list = []
        for i, line in enumerate(partialList):
            st_line = []
            # print("sizeof avg {}, sizeof dev {}, sizeof single line {}".format(len(self.st_avg), len(self.st_dev), len(line)))
            for j, item in enumerate(line):
                st_line.append( (item - self.st_avg[j])/self.st_dev[j] )
            st_list.append(st_line)
        return st_list
    def fetch(self, size):
        if size == 0:
            return self._preproc(self.fullList)
        # return a dataset of UNCERTAIN size everytime
        partialList = self.fullList[self.ctr:self.ctr+size]
        self.ctr += size
        return self._preproc(partialList)
    def haveData(self):
        return self.ctr < len(self.fullList)
        # does this emulator have further dataset
    @property
    def size(self):
        return len(self.fullList)

def fetch_list(addr):

    while True:
        try:
            response = requests.get(addr + CONFIG.API_GET_MINER)
            break
        except requests.exceptions.ConnectionError:
            print_log("requests", "fails to connect to seed")
            continue

    full_list = response.json()['peers']
    full_list.sort()
    if miner_access > 0:
        return full_list[:miner_access]
    elif miner_access < 0:
        return full_list[miner_access:]
    else:
        return full_list

def get_valid_global(addr_list):

    sleep(CONFIG.EDGE_HTTP_INTERVAL)
    while True:
        addr = random.choice(addr_list)
        try:
            response = requests.get(addr + CONFIG.API_GET_GLOBAL)
            break
        except requests.exceptions.ConnectionError:
            print_log("requests", "fails to connect to" + addr)
            continue
    return response.json()

def get_latest(addr_list):
    global task_name
    global global_gen
    global mode

    while True:
        data = get_valid_global(addr_list)
        new_task_name = data['seed_name']
        new_global_gen = data['generation']

        if new_task_name != task_name or new_global_gen - global_gen >= 1:          
            # accept global if it is a new task
            break
        print_log("spin", "current global has been {}ed".format(mode))

    task_name = new_task_name
    global_gen = new_global_gen
    
    return data['weight'], data['preprocPara'], data['trainPara'], data['layerStructure']

def push_trained(size, lossDelta, loss, weight, addr_list, index):
    global LR_DECAY
    if CONFIG.AUTO_SUPPRESS and lossDelta < 0:
        return
    if lossDelta < 0:
        LR_DECAY = 0.1 # decay the LR in the next round
    # else:
    #     LR_DECAY = 1
    MLdata = {
        'stat' : {  'size' : size,
                    'lossDelta' : lossDelta,
                    'trainedLoss' : loss},
        'weight' : weight,
        'base_gen' : global_gen,
    }
    global myName
    data = {
        'author' : myName,
        'content' : MLdata,
        'timestamp' : genTimestamp(),
        'type' : 'localModelWeight',
        'plz_spread' : 1,
        'upload_index' : index, # the i-th local weights uploaded by this edge, starts from 1
        'seed_name' : task_name,
    }
    while True:
        addr = random.choice(addr_list)
        try:
            requests.post(addr + CONFIG.API_POST_LOCAL, json=data)
            break
        except requests.exceptions.ConnectionError:
            print_log("requests", "fails to connect to" + addr)
            continue

    # send to server

class get_data_set(torch.utils.data.Dataset):
    def __init__(self, myList, layerStructure):
        self.myList = myList
        self.inputSize = layerStructure[0]
        self.outputSize = layerStructure[-1]

    def __getitem__(self, index):
        row = self.myList[index]
        input_tensor = torch.tensor(sincos_encode(row[:self.inputSize], L=CONFIG.POSITIONAL_ENCODE))
        output_tensor = torch.tensor(row[self.inputSize: self.inputSize + self.outputSize])
        return input_tensor, output_tensor

    def __len__(self):
        return len(self.myList) 

def local_training(model, data, para, layerStructure):
    batch = para['batch']
    lrate = para['lr'] * LR_DECAY
    epoch = para['epoch']
    lossf = para['loss']
    opt = para['opt']
    size = len(data)
    trainSet = get_data_set(data, layerStructure)
    trainLoader = torch.utils.data.DataLoader(  trainSet,
                                                batch_size=batch,
                                                shuffle=True,
                                                num_workers=DATA_PARALLEL)
    lossFunc = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr = lrate)

    # avg_loss_begin = local_tester(model, data, para, layerStructure)
    # print(f"[before epoch]\t[avg loss]\t{avg_loss_begin}")

    avg_loss_begin = 0
    cur_avg_loss = 0
    prev_avg_loss = sys.float_info.max
    print("local learning rate decay: {}".format(LR_DECAY))
    model.train()
    for ep in range(epoch):
        loss_sum = 0.0
        for i, data in enumerate(trainLoader, 0):
            inputs, truth = data
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = lossFunc(outputs, truth)
            loss.backward()
            optimizer.step()
            loss_sum += loss.item()
        print(f"[epoch {ep+1}]\t[avg loss]\t{loss_sum/i}")
        cur_avg_loss = loss_sum/i
        if ep == 0:
            avg_loss_begin = cur_avg_loss
        if prev_avg_loss < cur_avg_loss:
            break
        prev_avg_loss = cur_avg_loss

    return size, avg_loss_begin - cur_avg_loss, cur_avg_loss, save_weights_into_dict(model)

def local_tester(model, data, para, layerStructure):
    batch = para['batch']
    lossf = para['loss']
    size = len(data)
    testSet = get_data_set(data, layerStructure)
    testLoader = torch.utils.data.DataLoader( testSet,
                                              batch_size=batch,
                                              shuffle=False,
                                              num_workers=DATA_PARALLEL)
    lossFunc = nn.MSELoss()
    with torch.no_grad():
        model.eval()
        loss_sum = 0.0
        for i, data in enumerate(testLoader, 0):
            inputs, truth = data
            outputs = model(inputs)
            loss = lossFunc(outputs, truth)
            loss_sum += loss.item()
    return loss_sum / i

def train_mode(train_file):
    global fetch_size_per
    global rounds
    global task_name
    global global_gen
    global mode
    global forever_flag
    global seed_addr

    localFeeder = DataFeeder(train_file)
    index = 0
    while (localFeeder.haveData() and (rounds > 0)) or forever_flag:
    # full life cycle of one round ==============================
        if not forever_flag:
            rounds -= 1
        index += 1

        # miner communication
        minerList = fetch_list(seed_addr)
        modelWeights, preprocPara, trainPara, layerStructure = get_latest(minerList)
        print("performing {}-th {} based on task {} # {}".format(index, mode, task_name, global_gen))

        # async simulation
        if CONFIG.ASYNC_SIM:
            tsundere_is_moe(minerList)

        # model init, should have built according to miner response
        myModel = FNNModel(layerStructure)
        load_weights_from_dict(myModel, modelWeights)

        # data preprocessing setup
        if (layerStructure[-1] == 8):       # tv to multi tv will change the output layer from 1 to 8
            # localFeeder = DataFeeder(train_file, tail_dup = layerStructure[-1] - 1)
            localFeeder = DataFeeder(train_file)
        else:
            localFeeder = DataFeeder(train_file)
        localFeeder.setPreProcess(preprocPara)

        # local training
        size, lossDelta, loss, weight = local_training(myModel, localFeeder.fetch(fetch_size_per), trainPara, layerStructure)

        # send back to server
        push_trained(size, lossDelta, loss, weight, minerList, index)
    # end of the life cycle =====================================

    print("local dataset training done!")
    # TODO loss estimation and map visualization

def tsundere_is_moe(addr_list):
    global tsundere
    if tsundere <= 1:
        sleep(random.uniform(0.0, 2.0))     # sleep to balance with the 1s http_requests_interval granularity
        return
    latest_global = get_valid_global(addr_list)
    while latest_global['generation'] - global_gen < tsundere - 1:
        print_log("spin", "I am a tsundere")
        latest_global = get_valid_global(addr_list)
    

def test_mode(test_file):
    global fetch_size_per
    global rounds
    global seed_addr

    index = 0
    localFeeder = DataFeeder(test_file)
    while forever_flag or rounds > 0: # none-stop test
        if not forever_flag:
            rounds -= 1
        index += 1
        # miner communication
        minerList = fetch_list(seed_addr)
        modelWeights, preprocPara, trainPara, layerStructure = get_latest(minerList)
        print("performing {}-th {} based on task {} # {}".format(index, mode, task_name, global_gen))

        # model init, should have built according to miner response
        myModel = FNNModel(layerStructure)
        load_weights_from_dict(myModel, modelWeights)

        # data preprocessing setup
        localFeeder.setPreProcess(preprocPara)

        # local test
        loss = local_tester(myModel, localFeeder.fetch(fetch_size_per), trainPara, layerStructure)
        print_loss(loss)

def print_loss(loss):
    output_path = "DecentSpec/Test/test_loss_{}.txt".format(myName)
    with open(output_path, "a+") as f:
        if SIMPLE_PRINT:
            f.write("{}\n".format(loss))
        else:
            f.write("[{}] [{} @ gen {}]\n{}\n\n".format(curTime(), task_name, global_gen, loss))


# main =======================================================

print("***** NODE init, I am edge {} *****".format(myName))

task_name = None
global_gen = -1
fetch_size_per = 0
rounds = 0
mode = "none"
miner_access = 0
tsundere = 1    # TsuNDeRe 蹭的累
                # perform next training 
                # only after the global grow up "tsundere"'s gen more!

if len(sys.argv) >= 6:
    seed_addr = sys.argv[1]
    mode = sys.argv[2]
    file_path = sys.argv[3]
    fetch_size_per = int(sys.argv[4])
    rounds = int(sys.argv[5])
    forever_flag = rounds == 0
    if len(sys.argv) == 7:
        if sys.argv[6].startswith("R"):
            miner_access = int(sys.argv[6][1:])
        elif sys.argv[6].startswith("T"):
            tsundere = int(sys.argv[6][1:])
        
else:
    print("unrecognized command")

if mode == "test":
    print("***   will use file <{}> perform TEST  ***".format(file_path))
    tsundere = 1 # force the threshold of tsundere to 1 for test instance
    test_mode(file_path)
elif mode == "train": 
    print("***   will use File <{}> perform TRAIN  ***".format(file_path))
    train_mode(file_path)
else:
    print("unrecognized command")



