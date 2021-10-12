from threading import Lock
from DecentSpec.Common.utils import dict2tensor, hashValue, genTimestamp, tensor2dict, log
import DecentSpec.Common.config as CONFIG

class Block:

    def __init__(self, local_list, prev_hash, time_stamp, index, para, miner):
        # header
        self.prev_hash = prev_hash
        self.hash = None
        self.index = index
        self.miner = miner
        self.timestamp = time_stamp
        self.nonce = 0
        self.difficulty = para.difficulty
        self.seed_name = para.seed_name         # since every miner has a copy of the full seed parameters in myPara
                                                # full aggregation parameters is replaced with the seed name, which is shorter

        # local models
        self.local_list = local_list
        self.local_hash = hashValue(local_list) # the replacement for full local list when hashing
        
        # global model
        self.base_global = para.init_weight
        self.new_global = Block.ewma_mix(self.local_list, self.base_global, para.alpha)
    
    def get_block_dict(self, shrank=False, with_hash=False):
        shrank_block = self.__dict__.copy()
        if not with_hash:
            shrank_block.pop('hash')
        if shrank:
            shrank_block.pop('local_list')
        return shrank_block
    
    def compute_hash(self):
        return hashValue(self.get_block_dict(shrank=CONFIG.FAST_HASH, with_hash=False))

    def get_global(self):
        return self.new_global
    
    @staticmethod
    def ewma_mix(local_list, base, alpha):
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
        if len(locals_with_size) < 1:
            return None
        averaged_weight = {}
        for k in locals_with_size[0][1].keys():
            
            for i in range(0, len(locals_with_size)):
                local_size, local_weight = locals_with_size[i]
                w = local_size / total_size
                if i==0:
                    averaged_weight[k] = local_weight[k] * w
                else:
                    averaged_weight[k] += local_weight[k] * w
            averaged_weight[k] = (1-alpha) * base[k] + alpha * averaged_weight[k]
        return tensor2dict(averaged_weight)

class BlockChain:
    def __init__(self):
        self.lock = Lock()
        self.chain = []

    def create_genesis_block(self, para):
        genesis_block = Block([], CONFIG.GENESIS_HASH, 0, 0, para, para.seeder)
        genesis_block.hash = genesis_block.compute_hash()
        self.chain.append(genesis_block)

    def flush(self):
        with self.lock:
            self.chain = []
    
    def get_chain_list(self):
        with self.lock:
            chain_data = []
            for block in self.chain:
                chain_data.append(block.get_block_dict())
            return chain_data

    def last_block(self):
        with self.lock:
            return self.chain[-1]
    
    def size(self):
        with self.lock:
            return len(self.chain)

    def valid_then_add(self, new_block):
        with self.lock:
            my_last = self.last_block()
            # continuity check
            if new_block.index != my_last.index + 1:
                log("add block", "fails for index mismatch")
                return False
            if new_block.prev_hash != my_last.hash:
                log("add block", "fails for hash link mismatch")
                return False
            if new_block.hash != new_block.compute_hash():
                log("add block", "fails for wrong hash")
                return False
            # difficulty check
            if (my_last.difficulty != new_block.difficulty) or (not new_block.hash.startswith('0' * my_last.difficulty)):
                log("add block", "fails for difficulty requirement")
                return False
            self.chain.append(new_block)
            return True