# TV-channel spatial prediction regression

class TV_CHANNEL_TASK:
    NAME = "tv_regression"
    DIFFICULTY = 3
    ALPHA = 0.5
    DEFAULT_NN_STRUCTURE = [2,50,50,50,1]
    SAMPLE_PARA = {
        'center_freq' : 525000000,
        'bandwidth'   : 50000000,
    }
    PREPROC_PARA = {
        'avg' : [43.073068, -89.431795, -84],
        'std' : [0.03, 0.05, 7],
    }
    TRAIN_PARA = {
        'batch' : 10,
        'lr'    : 0.001,
        'opt'   : 'Adam',
        'epoch' : 5,                            # local epoch Num
        'loss'  : 'MSE',
    }
    FULL_FILE_PATH = "../Dataset/GPS_power.dat"

class MULTI_TV_CHANNEL_TASK:
    NAME = "mtv_regression"
    DIFFICULTY = 3
    ALPHA = 0.5
    DEFAULT_NN_STRUCTURE = [2,50,50,50,8]
    SAMPLE_PARA = {
        'center_freq' : 525000000,
        'bandwidth'   : 50000000,
    }
    PREPROC_PARA = {
        'avg' : [43.073068, -89.431795] + [-84] * 8,
        'std' : [0.03, 0.05] + [7] * 8,
    }
    TRAIN_PARA = {
        'batch' : 10,
        'lr'    : 0.001,
        'opt'   : 'Adam',
        'epoch' : 10,                            # local epoch Num
        'loss'  : 'MSE',
    }
    FULL_FILE_PATH = "../Dataset/GPS_power.dat" 

class ANOMALY_DETECTION_TASK:
    NAME = "lte_detection"
    DIFFICULTY = 3
    ALPHA = 0.5
    DEFAULT_NN_STRUCTURE = [256,64,16,64,256]
    SAMPLE_PARA = {
        'center_freq' : 725000000,
        'bandwidth'   : 50000000,
    }
    PREPROC_PARA = {
        'avg' : [-104] * 512,
        'std' : [7] * 512,
    }
    TRAIN_PARA = {
        'batch' : 10,
        'lr'    : 0.001,
        'opt'   : 'Adam',
        'epoch' : 10,                            # local epoch Num
        'loss'  : 'MSE',
    }
    FULL_FILE_PATH = "../Dataset/PSD_256dup.dat"