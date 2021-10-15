from threading import Lock
import json
from DecentSpec.Common.utils import log

# local model pool
# unamed version

class Pool:
    def __init__(self):
        # self.lock = Lock()
        self.pool = set()                   # local model stores as Set<JSON> in pool
                                            # for easy comparison and index

    def add(self, new_model):
        # with self.lock:
            js_model = json.dumps(new_model, sort_keys=True)
            if js_model in self.pool:
                return False
            else:
                self.pool.add(js_model)
                return True

    def remove(self, local_list):
        # remove the local model in the new block from my pool
        # with self.lock:
            used_locals = set(map(lambda x: json.dumps(x, sort_keys=True), local_list))
            old_size = len(self.pool)
            self.pool = self.pool - used_locals
            new_size = len(self.pool)
            used_size = len(used_locals)
            log("pool remove", "size from {} to {}, should remove {}".format(old_size, new_size, used_size))

    def flush(self):
        # with self.lock:
            self.pool = set()

    def get_pool_list(self):
        # with self.lock:
            return list(map(
                lambda x: json.loads(x),
                self.pool
                ))
                                            # return List<Dict> from Set<JSON>
    # TODO arrival sequency is totally lost here because we use set()
    # try to retain the arrival sequency in some way
    
    @property
    def size(self):
        # with self.lock:
            return len(self.pool)

