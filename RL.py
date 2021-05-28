import random
import subprocess
import os
import re
import pickle
import torch
import torch.nn as nn
import torch.optim as optim
from IR import IR
from DQN import DQN

class Action:
    def __init__(self):
        try:
            with open('flags.pickle', 'rb') as f:
                self.flags = pickle.load(f)
        except FileNotFoundError:
            self.flags = self.retrieve_flags()
        finally:
            self.num_flags = len(self.flags)

    def retrieve_flags(self):
        p = subprocess.run(['opt','-h'], stdout=subprocess.PIPE)
        msg = p.stdout.decode('utf-8').split('Optimizations available:\n')[1]
        # exclude architecture specific optimizations for now
        flags = re.findall(r'--(?!amd|aarch|arm|avr|dot|falkor|function-import|gcn|help|hexagon|internalize|instruction-select|nvptx|machine|metarenamer|mips|objc|packets|ppc|print|r600|regbank|riscv|si|slotindexes|target|view|wasm|x86|X86)[^ ]*', msg)
        cutoff_str = '--bounds-checking-single-trap'
        for id, flag in enumerate(flags):
            if flag == cutoff_str:
                flags = flags[:id]

        # dump for future use
        with open('flags.pickle','wb') as f:
            pickle.dump(flags, f)

        return flags

    def get_action(self,*ids):
        flags = []
        for i in ids:
            flags.append(self.flags[i])
        return flags

    def random(self):
        # TODO: smart random
        return self.flags[random.randint(0,self.num_flags-1)]


class ReplayMemory:
    def __init__(self,memsize):
        self.mem = []
        self.memsize = memsize  # in state action reward pairs

    def push(self,ep):    # ep = (state_1,action_1,reward_1,state_2,...)
        pairs = (len(ep)-1)//3
        for _ in range(len(self.mem) + pairs - self.memsize):
            self.mem.pop(random.randint(0,len(self.mem)-1))
        for i in range((len(ep)-1)//3):
            self.mem.append(ep[i*3:i*3+4])

    def get_batch(self,batchsize):      # returns batchsize*4 of list
        assert batchsize < self.memsize, 'batch size larger than total memory size'
        batchsize = len(self.mem) if batchsize > len(self.mem) else batchsize

        batch = []
        for _ in range(batchsize):
            batch.append(self.mem.pop(random.randint(0,len(self.mem)-1)))
        return batch

    def full(self):
        return True if self.memsize == len(self.mem) else False


class RL:
    def __init__(self,src_folder,**kwargs):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.rpmem = ReplayMemory(100)
        self.actor = Action()
        # TODO 1 : split dataset into training & validation set
        # TODO 2 : keep src_folder clean, separate folder for generated files for training
        assert len(os.listdir(src_folder)) >= 1, 'please initialize with at least one source file (.ll)'
        self.agent = [IR(os.path.join(src_folder,src)) for src in os.listdir(src_folder)]
        # TODO : policy & target net
        self.network = DQN(len(self.agent[0].state_vec),self.actor.num_flags).to(self.device)
        self.loss_function = nn.MSELoss()

        # tunables
        self.LR = kwargs['lr']
        self.GAMMA = kwargs['gamma']
        self.EPSILON = kwargs['epsilon']    # epsilon decrease rate?
        self.EPSILON_MIN = 0.01
        self.EPSILON_DECR_RATE = 0.00001
        self.MAX_EPISODE = 100000
        self.MAX_STEPS = kwargs['max_steps']
        self.BATCH_SIZE = kwargs['batch_size']
        self.optimizer = optim.Adam(self.network.parameters(), lr=self.LR)

    def get_action(self,state_vec):
        # actions are all single-step right now

        flags_id = []
        if random.random() < self.EPSILON:
            flags_id.append(random.randint(0, self.actor.num_flags - 1))
        else:
            out = self.network.forward(torch.tensor(state_vec).float())
            flags_id.append(out.argmax().item())   # the optimization sequence in numbers (output from deep Q-network)

        path_append = ''.join('{:03X}'.format(flag_id) for flag_id in flags_id)
        flags = self.actor.get_action(*flags_id)

        if self.EPSILON > self.EPSILON_MIN:
            self.EPSILON -= self.EPSILON_DECR_RATE

        return flags_id, flags, path_append

    def train(self):
        ep_counter = 0
        while ep_counter < self.MAX_EPISODE:
            # fill replay memory
            while not self.rpmem.full():
                ir = self.agent[random.randint(0,len(self.agent)-1)]
                ep = []
                for _ in range(self.MAX_STEPS):
                    state = ir.state_vec
                    flags_id, flags, path_append = self.get_action(state)
                    reward = ir.opt(path_append, *flags)
                    if not reward:
                        break
                    ep.extend([state,flags_id[0],reward])

                ep.append(ir.state_vec)     # push finishing state
                ep_counter += 1
                if len(ep)>=4:
                    # avoid the case where the first opt fail, resulting ep = [[base_state]]
                    self.rpmem.push(ep)
                ir.reset()

            while True:
                batch = self.rpmem.get_batch(self.BATCH_SIZE)
                if len(batch):
                    groundtruth = [pair[2]+self.GAMMA*torch.max(self.network.forward(torch.tensor(pair[3]).float())) for pair in batch]
                    y = [self.network.forward(torch.tensor(pair[0]).float())[pair[1]] for pair in batch]
                    groundtruth = torch.stack(groundtruth)
                    y = torch.stack(y)
                    loss = self.loss_function(y,groundtruth)
                    print(f'loss = {loss}')
                    loss.backward()

                    # optional : clip gradient
                    for param in self.network.parameters():
                        param.grad.data.clamp_(-1, 1)

                    self.optimizer.step()

                if len(batch)!=self.BATCH_SIZE:
                    break
        self.network.save_model()

    def eval(self):
        # TODO : self-explanatory
        pass


# unit test
if __name__ == '__main__':
    act = Action()
    print(act.get_action(10,11,12))
    print(act.random())
