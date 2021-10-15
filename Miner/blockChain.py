from threading import Lock
from DecentSpec.Common.utils import curTime, dict2tensor, difficultyCheck, hashValue, genTimestamp, tensor2dict, log
import DecentSpec.Common.config as CONFIG

class Block:

    def __init__(self, local_list, prev_hash, time_stamp, index, para, miner, base_weight):
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
        self.local_hash = hashValue(local_list) # the replacement for full local list when hashing
        
        # global model
        self.base_global = base_weight
        self.new_global = Block.ewma_mix(self.local_list, self.base_global, para.alpha)
    
    def get_block_dict(self, shrank, with_hash=True):
        shrank_block = self.__dict__.copy()
        if not with_hash:
            shrank_block.pop('hash')
        if shrank:
            shrank_block.pop('local_list')
        return shrank_block
    
    def compute_hash(self):
        return hashValue(self.get_block_dict(shrank=True, with_hash=False))

    def get_global(self):
        return self.new_global
    
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
    def log(self, tag, content):
        with open(self.name, "a+") as f:
            f.write("[{}] {} \n{}\n\n".format(curTime(), tag, content))

class BlockChain:
    def __init__(self, name):
        # self.lock = Lock()
        self.name = name
        self.chain = []
        self.logger = FileLogger(name)

    def create_genesis_block(self, para):
        genesis_block = Block([], CONFIG.GENESIS_HASH, 0, 0, para, para.seeder, None)
        genesis_block.new_global = para.init_weight
        genesis_block.hash = genesis_block.compute_hash()
        self.chain.append(genesis_block)
        self.logger.log("genesis", self.get_chain_print())

    def flush(self):
        # with self.lock:
            self.chain = []
    
    def replace(self, new_chain):
        # with self.lock:
            self.chain = new_chain
            self.logger.log("replace", self.get_chain_print())

    
    def get_chain_list(self):
        # with self.lock:
            chain_data = []
            for block in self.chain:
                chain_data.append(block.get_block_dict(shrank=False, with_hash=True))
            return chain_data
    
    def get_chain_print(self):
        output = ""
        for block in self.chain:
            output +=  "{}({})[{}] ".format(block.hash[:8], block.miner[:5], len(block.local_list))
        return output

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
                log("validate block", "[fork alert] noncontinuous hash link")
                return False
            if new_block.index != my_last.index + 1:
                log("validate block", "fails for index mismatch")
                return False
            if new_block.hash != new_block.compute_hash():
                log("validate block", "fails for wrong hash")
                return False
            # difficulty check
            if (my_last.difficulty != new_block.difficulty) or (not difficultyCheck(new_block.hash, my_last.difficulty)):
                log("validate block", "fails for difficulty requirement")
                return False
            self.chain.append(new_block)
            self.logger.log("grow", self.get_chain_print())
            return True
