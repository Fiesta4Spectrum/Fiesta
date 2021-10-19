from threading import Lock
from copy import deepcopy
from DecentSpec.Common.utils import curTime, dict2tensor, difficultyCheck, hashValue, genTimestamp, tensor2dict, print_log
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
        self.difficulty = para.difficulty
        self.seed_name = para.seed_name         # since every miner has a copy of the full seed parameters in myPara
                                                # full aggregation parameters is replaced with the seed name, which is shorter

        # local models
        self.local_list = local_list
        if not template:
            self.local_hash = hashValue(local_list) # the replacement for full local list when hashing
        else:
            self.local_hash = None
        
        # global model
        self.base_global = base_weight
        if not template:
            self.new_global = Block.ewma_mix(self.local_list, self.base_global, para.alpha)
        else:
            self.new_global = None
    
    def get_block_dict(self, shrank, with_hash=True):
        shrank_block = self.__dict__.copy()
        if not with_hash:
            shrank_block.pop('hash')
        if shrank:
            shrank_block.pop('local_list')
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

    @staticmethod
    def size_in_char(block):
        content = str(block.__dict__)
        return len(content)

    @staticmethod
    def ewma_mix(local_list, base, alpha):
        if local_list == None or len(local_list) < 1 or base == None:
            return None
        base_tensor = dict2tensor(base)
        locals_with_size = []
        total_size = 0
        for local in local_list:
            if local['type'] == 'localModelWeight':
                MLdata = local['content']
                size = MLdata['stat']['size']
                total_size += size
                locals_with_size.append(
                    (size, dict2tensor(MLdata['weight']))
                )

        averaged_weight = {}
        for k in locals_with_size[0][1].keys():
            
            for i in range(0, len(locals_with_size)):
                local_size, local_weight = locals_with_size[i]
                w = local_size / total_size
                if i==0:
                    averaged_weight[k] = local_weight[k] * w
                else:
                    averaged_weight[k] += local_weight[k] * w
            averaged_weight[k] = (1-alpha) * base_tensor[k] + alpha * averaged_weight[k]
        return tensor2dict(averaged_weight)

class FileLogger:
    def __init__(self, name):
        self.name = "DecentSpec/Test/log_{}.txt".format(name)
        self.zero = 0
    def log(self, tag, content):
        with open(self.name, "a+") as f:
            f.write("{:.5f} [{}] \n{}\n\n".format(genTimestamp() - self.zero, tag, content))
    def calibrate(self):
        with open(self.name, "a+") as f:
            f.write("start from: {}\n\n".format(curTime()))
        self.zero = genTimestamp()

class BlockChain:
    def __init__(self, logger):
        # self.lock = Lock()
        self.chain = []
        self.logger = logger

    def create_genesis_block(self, para):
        genesis_block = Block([], CONFIG.GENESIS_HASH, 0, 0, para, para.seeder, None)
        genesis_block.new_global = para.init_weight
        genesis_block.hash = genesis_block.compute_hash()
        self.chain.append(genesis_block)
        self.file_log('genesis')

    def flush(self):
        # with self.lock:
            self.chain = []
            self.file_log('flush')
    
    def replace(self, new_chain):
        # with self.lock:
            self.chain = new_chain
            self.file_log('replace')

    
    def get_chain_list(self):
        # with self.lock:
            chain_data = []
            for block in self.chain:
                chain_data.append(block.get_block_dict(shrank=False))
            return chain_data
    
    def get_chain_log(self):
        output = ""
        for block in self.chain:
            output +=  "{}({}){}[{},{}] ".format(block.prev_hash[:5], block.miner[:5], block.hash[:5], len(block.local_list), Block.size_in_char(block))
        return output
    
    def file_log(self, tag):
        if CONFIG.LOG_CHAIN:
            self.logger.log("chain_" + tag, self.get_chain_log())

    @property
    def last_block(self):
        # with self.lock:
            if len(self.chain) == 0:
                return None
            return self.chain[-1]
    
    @property
    def difficulty(self):
        # with self.lock:
            return self.last_block.difficulty
    
    @property
    def size(self):
        # with self.lock:
            return len(self.chain)

    def valid_then_add(self, new_block):
        # with self.lock:
            my_last = self.last_block
            # continuity check
            if new_block.prev_hash != my_last.hash:
                print_log("validate block", "noncontinuous hash link")
                return False
            if new_block.index != my_last.index + 1:
                print_log("validate block", "fails for index mismatch")
                return False
            if new_block.hash != new_block.compute_hash():
                print_log("validate block", "fails for wrong hash")
                return False
            # difficulty check
            if (my_last.difficulty != new_block.difficulty) or (not difficultyCheck(new_block.hash, my_last.difficulty)):
                print_log("validate block", "fails for difficulty requirement")
                return False
            self.chain.append(new_block)
            self.file_log('grow')
            return True
