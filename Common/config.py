# COMMON 
DEFAULT_NN_STRUCTURE = [2,50,50,50,1]
DEFAULT_NAME_LENGTH = 10
SEED_ADDR = "http://api.decentspec.org:5000"
POW_ENABLE = True # false will disable the difficulty check which we do not care hash anymore
REPRODUCIBILITY = True

# @EDGE_SIM related 
RANDOM_EDGE = True # do we need to random send?
LOCAL_DATASET_FILE = "DecentSpec/Dataset/GPS-power.dat"     # data structure 
EDGE_TRAIN_INTERVAL = 1    # seconds between two round

# @MINER related 
MINER_REG_INTERVAL = 19
UNAMED_POOL = True
GENESIS_HASH = "genesis_hash"
CHAIN_LOGGER = True

# POOL_MINE_THRESHOLD = 3     # num of local models before mining
                                # get mine threshold at runtime for easy test
BLOCK_GEN_INTERVAL = 1      # seconds between mining

# @SEED server related 
SEED_CHAIN_SCAN_INTERVAL = 20     # compute reward per 20s
SEED_LEASING_COUNTDOWN = 1    # rate of leasing timer reduction
SEED_LEASING_INIT = 20

# API related

API_POST_LOCAL = '/new_transaction'
API_GET_GLOBAL = '/global_model'

API_GET_CHAIN = '/chain'                # full chain
API_GET_CHAIN_SIMPLE = '/chain_simple'  # chain size and last block, for consensus
API_GET_CHAIN_PRINT = '/chain_print'    # chain for pretty print, not implemented yet
API_POST_BLOCK = '/add_block'
API_GET_POOL = '/pending_tx'
API_UPDATE_SEED = '/seed_update'

API_GET_MINER = '/miner_peers'
API_REGISTER = '/register'
