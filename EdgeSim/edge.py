import sys
from time import sleep
import requests
import random

import torch
import torch.nn as nn
import torch.optim as optim

from DecentSpec.Common.utils import curTime, print_log, save_weights_into_dict, load_weights_from_dict, genName, genTimestamp
from DecentSpec.Common.modelTemplate import FNNModel
import DecentSpec.Common.config as CONFIG
'''
usage:
    python -m DecentSpec.EdgeSim.edge {1} {2} {3} {4} {opt-5}
    {1} - mode: test or training
    {2} - file path (train or test)
    {3} - size per round / "0" refers to full set
    {4} - round nums
    {5} - reachable minerlist
            0 : full minerlist
            n : first n miners
           -n : last n mines 
'''

DATA_PARALLEL = 8
SIMPLE_PRINT = True

task_name = None
global_gen = -1
myName = genName()

class DataFeeder:                   # emulate each round dataset feeder
    def __init__(self, filePath):
        self.st_avg = []
        self.st_dev = []
        f = open(filePath, "r")
        rawList = f.readlines()
        f.close()
        print(f"file {filePath} is read into memory")
        print(f"totally {len(rawList)} lines")
        self.fullList = list(map(   lambda x: list( map(float, x.split(" "))), 
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

def fetchList(addr):
    response = requests.get(addr + CONFIG.API_GET_MINER)
    full_list = response.json()['peers']
    if miner_access > 0:
        return full_list[:miner_access]
    elif miner_access < 0:
        return full_list[miner_access:]
    else:
        return full_list

def getLatest(addr_list):
    global task_name
    global global_gen
    while True:
        while True:
            addr = random.choice(addr_list)
            try:
                response = requests.get(addr + CONFIG.API_GET_GLOBAL)
                break
            except requests.exceptions.ConnectionError:
                print_log("requests", "fails to connect to" + addr)
                continue
        data = response.json()
        new_task_name = data['seed_name']
        new_global_gen = data['generation']
        if new_task_name != task_name or new_global_gen > global_gen:
            break
        print("spin because {} is an old guy".format(addr))
        sleep(CONFIG.EDGE_TRAIN_INTERVAL)
    task_name = new_task_name
    global_gen = new_global_gen
    
    print("will perform on task<{}> of gen<{}>".format(task_name, global_gen))
    return data['weight'], data['preprocPara'], data['trainPara'], data['layerStructure']

def pushTrained(size, lossDelta, weight, addr_list):

    MLdata = {
        'stat' : {  'size' : size,
                    'lossDelta' : lossDelta,},
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

class getDataSet(torch.utils.data.Dataset):
    def __init__(self, myList, layerStructure):
        self.myList = myList
        self.inputSize = layerStructure[0]
        self.outputSize = layerStructure[-1]

    def __getitem__(self, index):
        row = self.myList[index]
        input_tensor = torch.tensor(row[:self.inputSize])
        output_tensor = torch.tensor(row[self.inputSize: self.inputSize + self.outputSize])
        return input_tensor, output_tensor

    def __len__(self):
        return len(self.myList) 

def localTraining(model, data, para, layerStructure):
    batch = para['batch']
    lrate = para['lr']
    epoch = para['epoch']
    lossf = para['loss']
    opt = para['opt']
    size = len(data)
    trainSet = getDataSet(data, layerStructure)
    trainLoader = torch.utils.data.DataLoader(  trainSet,
                                                batch_size=batch,
                                                shuffle=True,
                                                num_workers=DATA_PARALLEL)
    lossFunc = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr = lrate)

    avg_loss_begin = 0
    avg_loss_end = 0
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
        if ep == 0:
            avg_loss_begin = loss_sum/i
        if ep == epoch - 1:
            avg_loss_end = loss_sum/i

    return size, avg_loss_begin - avg_loss_end, save_weights_into_dict(model)

def localTester(model, data, para, layerStructure):
    batch = para['batch']
    lossf = para['loss']
    size = len(data)
    testSet = getDataSet(data, layerStructure)
    testLoader = torch.utils.data.DataLoader( testSet,
                                              batch_size=batch,
                                              shuffle=True,
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

    # shift in init phase
    if CONFIG.MAX_INIT_DELAY:
        sleep(random.uniform(0.0, float(CONFIG.MAX_INIT_DELAY)))
    
    localFeeder = DataFeeder(train_file)
    while localFeeder.haveData() and (rounds > 0):
    # full life cycle of one round ==============================
        rounds -= 1
        # miner communication
        minerList = fetchList(CONFIG.SEED_ADDR)
        modelWeights, preprocPara, trainPara, layerStructure = getLatest(minerList)
        # model init, should have built according to miner response
        myModel = FNNModel(layerStructure)
        load_weights_from_dict(myModel, modelWeights)
        # data preprocessing setup
        localFeeder.setPreProcess(preprocPara)
        # local training
        size, lossDelta, weight = localTraining(myModel, localFeeder.fetch(fetch_size_per), trainPara, layerStructure)
        # print(myModel.state_dict())
        # send back to server
        # shipf in upload phase
        if CONFIG.MAX_UPLOAD_DELAY:
            sleep(random.uniform(0.0, float(CONFIG.MAX_UPLOAD_DELAY)))
        pushTrained(size, lossDelta, weight, minerList)
    # end of the life cycle =====================================

    print("local dataset training done!")
    # TODO loss estimation and map visualization

def test_mode(test_file):
    global fetch_size_per
    global rounds

    localFeeder = DataFeeder(test_file)
    while localFeeder.haveData() and (rounds > 0): # add one round to enable the init global model evaluate
        rounds -= 1
        # miner communication
        minerList = fetchList(CONFIG.SEED_ADDR)
        modelWeights, preprocPara, trainPara, layerStructure = getLatest(minerList)
        # model init, should have built according to miner response
        myModel = FNNModel(layerStructure)
        load_weights_from_dict(myModel, modelWeights)
        # data preprocessing setup
        localFeeder.setPreProcess(preprocPara)
        # local test
        loss = localTester(myModel, localFeeder.fetch(fetch_size_per), trainPara, layerStructure)
        print_loss(loss)
        # TODO some test

def print_loss(loss):
    output_path = "DecentSpec/Test/test_loss_{}.txt".format(myName)
    with open(output_path, "a+") as f:
        if SIMPLE_PRINT:
            f.write("{}\n".format(loss))
        else:
            f.write("[{}] [{} @ gen {}]\n{}\n\n".format(curTime(), task_name, global_gen, loss))


# main =======================================================

print("***** NODE init, I am edge {} *****".format(myName))

fetch_size_per = 0
rounds = 0
mode = "none"
miner_access = 0

if len(sys.argv) >= 5:
    mode = sys.argv[1]
    file_path = sys.argv[2]
    fetch_size_per = int(sys.argv[3])
    rounds = int(sys.argv[4])
    if len(sys.argv) == 6:
        miner_access = int(sys.argv[5])
else:
    print("unrecognized command")

if mode == "test":
    print("***   will use file <{}> perform TEST  ***".format(file_path))
    test_mode(file_path)
elif mode == "train": 
    print("***   will use File <{}> perform TRAIN  ***".format(file_path))
    train_mode(file_path)
else:
    print("unrecognized command")



