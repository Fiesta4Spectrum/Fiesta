from copyreg import pickle
from threading import Lock, local
import os
from copy import deepcopy
from DecentSpec.Common.utils import *
import DecentSpec.Common.config as CONFIG

class Block:

    def __init__(self, local_list, prev_hash, time_stamp, index, para, miner, base_weight, template = False):
        # header
        self.prev_hash = prev_hash
        self.hash = None
        self.index = index
        self.miner = miner
        self.time_stamp = time_stamp
        self.nonce = 0


        # local models
        self.local_list = local_list
        if not template:                        # I propose a new block
            self.difficulty = para.difficulty
            self.seed_name = para.seed_name
            self.local_hash = hashValue(local_list) # the replacement for full local list when hashing
            self.new_global = Block.ewma_mix(self.local_list, base_weight, para.alpha, self.index)
        else:
            self.local_hash = None
            self.new_global = None
            self.difficulty = None
            self.seed_name = None

    
    def get_block_dict(self, shrank, with_hash=True):
        shrank_block = self.__dict__.copy()
        if not with_hash:
            shrank_block.pop('hash')
        
        if shrank:
            shrank_block.pop('local_list')
            shrank_block.pop('new_global')
        else:
            # when we need to keep the local list information
            local_list_shrank = deepcopy(self.local_list)
            for local in local_list_shrank:
                if local['type'] == 'localModelWeight':
                    local['content']['weight'] = None
            shrank_block['local_list'] = local_list_shrank
        return shrank_block
    
    def compute_hash(self):
        return hashValue(self.get_block_dict(shrank=True, with_hash=False))

    def get_global(self):
        return self.new_global

    def print_list(self):
        printable = list(map(Block.extract_author, self.local_list))
        printable.sort()
        return "\t".join(printable)

    def delay_stat(self):
        delay = 0.0
        size = 0
        for local in self.local_list:
            if local['type'] == 'localModelWeight':
                size += 1
                if 'base_gen' in local['content']:
                    delay += self.index - local['content']['base_gen']
                else:
                    delay += 1
        return delay, size
                
    @staticmethod
    def extract_author(local_dict):
        if 'base_gen' in local_dict['content']:
            base_gen = local_dict['content']['base_gen']
        else:
            base_gen = "?"
        if 'upload_index' in local_dict:
            index = local_dict['upload_index']
        else:
            index = "?"
        return "{}-{}-{}".format(base_gen, local_dict['author'][:3], index)

    @staticmethod
    def size_in_char(block):
        content = str(block.__dict__)
        return len(content)

    @staticmethod
    def ewma_mix(local_list, base, alpha, cur_gen):
        if local_list == None or len(local_list) < 1 or base == None:
            return None
        base_tensor = dict2tensor(base)
        locals_with_size = []
        total_size = 0
        for local in local_list:
            if local['type'] == 'localModelWeight':
                MLdata = local['content']
                size = MLdata['stat']['size']
                if 'base_gen' in MLdata:
                    base_gen = MLdata['base_gen']
                else:
                    base_gen = cur_gen - 1  # default as the freshest
                total_size += size
                locals_with_size.append(
                    (size, dict2tensor(MLdata['weight']), base_gen)
                )

        averaged_weight = {}
        for k in locals_with_size[0][1].keys():
            
            for i in range(0, len(locals_with_size)):
                local_size, local_weight, local_base_gen = locals_with_size[i]
                w = local_size / total_size
                twisted_local_k = base_tensor[k] + (local_weight[k] - base_tensor[k]) * Block.ewma_gen_penalty(cur_gen - local_base_gen, alpha)
                if i==0:
                    averaged_weight[k] = twisted_local_k * w
                else:
                    averaged_weight[k] += twisted_local_k * w
        return tensor2dict(averaged_weight)

    @staticmethod
    def ewma_gen_penalty(gap, alpha):
        if CONFIG.EWMA_SIMPLE:
            return alpha
        return alpha ** abs(gap-1)
    
    @staticmethod
    def gen_global_loss(block):
        local_list = block.local_list
        sum_loss = 0.0
        total_size = 0
        for local in local_list:
            if local['type'] == 'localModelWeight':
                MLdata = local['content']
                size = MLdata['stat']['size']
                sum_loss += MLdata['stat']['trainedLoss'] * size
                total_size += size
        if total_size == 0:
            return 0
        return sum_loss / total_size

class FileLogger:
    def __init__(self, name):
        os.makedirs(CONFIG.LOG_DIR, exist_ok=True)
        self.__log_path = CONFIG.LOG_DIR + "miner_{}.txt".format(name)
        self.__chain_path = CONFIG.LOG_DIR + "chain_{}.txt".format(name)
        self.zero = 0
        self.name = name
        self.seed_dir = ""
    def switch(self, new_seed):
        self.seed_dir = new_seed + "/"
    def print_chain(self, chain):
        with open(self.__chain_path, "w+") as f:
            f.write("#\tP-Hash\tHash\tMiner\tLoss\tTime\t\tLocal_weights\n")
            sum_delay = 0.0
            sum_size = 0
            for block_name in chain:
                block = loadBlock_pub(CONFIG.BLOCK_DIR + self.name + "/" + self.seed_dir, block_name)
                f.write("{}\t{}\t{}\t{}\t{:.4f}\t{}\t{}\n".format(block.index, block.prev_hash[:6], block.hash[:6], block.miner[:6], Block.gen_global_loss(block), int(block.time_stamp), block.print_list()))
                delay, size = block.delay_stat()
                sum_delay += delay
                sum_size += size
            if size > 0 :
                f.write("\nAvg gap between Base-block and Includer-block is {:.2f}\n".format(sum_delay / sum_size))
    def log(self, tag, content):
        with open(self.__log_path, "a+") as f:
            f.write("{} [{}] \n{}\n\n".format(curTime(), tag, content))
    def calibrate(self):
        with open(self.__log_path, "a+") as f:
            f.write("start from: {}\n".format(curTime()))
        self.zero = genTimestamp()

