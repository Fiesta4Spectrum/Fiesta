# FILE LOG ENABLE
LOG_DIR = "decentspec_log/"
LOG_POOL = False
LOG_MINER = True
LOG_CHAIN = True
LOG_REWARD = True

# state save realted
PICKLE_INTERVAL = 10    # reserve the miner state per 10s. 
                        # seed has no state, so only reserve once
                        # but the latest global will be pickled in database.py
PICKLE_DIR = "decentspec_pickle/"
PICKLE_GLOBAL = "global"
PICKLE_MINER = "miner"
PICKLE_SEED = "seed"

# COMMON 
DEFAULT_NAME_LENGTH = 10
SEED_ADDR = "http://api.decentspec.org:5000"
POW_ENABLE = True # false will disable the difficulty check which we do not care hash anymore
REPRODUCIBILITY = True

# @EDGE_SIM related 
EDGE_HTTP_INTERVAL = 1     # seconds between two round
ASYNC_SIM = True            # enable async simulation

# @MINER related 
MINER_REG_INTERVAL = 19
GENESIS_HASH = "genesis_hash"
BLOCK_GEN_INTERVAL = 1      # seconds between mining
STRICT_BLOCK_SIZE = False    # True: each block size will be max
                            # False: each block size will be min~max
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
API_TV_TO_MULTITV = '/reseed_to_mtv'
API_GET_REWARD = '/reward'