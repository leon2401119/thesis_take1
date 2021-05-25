compile = ['llc','--filetype=obj',None,'-o',None]
link = ['clang++',None,'-o',None]
clean = ['rm',None]
time = ['/usr/bin/time','--format',
        '"SYMVEC%D %F %I %K %M %O %R %W %X %Z %c %p %r %s %t %w %S %USYMVEC"',
        None]
opt = None
opt_front = ['opt','-S']
opt_back = [None,'-o',None]
format = 'utf-8'


def fill_cmds(base_ll):
    base = base_ll[:-3]
    base_o = base + '.o'
    compile[2], compile[4] = base_ll, base_o
    link[1], link[3] = base_o, base
    time[3] = base
    clean[1] = base_o

def fill_opt(base_ll,opt_ll,*flags):
    global opt
    opt_back[0], opt_back[2] = base_ll, opt_ll
    opt = opt_front + list(flags) + opt_back