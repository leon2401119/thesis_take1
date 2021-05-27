import torch
import torch.nn as nn
import torch.nn.functional as F

class DQN(nn.Module):
    def __init__(self,dim_state,dim_action):
        super(DQN, self).__init__()
        self.dim_in, self.dim_out = dim_state, dim_action
        self.fc1 = nn.Linear(dim_state, dim_state//2)
        self.fc2 = nn.Linear(dim_state//2, dim_state//4)
        self.fc3 = nn.Linear(dim_state//4, dim_action)

    def forward(self, x):
        x = F.leaky_relu(self.fc1(x))
        x = F.leaky_relu(self.fc2(x))
        return F.leaky_relu(self.fc3(x))

    def load_model(self):
        self.load_state_dict(torch.load(f'{self.dim_in}_{self.dim_out}.model'))

    def save_model(self):
        torch.save(self.state_dict(), f'{self.dim_in}_{self.dim_out}.model')
