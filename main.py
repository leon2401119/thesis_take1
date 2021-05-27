from RL import *

dict = {
    'lr':0.01,
    'gamma':0.9
}
my_framework = RL('src_ir',**{'lr':0.01,'gamma':0.9,'epsilon':0.9,'max_steps':30,'batch_size':128})
my_framework.train()

