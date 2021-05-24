import os
import subprocess
import cmd

class IR:
    def __init__(self,src_path):
        assert len(src_path)>3 and src_path[-3:]=='.ll', f'class IR initialized with non-IR: {src_path}'
        assert os.path.isfile(src_path), f'IR {src_path} does not exist'

        ########### naming convention ###########
        # eg. IR_path = src.ll, after opt with -dce then
        # IR_path = src_opt_{dce flag in hex}.ll

        # public members
        self.IR_path = src_path
        self.opt_IR_path = src_path
        self.optimized = False
        self.exec_time = None
        self.state_vec = None
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
    def opt(self, flag):    # returns reward
        # TODO : check if file exist first
        self.optimized = True

    def retarget(self,src_path):
        self.__init__(src_path)

    def reset(self):
        self.__init__(self.IR_path)


