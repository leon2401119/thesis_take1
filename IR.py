import os
import subprocess
import cmd
from math import log

class IR:
    def __init__(self,src_path):
        # print(f'initializing IR : {src_path}')

        assert len(src_path) > 3 and src_path[-3:] == '.ll', f'class IR initialized with non-IR: {src_path}'
        assert os.path.isfile(src_path), f'IR {src_path} does not exist'

        ########### naming convention ###########
        # eg. opt_IR_path = src.ll, after opt with -dce then
        # opt_IR_path = src_opt_{dce flag in hex}.ll

        # public members
        self.IR_path = src_path
        self.opt_IR_path = src_path
        self.opt_counter = 0
        self.exec_time = None
        self.state_vec = None
        cmd.fill_cmds(self.opt_IR_path)
        if not os.path.isfile(src_path[:-3]):
            r = self.__prep_binary()
            if not r:
                raise Exception(f'base file initialization for class IR failed\nfailed IR : {self.opt_IR_path}')
        self.__time_binary()

    def __prep_binary(self):
        p = subprocess.run(cmd.compile,stderr=subprocess.PIPE)
        if p.returncode:
            # error occur
            # raise Exception(f'compile failed \n{p.stderr.decode(cmd.format)}')
            print(f'compile failed with IR {cmd.compile[2]}')
            return False
        p = subprocess.run(cmd.link,stderr=subprocess.PIPE)
        if p.returncode:
            # error occur
            # raise Exception(f'link failed \n{p.stderr.decode(cmd.format)}')
            print(f'link failed with file {cmd.link[1]}')
            return False
        subprocess.run(cmd.clean,check=True)
        return True

    def __time_binary(self):
        # TODO : adaptive time to counter noisy results
        # UPDATE : postponed bcuz timing is already slow
        while True:
            p = subprocess.run(cmd.time, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if p.returncode == 176:
                # error recovery
                # TODO : cope with 'cannot allocate memory' error from time cmd (free cache) - DONEN'T
                # UPDATE : "echo 1 > /proc/sys/vm/overcommit_memory" seeems to solve the problem
                print('time : cannot allocate memory, retrying...')
            elif p.returncode:
                # error occur
                # raise Exception(f'time failed\n{p.stderr.decode(cmd.format)}')
                print(f'time failed\n{p.stderr.decode(cmd.format)}')
                return False
            else:
                break

        # process static information from time
        # results are enclosed between symbol 'SYMVEC' just in case the timed binary has output
        # weirdly, the results of time is stored in stderr instead of stdout
        vector = p.stderr.decode(cmd.format).split('SYMVEC')[1].split(' ')
        self.state_vec = [int(v) for v in vector[:-2]]
        self.exec_time = float(vector[-2]) + float(vector[-1])
        return True

    # public methods
    def opt(self, opt_encoded_seq, *flags):    # returns reward
        # TODO : change hex representation of flags in naming convention to BASE-64 - DONE (not b64 though)
        new_path = self.opt_IR_path[:-3] + opt_encoded_seq + '.ll'
        cmd.fill_cmds(new_path)

        # TODO : check if file exist first -- DONE
        exist = os.path.isfile(new_path)
        if not exist:
            # do opt
            cmd.fill_opt(self.opt_IR_path, new_path, *flags)
            p = subprocess.run(cmd.opt, stderr=subprocess.PIPE)
            if p.returncode:
                # error occur
                # raise Exception(f'opt failed \n{p.stderr.decode(cmd.format)}\nopt command: {cmd.opt}')
                print(f'opt failed with option {cmd.opt[2]}')
                return None

            if not self.__prep_binary():
                return None

        # calculate reward
        val_before = self.exec_time
        if not self.__time_binary():
            return None
        val_after = self.exec_time

        self.opt_counter += 1
        self.opt_IR_path = new_path

        return log(val_before/val_after)

    def retarget(self,src_path):
        self.__init__(src_path)

    def reset(self):
        self.__init__(self.IR_path)



