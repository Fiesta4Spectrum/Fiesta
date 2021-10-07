
DEFAULT_NN_STRUCTURE = [2,50,50,50,1]
DEFAULT_NAME_LENGTH = 10

RANDOM_EDGE = False # do we need to random send?
LOCAL_DATASET_FILE = "DecentSpec/Dataset/GPS-power.dat"     # data structure 
SEED_ADDR = "http://api.decentspec.org:5000"

# seed server related consts
SEED_CHAIN_SCAN_RATE = 20      # compute reward per 10s
SEED_LEASING_COUNTDOWN = 1    # rate of leasing timer reduction
SEED_LEASING_INIT = 20