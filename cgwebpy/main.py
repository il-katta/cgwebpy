#!/usr/bin/env python
import argparse
import configparser
import logging
import pwd
import subprocess
import threading
from typing import List, Optional

try:
    from . import proc_event
    from . import pyproc
    from .cgroup_utils import *
except ImportError:
    import proc_event
    import pyproc
    from cgroup_utils import *

try:
    import systemd.daemon
    import systemd.journal
except:
    systemd = None


class CGWeb(object):
    def __init__(self):
        self.config = self.read_config()
        self._logger_init(self.config['global']['logging_level'], self.config.getboolean('global', 'systemd'))

    def run(self):
        logging.debug(f"creating parent cgroup '{self.config['global']['cgroup_name']}'")

        self._create_cgroup(force=True)
        if self.config.getboolean('global', 'virtualmin'):
            virtualmin_user = self._virtualmin_users()
            for user in virtualmin_user:
                logging.debug(f"creating cgroup for user '{user}'")
                self._create_cgroup(user, force=True)
        else:
            virtualmin_user = []
        if systemd and self.config.getboolean('global', 'systemd'):
            systemd.daemon.notify('READY=1')
            on_signal = lambda: systemd.daemon.notify('STOPPING=1')
        else:
            on_signal = None

        threading.Thread(target=self._classify_all_processes).start()

        proc_gen = proc_event.process_events(
            [
                proc_event.PROC_EVENT_FORK,
                proc_event.PROC_EVENT_EXEC,
                proc_event.PROC_EVENT_UID,
                proc_event.PROC_EVENT_GID
            ],
            on_signal
        )
        for what, pid in proc_gen:
            try:
                self._process_pid(pid, virtualmin_user=virtualmin_user, what=what)
            except Exception as e:
                logging.exception(e)

    def _classify_all_processes(self):
        import os

        if self.config.getboolean('global', 'virtualmin'):
            virtualmin_user = self._virtualmin_users()
        else:
            virtualmin_user = []

        for pid in os.listdir('/proc'):
            if not pid.isdigit() or not os.path.isdir(os.path.join('/proc', pid)):
                continue
            try:
                self._process_pid(int(pid), virtualmin_user=virtualmin_user)
            except Exception as e:
                logging.exception(e)

    def _process_pid(self, pid: int, virtualmin_user: Optional[List[str]] = None, what: Optional[str] = None):
        procinfo = pyproc.get_status(pid)
        if procinfo is None:
            # logging.debug(f"process {pid} not found - event: {what}")
            return
        uid = procinfo['Uid']['real']

        if self.config.getboolean('global', 'virtualmin'):
            user = pwd.getpwuid(uid).pw_name
            if user not in virtualmin_user:
                return
        else:
            if uid < 1000:
                return
            user = pwd.getpwuid(uid).pw_name

        cgroup_name = self._create_cgroup(user=user, force=False)
        self._cgroup_assign_pid(user=user, pid=pid)

        logging.info(
            f"process {procinfo['Name']} ({pid}/{what}) for user {user} ({uid}) added to cgroup '{cgroup_name}'"
        )

    def _parse_args(self):
        parser = argparse.ArgumentParser(description='Cgroup daemon for LAMP server')
        parser.add_argument('--config', dest='config', default='/etc/cgweb.conf', required=True)
        parser.add_argument(
            '--controllers',
            dest='controllers',
            choices=[
                # cgroup v2
                'cpuset', 'cpu', 'io', 'memory', 'hugetlb', 'pids', 'rdma', 'misc',
                # cgroup v1 only
                'cpuacct', 'devices', 'freezer', 'net_cls', 'blkio', 'perf_event', 'net_prio', 'hugetlb'
            ],
            action='append'
        )
        parser.add_argument('-n', '--cgroup.group', dest='cgroup_group', default='webusers')
        parser.add_argument('--virtualmin', dest='virtualmin', action='store_true')
        parser.add_argument('--logging.level', dest='logging_level', choices=[
            'CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'
        ], default='INFO')
        parser.add_argument('--systemd', dest='use_systemd', action='store_true', default=False)

        return parser.parse_args()

    def _parse_conf_file(self, filepath: str) -> configparser.ConfigParser:
        config = configparser.ConfigParser()
        config.read(filepath)
        return config

    def read_config(self):
        args = self._parse_args()
        config = self._parse_conf_file(args.config)
        if args.use_systemd:
            config['global']['systemd'] = 'yes'
        if args.virtualmin:
            config['global']['virtualmin'] = 'yes'
        if args.logging_level:
            config['global']['logging.level'] = args.logging_level
        if args.controllers:
            config['global']['controllers'] = ','.join(args.controllers)
        if args.cgroup_group:
            config['global']['cgroup_name'] = args.cgroup_group
        return config

    def _logger_init(self, level: str = "DEBUG", use_systemd: bool = False):
        if systemd and use_systemd:
            log_handlers = [systemd.journal.JournalHandler()]
        else:
            log_handlers = [logging.StreamHandler()]

        logging.basicConfig(
            format='%(asctime)s - %(levelname)s - %(message)s',
            encoding='utf-8',
            level=logging.getLevelName(level),
            handlers=log_handlers
        )

    def _create_cgroup(self, user: Optional[str] = None, force: bool = False):
        cgroup_name = self._cgroup_name(user)
        if user:
            options = self.config.items('users_cgroup')
        else:
            options = self.config.items('global_cgroup')

        if force or not cgroup_exists(cgroup_name):
            cgroup_create(cgroup_name, self.config['global']['controllers'].split(','))
            for key, value in options:
                cgroup_set(cgroup_name, key, value, key.split('.')[0])
        return cgroup_name

    def _cgroup_assign_pid(self, user: str, pid: int):
        cgroup_name = self._cgroup_name(user)
        cgroup_assing(cgroup_name, pid, self.config['global']['controllers'].split(','))

    def _cgroup_name(self, user: Optional[str] = None) -> str:
        if user:
            return f"{self.config['global']['cgroup_name']}/{user}"
        else:
            return self.config['global']['cgroup_name']

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
