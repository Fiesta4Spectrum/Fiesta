# common 
DEFAULT_NN_STRUCTURE = [2,50,50,50,1]
DEFAULT_NAME_LENGTH = 10
SEED_ADDR = "http://api.decentspec.org:5000"

# edge_sim related consts
RANDOM_EDGE = False # do we need to random send?
LOCAL_DATASET_FILE = "DecentSpec/Dataset/GPS-power.dat"     # data structure 

# miner related consts
MINER_REG_INTERVAL = 19

# seed server related consts
SEED_CHAIN_SCAN_INTERVAL = 20     # compute reward per 20s
SEED_LEASING_COUNTDOWN = 1    # rate of leasing timer reduction
SEED_LEASING_INIT = 20

# YOU ARE NOT SUPPOSED TO CHANGE THE CONFIG BELOW

# api related
API_UPDATE_SEED = '/seed_update'
API_POST_LOCAL = '/new_transaction'
API_GET_POOL = '/pending_tx'
API_GET_GLOBAL = '/global_model'
API_GET_CHAIN = '/chain'
API_GET_CHAIN_PRINT = '/chain_print'
API_POST_BLOCK = '/add_block'

API_REGISTER = '/register'
