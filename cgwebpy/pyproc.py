import os
import re


def get_uptime():
    with open('/proc/uptime', 'r') as proc_uptime:
        uptime = proc_uptime.readline().split()
        return {
            'uptime': float(uptime[0]),
            'idle': float(uptime[1]),
        }


def get_status(pid: int):
    status = {}
    status_file = '/proc/%d/status' % pid
    if not os.path.exists(status_file):
        return None
    with open(status_file, 'r') as pid_status:
        for line in pid_status.readlines():
            name, value = line.split(':\t')
            value = value.strip()
            if name.startswith('Vm'):
                value = int(value.split(' kB')[0])
            elif name in ('Uid', 'Gid'):
                keys = ('real', 'effective', 'saved_set', 'fs')
                values = map(int, value.split())
                value = dict(zip(keys, values))
            elif name == 'SigQ':
                queued, max_ = value.split('/', 1)
                value = dict(queued=int(queued), max=int(max_))
            elif name == 'Groups':
                groups = value.split()
                value = map(int, groups)
            elif name in ('Tgid', 'PPid', 'TracerPid', 'FDSize', 'Threads',
                          'Pid', 'nonvoluntary_ctxt_switches',
                          'voluntary_ctxt_switches'):
                value = int(value)
            status[name] = value
    return status


def get_stat(pid=None):
    if pid:
        pid = int(pid)
        with open('/proc/%d/stat' % pid, 'r') as pid_stat:
            stat = pid_stat.readline().split()
            return {
                'pid': int(stat[0]),
                'comm': str(stat[1]),
                'state': str(stat[2]),
                'ppid': int(stat[3]),
                'pgrp': int(stat[4]),
                'session': int(stat[5]),
                'tty_nr': int(stat[6]),
                'tpgid': int(stat[7]),
                'flags': int(stat[8]),
                'minflt': int(stat[9]),
                'cminflt': int(stat[10]),
                'majflt': int(stat[11]),
                'cmajflt': int(stat[12]),
                'utime': int(stat[13]),
                'stime': int(stat[14]),
                'cutime': int(stat[15]),
                'cstime': int(stat[16]),
                'priority': int(stat[17]),
                'nice': int(stat[18]),
                'num_treads': int(stat[19]),
                'itrealvalue': int(stat[20]),
                'starttime': int(stat[21]),
                'vsize': int(stat[22]),
                'rss': int(stat[23]),
                'rsslim': int(stat[24]),
                'startcode': int(stat[25]),
                'endcode': int(stat[26]),
                'startstack': int(stat[27]),
            }
    else:

        with open('/proc/stat', 'r') as cpu_stat:
            stats = cpu_stat.readlines()

        # according to man proc(5):
        cpu_names = ['user', 'nice', 'system', 'idle', 'iowait', 'irq', 'softirq', 'steal', 'guest', 'guest_nice']
        page_names = ['in', 'out']
        swap_names = ['in', 'out']

        ret = []
        # CPU
        cpu_line = [x.split() for x in stats if x.startswith('cpu ')]
        if len(cpu_line) == 1:
            cpu_line = [int(x) for x in cpu_line[0] if x.isdigit()]
            cpu = dict(zip(cpu_names, cpu_line))
            ret.append(['cpu', cpu])

        # CPU<N>
        cpus_lines = [[int(y) for y in x if y.isdigit()] for x in stats if re.match('^cpu\d', x)]
        if len(cpus_lines) > 0:
            cpus = [dict(zip(cpu_names, cpu)) for cpu in cpus_lines]
            ret.append(['cpus', cpus])

        # PAGE
        page_line = [x.split() for x in stats if x.startswith('page')]
        if len(page_line) == 1:
            page = dict(zip(page_names, page_line))
            ret.append(['page', page])

        # SWAP
        swap_line = [x.split() for x in stats if x.startswith('swap')]
        if len(swap_line) == 1:
            swap_line = [int(x) for x in swap_line[0] if x.isdigit()]
            swap = dict(zip(swap_names, swap_line))
            ret.append(['swap', swap])

        # INTR
        intr_line = [x.split() for x in stats if x.startswith('intr')]
        if len(intr_line) == 1:
            intr_line = [int(x) for x in intr_line[0] if x.isdigit()]
            ret.append(['intr', intr_line])

        # CTXT
        ctxt_line = [x.split() for x in stats if x.startswith('ctxt')]
        if len(ctxt_line) == 1:
            ret.append(['ctxt', int(ctxt_line[0][1])])

        # BTIME
        btime_line = [x.split() for x in stats if x.startswith('btime')]
        if len(btime_line) == 1:
            ret.append([ctxt_line[0][0], int(btime_line[0][1])])

        # PROCESSES
        processes_line = [x.split() for x in stats if x.startswith('processes')]
        if len(processes_line) == 1:
            ret.append(['processes', int(processes_line[0][1])])

        # PROCS_RUNNING
        procs_running_line = [x.split() for x in stats if x.startswith('procs_running')]
        if len(procs_running_line) == 1:
            ret.append(['procs_running', int(procs_running_line[0][1])])

        # PROCS_BLOCKED
        procs_blocked_line = [x.split() for x in stats if x.startswith('procs_blocked')]
        if len(procs_blocked_line) == 1:
            ret.append(['procs_blocked', int(procs_blocked_line[0][1])])

        return dict(ret)


# sysconf(_SC_CLK_TCK)
def get_hertz():
    return os.sysconf(os.sysconf_names['SC_CLK_TCK'])
