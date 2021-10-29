# FILE LOG ENABLE
LOG_POOL = False
LOG_MINER = True
LOG_CHAIN = True
LOG_REWARD = True

# COMMON 
DEFAULT_NAME_LENGTH = 10
SEED_ADDR = "http://127.0.0.1:5000"
POW_ENABLE = True # false will disable the difficulty check which we do not care hash anymore
REPRODUCIBILITY = True

# @EDGE_SIM related 
EDGE_TRAIN_INTERVAL = 1     # seconds between two round
MAX_UPLOAD_DELAY = 0        # seconds of max delay before upload trained local, 0 for no delay
MAX_INIT_DELAY = 0         # seconds of max delay before init an edge device, 0 for no delay

# @MINER related 
MINER_REG_INTERVAL = 19
GENESIS_HASH = "genesis_hash"
BLOCK_GEN_INTERVAL = 1      # seconds between mining
STRICT_BLOCK_SIZE = False    # True: each block size will be max except #1 = min
                            # False: each block size will be min~max, except #1 = min
ONE_AUTHOR_ONE_LOCAL = True

# @SEED server related 
SEED_CHAIN_SCAN_INTERVAL = 20     # compute reward per 20s
SEED_LEASING_COUNTDOWN = 1    # rate of leasing timer reduction
SEED_LEASING_INIT = 20
EWMA_SIMPLE = True             # policy of ewma
                                # simple: new * alpha + base * (1-alpha)
                                # complicated: (new - base) * genPenalty() + base

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
