# NOTICE !!!
# normally edge device have no knowledge of the NN class definition
# so this model.py sharing is IMPOSSIBLE
# TODO use TorchScript to serialize the model class

import torch
import torch.nn as nn
import torch.nn.functional as F
import DecentSpec.Common.tasks as SEED
import DecentSpec.Common.config as CONFIG

if CONFIG.REPRODUCIBILITY:
    torch.manual_seed(32767)

class FNNModel(nn.Module):

    # parameter-related operation is defined in init as nn
    def __init__(self, nlist = SEED.DEFAULT_NN_STRUCTURE):
        super(FNNModel, self).__init__()
        # input of network is a 2-dimensional feature(latitude, longitude)
        self.hidden = nn.ModuleList()
        self.hidden_size = len(nlist) - 2
        for i in range(self.hidden_size):
            self.hidden.append(nn.Linear(nlist[i], nlist[i+1]))
        self.ol = nn.Linear(nlist[-2],nlist[-1])   # outputlayer
    
    # parameter-irrelative operation is recommended as function
    def forward(self, x): # input x is the 2-dimensional spatial coordinates
        for i in range(self.hidden_size):
            x = F.relu(self.hidden[i](x))
        x = self.ol(x)
        return x