# TV-channel spatial prediction regression

PREPROC_PARA = {
    'avg' : [43.07850074790703, -89.3982621182465, -58.52785514280172],
    'std' : [0.026930841086101193, 0.060267757907425355, 7.434576197607559],
}

TRAIN_PARA = {
    'batch' : 10,
    'lr'    : 0.001,
    'opt'   : 'Adam',
    'epoch' : 10,                            # local epoch Num
    'loss'  : 'MSE',
}

DEFAULT_NN_STRUCTURE = [2,50,50,50,1]

ALPHA = 0.5