class ChainState:
    def __init__(self, chain, seed):
        self.chain = chain
        self.seed_dir = seed

class BlockChain:
    def __init__(self, logger):
        self.lock = Lock()
        self.logger = logger
        self.seed_dir = ""
        self.chain = []
    
    @property
    def block_dir(self):
        return CONFIG.BLOCK_DIR + self.logger.name + "/" + self.seed_dir

    def dumpBlock(self, new_block):
        file_name = genBlockFileName(new_block)
        if os.path.isfile(self.block_dir + file_name):
            return file_name
        with open(self.block_dir + file_name, "wb+") as f:
            pickle.dump(new_block, f)
        return file_name

    def loadBlock(self, file_name):
        with open(self.block_dir + file_name, "rb") as f:
            my_block = pickle.load(f)
        return my_block


    def create_genesis_block(self, para):
        with self.lock:
            genesis_block = Block([], CONFIG.GENESIS_HASH, 0, 0, para, para.seeder, None)
            genesis_block.new_global = para.init_weight
            genesis_block.hash = genesis_block.compute_hash()
            self.logger.log('NEW CHAIN', 'new chain injected, flush chain, but block file is reserved')
            self.chain = [self.dumpBlock(genesis_block)]
            self.file_log('genesis')
            self.update_chain_print()

    def flush(self):
        with self.lock:
            self.chain = []
            # cleanDir(self.block_dir)
            self.file_log('flush')
    
    def switch(self, new_seed):
        self.seed_dir = new_seed + "/"
        self.logger.switch(new_seed)
        os.makedirs(self.block_dir, exist_ok=True)

    # old implement based on block list
    # def replace(self, new_chain, rm_base_global = False):
    #     self.chain = []
    #     # replace only happens when outcoming chain shares the same seed_name with my old chain
    #     # no switch is needed
    #     for block in new_chain:
    #         if rm_base_global:
    #             try:
    #                 block.delattr('base_global')
    #             except:
    #                 pass
    #         self.chain.append(self.dumpBlock(block))
    #     self.file_log('replace')
    #     self.update_chain_print()

    # new implement based on fetcher
    def replace(self, new_fetcher):
        new_chain = new_fetcher.chain()
        if new_chain == None:
            print_log("chain replace", "fails")
            return
        for i in range(0, len(new_chain)):
            if (self.size <= i) or (self.chain[i] != new_chain[i]):
                break
        self.chain = self.chain[:i]
        new_fetcher.set(i)
        for block in new_fetcher:
            if not self.valid_then_add(extract_block_from_dict(block), log_enable=False):
                break
        print_log("chain replace", "replace chain from #{} - #{}".format(i, len(self.chain) - 1))
        
        self.file_log('replace')
        self.update_chain_print()

    def get_chain_details(self):
        chain_data = []
        for block_name in self.chain:
            chain_data.append(self.loadBlock(block_name).get_block_dict(shrank=False))
        return chain_data
    
    def get_chain_brief(self):
        # output = ""
        # for block_name in self.chain:
        #     block = self.loadBlock(block_name)
        #     output +=  "{}({}){}[{},{}] ".format(block.prev_hash[:5], block.miner[:5], block.hash[:5], len(block.local_list), Block.size_in_char(block))
        output = " ".join(self.chain)
        return output
    
    def file_log(self, tag):
        if CONFIG.LOG_MINER:
            self.logger.log("chain_" + tag, self.get_chain_brief())
    
    def update_chain_print(self):
        if CONFIG.LOG_CHAIN:
            self.logger.print_chain(self.chain)

    @property
    def last_block(self):
        if len(self.chain) == 0:
            return None
        return self.loadBlock(self.chain[-1])
    
    @property
    def difficulty(self):
        return self.last_block.difficulty
    
    @property
    def size(self):
        return len(self.chain)

    def valid_then_add(self, new_block, log_enable=True):
        if new_block == None:
            return False
        with self.lock:
            my_last = self.last_block
            # continuity check
            if new_block.prev_hash != my_last.hash:
                print_log("validate block", "noncontinuous hash link, my latest is #{}, received #{}".format(my_last.index, new_block.index))
                return False
            if new_block.index != my_last.index + 1:
                print_log("validate block", "fails for index mismatch, my latest is #{} received #{}".format(my_last.index, new_block.index))
                return False
            if new_block.hash != new_block.compute_hash():
                print_log("validate block", "fails for wrong hash")
                return False
            # difficulty check
            if (my_last.difficulty != new_block.difficulty) or (not difficultyCheck(new_block.hash, my_last.difficulty)):
                print_log("validate block", "fails for difficulty requirement")
                return False            
            self.chain.append(self.dumpBlock(new_block))
            if log_enable:
                self.file_log('grow')
                self.update_chain_print()
        return True

def extract_block_from_dict(resp):
    if resp == None:
        return None
    template = Block(
        resp['local_list'],
        resp['prev_hash'],
        resp['time_stamp'],
        resp['index'],
        None,       # myPara as a placeholder here
        resp['miner'],
        None,       # base global is none: it is a block from outside, template must be true
        template=True
    )
    template.hash = resp['hash']
    template.nonce = resp['nonce']
    template.difficulty = resp['difficulty']
    template.seed_name = resp['seed_name']

    template.local_hash = resp['local_hash']
    template.new_global = resp['new_global']

    return template