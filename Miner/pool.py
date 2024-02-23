from threading import Lock
import json
from Fiesta.Common.utils import print_log
import Fiesta.Common.config as CONFIG
from Fiesta.Miner.blockChain import FileLogger

# local model pool
# unamed version

class Pool:
    def __init__(self, logger):
        # self.lock = Lock()
        self.logger = logger
        self.pool = {}                   # local model stores as Dict<hash, local_dict> in pool
                                            # for easy comparison and index

    def add(self, new_model):           # add a local_dict
        # with self.lock:
        if new_model['hash'] in self.pool:
            return False
        else:
            if CONFIG.ONE_AUTHOR_ONE_LOCAL:
                self.__retire_author(new_model['author'])
            self.pool[new_model['hash']] = new_model
            self.file_log('add')

    def __retire_author(self, author):
        old_local = None
        for local_hash in self.pool.keys():
            if self.pool[local_hash]['author'] == author:
                old_local = local_hash
        if old_local:
            self.pool.pop(old_local)
            self.file_log('kick_stale')

    def remove(self, local_list):       # remove a List<local_dict>
        # remove the local model in the new block from my pool
        # with self.lock:
        old_size = len(self.pool)
        used_size = len(local_list)
        for local in local_list:
            if local['hash'] in self.pool:
                self.pool.pop(local['hash'])
        new_size = len(self.pool)
        print_log("pool remove", "size from {} to {}, should remove {}".format(old_size, new_size, used_size))
        self.file_log('remove')

    def flush(self):
        # with self.lock:
            self.pool = {}
            self.file_log('flush')


    def get_pool_list(self, size = 0):  # return a List<local_dict>
        # with self.lock:
        if size == 0:
            return list(self.pool.values())
        else:
            return list(self.pool.values())[0:size]
    
    def get_pool_log(self):
        content = ""
        for hash, local in self.pool.items():
            content += "{}({}) ".format(hash[0:5], local['author'][0:5])
        return content
    
    def file_log(self, tag):
        if CONFIG.LOG_POOL:
            self.logger.log("pool_" + tag, self.get_pool_log())
    
    @property
    def size(self):
        # with self.lock:
            return len(self.pool)

