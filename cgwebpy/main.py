#!/usr/bin/env python
import logging
import pwd

import pyproc
from cgroup_utils import *
import proc_event


try:
    import systemd.daemon
    import systemd.journal
except:
    systemd = None


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Cgroup daemon for LAMP server')
    parser.add_argument('-m', '--memory.max', dest='memory_max', default='1000M')
    parser.add_argument('-c', '--cpu.weight', dest='cpu_weight', default='1024')
    parser.add_argument('-n', '--cgroup.group', dest='cgroup_group', default='webusers')
    args = parser.parse_args()

    memory_max=args.memory_max
    cpu_weight=args.cpu_weight
    cgroup_base=args.cgroup_group
    controllers = ["cpu", "memory"]  # , "cpuacct"

    if systemd:
        log_handlers = [systemd.journal.JournalHandler(), logging.StreamHandler()]
    else:
        log_handlers = [logging.StreamHandler()]

    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(message)s',
        encoding='utf-8',
        level=logging.DEBUG,
        handlers=log_handlers
    )

    cgroup_create(cgroup_base, controllers)
    #cgroup_set(cgroup_base, "memory.max", memory_max)
    #cgroup_set(cgroup_base, "cpu.weight", cpu_weight)

    if systemd:
        systemd.daemon.notify('READY=1')
        on_signal = lambda: systemd.daemon.notify('STOPPING=1')
    else:
        on_signal = None

    for (what, pid) in proc_event.process_events([proc_event.PROC_EVENT_FORK, proc_event.PROC_EVENT_EXEC], on_signal):
        try:
            procinfo = pyproc.get_status(pid)
            if procinfo is None:
                logging.warning(f"process {pid} not found - event: {what}")
                continue
            uid = procinfo['Uid']['real']
            user = pwd.getpwuid(uid)
            if uid < 1000:
                continue
            cgroup_name = f'{cgroup_base}/{user.pw_name}'
            cgroup_create(cgroup_name, controllers)
            cgroup_set(cgroup_name, 'memory.max', memory_max)
            cgroup_set(cgroup_name, "cpu.weight", cpu_weight)
            cgroup_assing(cgroup_name, pid)

            logging.info(
                f"process {procinfo['Name']} ( {pid} ) for user {user.pw_name} ( {uid} ) added to cgroup '{cgroup_name}'"
            )
        except Exception as e:
            logging.exception(e)


if __name__ == "__main__":
    main()
