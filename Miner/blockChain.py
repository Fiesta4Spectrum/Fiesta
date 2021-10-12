from threading import Lock

class Block:
    def __init__(self):
        pass
    
    def get_block_dict(self):
        return self.__dict__

class BlockChain:
    def __init__(self):
        self.lock = Lock()
        self.chain = []

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
            # TODO validate the new block
            return True