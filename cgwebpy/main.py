#!/usr/bin/env python
import argparse
import logging
import pwd
import subprocess
from typing import List

from . import proc_event
from . import pyproc
from .cgroup_utils import *

try:
    import systemd.daemon
    import systemd.journal
except:
    systemd = None


class CGWeb(object):

    def __init__(self):
        self._logger_init()
        self.args = self._parse_args()

    def run(self):
        cgroup_create(self.args.cgroup_group, self.args.controllers)

        if self.args.virtualmin:
            virtualmin_user = self._virtualmin_users()
            for user in virtualmin_user:
                self._create_cgroup(user)
        else:
            virtualmin_user = []
        if systemd:
            systemd.daemon.notify('READY=1')
            on_signal = lambda: systemd.daemon.notify('STOPPING=1')
        else:
            on_signal = None
        for (what, pid) in proc_event.process_events(
                [proc_event.PROC_EVENT_FORK, proc_event.PROC_EVENT_EXEC],
                on_signal
        ):
            try:
                procinfo = pyproc.get_status(pid)
                if procinfo is None:
                    logging.debug(f"process {pid} not found - event: {what}")
                    continue
                uid = procinfo['Uid']['real']

                if self.args.virtualmin:
                    user = pwd.getpwuid(uid).pw_name
                    if user not in virtualmin_user:
                        continue
                else:
                    if uid < 1000:
                        continue
                    user = pwd.getpwuid(uid).pw_name

                cgroup_name = self._create_cgroup(user=user, force=False)
                self._cgroup_assign_pid(user=user, pid=pid)

                logging.info(
                    f"process {procinfo['Name']} ({pid}) for user {user} ( {uid} ) added to cgroup '{cgroup_name}'"
                )
            except Exception as e:
                logging.exception(e)

    def _parse_args(self):
        parser = argparse.ArgumentParser(description='Cgroup daemon for LAMP server')
        parser.add_argument(
            '--controllers',
            dest='controllers',
            choices=['cpuset', 'cpu', 'io', 'memory', 'hugetlb', 'pids', 'rdma', 'misc'],
            action='append'
        )
        parser.add_argument('-n', '--cgroup.group', dest='cgroup_group', default='webusers')
        parser.add_argument('--virtualmin', dest='virtualmin', action='store_true')
        parser.add_argument('--memory.max', dest='memory_max', default=None)
        parser.add_argument('--cpu.weight', dest='cpu_weight', default=None)  # choices=range(0, 10000)
        parser.add_argument('--cpu.max', dest='cpu_max', default=None, required=False)
        parser.add_argument('--cpu.max.burst', dest='cpu_max_burst', default=None, required=False)
        parser.add_argument('--cpu.pressure', dest='cpu_pressure', default=None, required=False)
        parser.add_argument('--cpu.uclamp.min', dest='cpu_uclamp_min', default=None, required=False)
        parser.add_argument('--cpu.weight.nice', dest='cpu_weight_nice', default=None, required=False)
        parser.add_argument('--cpu.uclamp.max', dest='cpu_uclamp_max', default=None, required=False)
        parser.add_argument('--memory.min', dest='memory_min', default=None, required=False)
        parser.add_argument('--memory.low', dest='memory_low', default=None, required=False)
        parser.add_argument('--memory.high', dest='memory_high', default=None, required=False)
        parser.add_argument('--memory.oom.group', dest='memory_oom_group', default=None, required=False)
        parser.add_argument('--memory.swap.high', dest='memory_swap_high', default=None, required=False)
        parser.add_argument('--memory.swap.max', dest='memory_swap_max', default=None, required=False)
        parser.add_argument('--memory.zswap.max', dest='memory_zswap_max', default=None, required=False)
        parser.add_argument('--io.cost.qos', dest='io_cost_qos', default=None, required=False)
        parser.add_argument('--io.cost.model', dest='io_cost_model', default=None, required=False)
        parser.add_argument('--io.weight', dest='io_weight', default=None, required=False)
        parser.add_argument('--io.max', dest='io_max', default=None, required=False)
        parser.add_argument('--pids.max', dest='pids_max', default=None, required=False)
        return parser.parse_args()

    def _logger_init(self):
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

    def _create_cgroup(self, user: str, force: bool = False):
        cgroup_name = self._cgroup_name(user)
        if force or not cgroup_exists(cgroup_name):
            cgroup_create(cgroup_name, self.args.controllers)
            if self.args.cpu_weight is not None:
                cgroup_set(cgroup_name, "cpu.weight", self.args.cpu_weight, "cpu")
            if self.args.cpu_max is not None:
                cgroup_set(cgroup_name, 'cpu.max', self.args.cpu_max, "cpu")
            if self.args.cpu_max_burst is not None:
                cgroup_set(cgroup_name, 'cpu.max.burst', self.args.cpu_max_burst, "cpu")
            if self.args.cpu_pressure is not None:
                cgroup_set(cgroup_name, 'cpu.pressure', self.args.cpu_pressure, "cpu")
            if self.args.cpu_weight_nice is not None:
                cgroup_set(cgroup_name, 'cpu.weight.nice', self.args.cpu_weight_nice, "cpu")
            if self.args.cpu_uclamp_min is not None:
                cgroup_set(cgroup_name, 'cpu.uclamp.min', self.args.cpu_uclamp_min, "cpu")
            if self.args.cpu_uclamp_max is not None:
                cgroup_set(cgroup_name, 'cpu.uclamp.max', self.args.cpu_uclamp_max, "cpu")
            if self.args.memory_max is not None:
                cgroup_set(cgroup_name, 'memory.max', self.args.memory_max, "memory")
            if self.args.memory_min is not None:
                cgroup_set(cgroup_name, 'memory.min', self.args.memory_min, "memory")
            if self.args.memory_low is not None:
                cgroup_set(cgroup_name, 'memory.low', self.args.memory_low, "memory")
            if self.args.memory_high is not None:
                cgroup_set(cgroup_name, 'cpu.memory.max', self.args.memory_high, "cpu")
            if self.args.memory_oom_group is not None:
                cgroup_set(cgroup_name, 'memory.oom.group', self.args.memory_oom_group, "memory")
            if self.args.memory_swap_high is not None:
                cgroup_set(cgroup_name, 'memory.swap.high', self.args.memory_swap_high, "memory")
            if self.args.memory_swap_max is not None:
                cgroup_set(cgroup_name, 'memory.swap.max', self.args.memory_swap_max, "memory")
            if self.args.memory_zswap_max is not None:
                cgroup_set(cgroup_name, 'memory.zswap.max', self.args.memory_zswap_max, "memory")
            if self.args.io_cost_qos is not None:
                cgroup_set(cgroup_name, 'io.cost.qos', self.args.io_cost_qos, "io")
            if self.args.io_cost_model is not None:
                cgroup_set(cgroup_name, 'io.cost.model', self.args.io_cost_model, "io")
            if self.args.io_weight is not None:
                cgroup_set(cgroup_name, 'io.weight', self.args.io_weight, "io")
            if self.args.io_max is not None:
                cgroup_set(cgroup_name, 'io.max', self.args.io_max, "io")
            if self.args.pids_max is not None:
                cgroup_set(cgroup_name, 'pids.max', self.args.pids_max, "pids")
        return cgroup_name

    def _cgroup_assign_pid(self, user: str, pid: int):
        cgroup_name = self._cgroup_name(user)
        cgroup_assing(cgroup_name, pid)

    def _cgroup_name(self, user: str) -> str:
        return f'{self.args.cgroup_group}/{user}'

    def _virtualmin_users(self) -> List[str]:
        return [
            user for user in
            subprocess.check_output(['virtualmin', 'list-domains', '--user-only']).decode('utf-8').split('\n') if
            len(user) > 0
        ]


def main():
    cgweb = CGWeb()
    cgweb.run()


if __name__ == "__main__":
    main()
