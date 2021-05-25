import os
import subprocess
import cmd
from RL import Action
from math import log

actor = Action()

class IR:
    def __init__(self,src_path):
        assert len(src_path) > 3 and src_path[-3:] == '.ll', f'class IR initialized with non-IR: {src_path}'
        assert os.path.isfile(src_path), f'IR {src_path} does not exist'

        ########### naming convention ###########
        # eg. opt_IR_path = src.ll, after opt with -dce then
        # opt_IR_path = src_opt_{dce flag in hex}.ll

        # public members
        self.IR_path = src_path
        self.opt_IR_path = src_path
        self.optimized = False
        self.exec_time = None
        self.state_vec = None
        if not os.path.isfile(src_path[:-3]):
            self.__prep_binary()
        self.__time_binary()

    def __prep_binary(self):
        cmd.fill_cmds(self.opt_IR_path)
        p = subprocess.run(cmd.compile,stderr=subprocess.PIPE)
        if not p.returncode:
            # error occur
            raise Exception(f'compile failed \n{p.stderr.decode(cmd.format)}')
        p = subprocess.run(cmd.link,stderr=subprocess.PIPE)
        if not p.returncode:
            # error occur
            raise Exception(f'link failed \n{p.stderr.decode(cmd.format)}')
        subprocess.run(cmd.clean,check=True)

    def __time_binary(self):
        p = subprocess.run(cmd.time, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if not p.returncode:
            # error occur
            raise Exception(f'time failed\n{p.stderr.decode(cmd.format)}')
        # process static information from time
        # results are enclosed between symbol 'SYMVEC' just in case the timed binary has output
        vector = p.stdout.decode(cmd.format).split('SYMVEC')[1].split(' ')
        self.state_vec = vector[:-2]
        self.exec_time = float(vector[-2]) + float(vector[-1])

    # public methods
    def opt(self, *flags_id):    # returns reward
        new_path = self.opt_IR_path.join('{:02X}'.format(flag_id) for flag_id in flags_id)
        # TODO : check if file exist first -- DONE
        if not os.path.isfile(new_path):
            # do opt
            cmd.fill_opt(self.opt_IR_path, new_path, actor.get_action(flags_id))
            p = subprocess.run(cmd.opt, stderr=subprocess.PIPE)
            if not p.returncode:
                # error occur
                raise Exception(f'opt failed \n{p.stderr.decode(cmd.format)}')
            self.__prep_binary()

        self.opt_IR_path = new_path
        self.optimized = True

        # calculate reward
        val_before = self.exec_time
        self.__time_binary()
        val_after = self.exec_time

        return log(val_before/val_after)

    def retarget(self,src_path):
        self.__init__(src_path)

    def reset(self):
        self.__init__(self.IR_path)


