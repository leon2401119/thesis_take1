import random
import subprocess
import os
import re
import pickle
import torch
import torch.nn as nn
import torch.optim as optim
from math import floor
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
            self.mem.pop(0)
        for i in range((len(ep)-1)//3):
            self.mem.append(ep[i*3:i*3+4])

    def get_batch(self,batchsize):      # returns batchsize*4 of list
        assert batchsize < self.memsize, 'batch size larger than total memory size'
        batchsize = len(self.mem) if batchsize > len(self.mem) else batchsize

        return random.sample(self.mem,batchsize)

    def full(self):
        return True if self.memsize == len(self.mem) else False


class RL:
    def __init__(self,src_folder,**kwargs):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.rpmem = ReplayMemory(kwargs['memsize'])
        self.actor = Action()
        # TODO 1 : split dataset into training & validation set - DONE
        # TODO 2 : keep src_folder clean, separate folder for generated files for training - DONE
        assert len(os.listdir(src_folder)) >= 1, 'please initialize with at least one source file (.ll)'

        if os.path.isdir('llvm_gym'):
            os.system('rm -rf llvm_gym')
        os.system(f'cp -r {src_folder} llvm_gym')
        src_folder = 'llvm_gym'
        os.chdir(src_folder)

        dataset = ['./'+src for src in os.listdir('.')]
        random.shuffle(dataset)
        cutoff = floor(len(dataset)*(1-kwargs['eval_ratio']))
        train_dataset = dataset[:cutoff]
        eval_dataset = dataset[cutoff:]

        self.train_agent = [IR(path) for path in train_dataset]
        self.eval_agent = [IR(path) for path in eval_dataset]
        # TODO : policy & target net
        self.network = DQN(len(self.train_agent[0].state_vec),self.actor.num_flags).to(self.device)
        self.target_network = DQN(len(self.train_agent[0].state_vec),self.actor.num_flags).to(self.device)
        self.target_network.load_state_dict(self.network.state_dict())

        # tunables
        self.LR = kwargs['lr']
        self.GAMMA = kwargs['gamma']
        self.EPSILON = kwargs['epsilon']    # epsilon decrease rate?
        self.EPSILON_MIN = 0.01
        self.EPSILON_DECR_RATE = 0.00001
        self.MAX_EPISODE = 100000
        self.MAX_STEPS = kwargs['max_steps']
        self.BATCH_SIZE = kwargs['batch_size']
        self.UPDATE_INTERVAL = 10
        self.EVAL_INTERVAL = 30
        self.TARGET_UPDATE_INTERVAL = 100
        self.loss_function = nn.MSELoss()
        self.optimizer = optim.Adam(self.network.parameters(), lr=self.LR)

    def __myencoder(self,flag_id):
        code = ''
        for _ in range(2):
            modulo = flag_id % 36
            if modulo <= 9:
                char = chr(ord('0') + modulo)
            else:
                char = chr(ord('a') + modulo - 10)
            code = char + code
            flag_id //= 36
        return code

    def get_action(self,state_vec):
        # actions are all single-step right now

        flags_id = []
        if random.random() < self.EPSILON:
            flags_id.append(random.randint(0, self.actor.num_flags - 1))
        else:
            out = self.network.forward(torch.tensor(state_vec).float())
            flags_id.append(out.argmax().item())   # the optimization sequence in numbers (output from deep Q-network)

        path_append = ''.join(self.__myencoder(flag_id) for flag_id in flags_id)
        flags = self.actor.get_action(*flags_id)

        if self.EPSILON > self.EPSILON_MIN:
            self.EPSILON -= self.EPSILON_DECR_RATE

        return flags_id, flags, path_append

    def train(self):
        ep_counter, step_counter = 0, 0
        while ep_counter < self.MAX_EPISODE:
            # fill replay memory
            ir = self.train_agent[random.randint(0,len(self.train_agent)-1)]
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

            if not ep_counter % self.UPDATE_INTERVAL:
                batch = self.rpmem.get_batch(self.BATCH_SIZE)
                if len(batch):
                    groundtruth = [pair[2]+self.GAMMA*torch.max(self.target_network.forward(torch.tensor(pair[3]).float())) for pair in batch]
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
                    step_counter += 1

                if not step_counter % self.TARGET_UPDATE_INTERVAL:
                    with torch.no_grad():
                        self.target_network.load_state_dict(self.network.state_dict())

            if not ep_counter % self.EVAL_INTERVAL:
                self.eval()

    def eval(self):
        # TODO : self-explanatory - DONE
        self.network.eval()
        self.network.save_model()
        saved_epsilon = self.EPSILON
        speedup = []
        self.EPSILON = 0
        for ir in self.eval_agent:
            base_exec_time = ir.exec_time
            for _ in range(self.MAX_STEPS):
                state = ir.state_vec
                flags_id, flags, path_append = self.get_action(state)
                if not ir.opt(path_append, *flags):
                    print(f'best strategy is not a valid path')
                    break
            speedup_exec_time = ir.exec_time

            speedup.append(base_exec_time/speedup_exec_time)

        for ir in self.eval_agent:
            ir.reset()

        self.EPSILON = saved_epsilon
        self.network.train()
        print(f'[EVAL] avg.speedup = {sum(speedup)/len(speedup)}')
        return sum(speedup)/len(speedup)    # return avg. speedup for validation

# unit test
if __name__ == '__main__':
    act = Action()
    print(act.get_action(10,11,12))
    print(act.random())
