from RL import *

my_framework = RL('src_ir',**{'lr':0.01,'gamma':0.9,'epsilon':0.9,'max_steps':5,'batch_size':16})
my_framework.train()

