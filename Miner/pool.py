from threading import Lock
import json

# local model pool
# unamed version

class Pool:
    def __init__(self):
        self.lock = Lock()
        self.pool = set()                   # local model stores as Set<JSON> in pool
                                            # for easy comparison and index

    def add(self, new_model):
        with self.lock:
            js_model = json.dumps(new_model, sort_keys=True)
            if js_model in self.pool:
                return False
            else:
                self.pool.add(js_model)
                return True

    def remove(self, local_list):
        # TODO
        # remove the local model in the new block from my pool
        pass

    def flush(self):
        with self.lock:
            self.pool = set()

    def get_pool_list(self):
        with self.lock:
            return list(map(
                lambda x: json.loads(x),
                self.pool
                ))
                                            # return List<Dict> from Set<JSON>
    
    def size(self):
        with self.lock:
            return len(self.pool)

# TODO use a two layer structure
# local model is companied with its hash