'''
a simulator of database in memory
might change to a real db lib later
'''

# TODO add lock for the database

from threading import Thread, Lock
import time
import requests
import pickle
import os

import Fiesta.Common.config as CONFIG
from Fiesta.Common.utils import ChainFetcher, genPickleName, genName, print_log

class MinerDB:
    def __init__(self):
        self.key = []     # primary key, the name of the seed or its pub key
        self.addr = []    # first entry, ip addr with port
        self.role = []    # second entry, role
        # the role, might be "miner" or "seed" or "admin" (mother seed)

        '''
        currently only implement a permanent registration, no timer
        '''
        self.timer = []   # third entry, timer
        # TODO: define the lock to protect those entries
        self.__runTick()  # init the timer ticking for leasing

    def getList(self):
        return self.addr
    
    @property
    def size(self):
        return len(self.key)

    def regNew(self, key, addr, role="miner"):
        if not (key in self.key):       # if a new reg
            self.key.append(key)
            self.addr.append(addr)
            self.role.append(role)
            self.timer.append(CONFIG.SEED_LEASING_INIT)
        else:
            idx = self.key.index(key)
            self.addr[idx] = addr
            self.role[idx] = role
            self.timer[idx] = CONFIG.SEED_LEASING_INIT
        return 0

    def tick(self):
        while True:
            self.timer = list(map(lambda x:x-1, self.timer))
            # TODO a small bug here
            # can not use for to 
            i = 0
            while i < self.size:
                if self.timer[i] < 0:
                    self.key.pop(i)
                    self.addr.pop(i)
                    self.role.pop(i)
                    self.timer.pop(i)
                else:
                    i = i + 1
            time.sleep(CONFIG.SEED_LEASING_COUNTDOWN) 

    def __runTick(self):    # we do not use it currently
        tick_thread = Thread(target=self.tick)
        tick_thread.setDaemon(True)
        tick_thread.start()
    
    def showMember(self, idx):
        return self.key[idx] + '\t' + self.addr[idx] + '\t' + str(self.timer[idx])

class Contributor:
    DELTA_THRESHOLD = 0.0
    def __init__(self, key, role):
        self.key = key
        self.role = role
        self.mined_block = 0
        self.shared_weight = 0
        self.total_size = 0
        self.reward = 0
    def submit(self, size, lossDelta):
        self.shared_weight += 1
        # print("get a local update with size {} and loss {}".format(size, lossDelta))
        if lossDelta > Contributor.DELTA_THRESHOLD:
            self.reward += int(size) * float(lossDelta)
            self.total_size += int(size)
    def mine(self):
        self.mined_block += 1
    def showContribution(self):
        return  self.key + '\t' + self.role + ' \t' + \
                str(self.mined_block) + '   \t' + \
                str(self.shared_weight) + '    \t' + \
                str(self.total_size) + '  \t' + str(self.reward)

class RewardDB:
    def __init__(self, MinerDB, para, name):
        self.rewardDict = {}
        self.name = name
        self.fileName = CONFIG.LOG_DIR + "reward_{}.txt".format(name)

        self.myMember = MinerDB # link with memberlist for scan
        self.para = para        # link with para
        self.__runscan()
    
    def __flush(self):
        self.rewardDict = {}

    def scan(self):
        while True:
            peers = self.myMember.getList()
            print("scan the memberlist to compute reward")
            time.sleep(CONFIG.SEED_CHAIN_SCAN_INTERVAL)
            current_len = 0
            fromwhom = 'nobody'
            longest_chain_fetcher = None
            for miner in peers:
                try:
                    fetcher = ChainFetcher(miner)
                    if fetcher.length > current_len:
                        current_len = fetcher.length
                        longest_chain_fetcher = fetcher
                        fromwhom = miner
                except requests.exceptions.ConnectionError:
                    print_log("requests", "fails to connect to " + miner)
            print("longest chain from {} with length {}".format(fromwhom, current_len))
            if longest_chain_fetcher == None:
                continue
            if current_len > 0:
                latest_global_weight = longest_chain_fetcher.get(-1)['new_global']
                with open(CONFIG.PICKLE_DIR + genPickleName(self.name, CONFIG.PICKLE_GLOBAL),"wb") as f:
                    pickle.dump(latest_global_weight, f)
            self.updateReward(longest_chain_fetcher)
            self.__print()
    
    def __print(self):
        print("============== Reward Database ===============")
        print("key     \trole \tmined\tupdate\tsize     \treward")
        for node in self.rewardDict:
            print(self.rewardDict[node].showContribution())
        print("============== =============== ===============")
        if CONFIG.LOG_REWARD:
            os.makedirs(CONFIG.LOG_DIR, exist_ok=True)
            with open(self.fileName, "w+") as f:
                f.write("============== Reward Database ===============\n")
                f.write("key     \trole \tmined\tupdate\tsize     \treward\n")
                for node in self.rewardDict:
                    f.write(self.rewardDict[node].showContribution() + "\n")
                f.write("============== =============== ===============\n")
    
    def updateReward(self, chain_fetcher):
        self.__flush()  # calculate reward from the very first block
        for block in chain_fetcher:
            # calculate miner contribution
            # print("the miner of this block is {}".format(block['miner']))
            key = block['miner']
            if block['index'] == 0:
                self.rewardDict[key] = Contributor(key, 'seed')
                self.rewardDict[key].mine()
                continue
            if not block['miner'] in self.rewardDict:
                self.rewardDict[key] = Contributor(key, 'miner')
            self.rewardDict[key].mine()

            for tx in block["local_list"]:
                if tx["type"] == "localModelWeight":
                    # calculate edge contribution
                    # print("the author of this update is {}".format(tx['author']))
                    key = tx['author']
                    if not tx['author'] in self.rewardDict:
                        self.rewardDict[key] = Contributor(key, 'edge')
                    self.rewardDict[key].submit(tx['content']['stat']['size'],
                                                tx['content']['stat']['lossDelta'])
    
    def query(self, id):
        if not id in self.rewardDict:
            return "stranger", 0, 0
        contri = self.rewardDict[id]
        return contri.role, contri.mined_block + contri.shared_weight, contri.reward

    def __runscan(self):
        scan_thread = Thread(target=self.scan)
        scan_thread.setDaemon(True)
        scan_thread.start()