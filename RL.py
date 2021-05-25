import random
import subprocess
import re
import pickle

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
        flags = re.findall(r'--(?!amd|aarch|arm|dot|falkor|hexagon|mips|objc|ppc|print|r600|view|x86)[^ ]*', msg)

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
        return self.flags[random.randint(0,len(self.flags)-1)]


class ReplayMemory:
    def __init__(self):
        pass


if __name__ == '__main__':
    act = Action()
    print(act.get_action(10,11,12))
    print(act.random())
