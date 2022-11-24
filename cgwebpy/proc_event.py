import logging
import os
import signal
import socket
import struct
import sys
from threading import Event
from typing import List, Tuple, Callable, Generator

__all__ = [
    'process_events',
    'PROC_EVENT_NONE',
    'PROC_EVENT_FORK',
    'PROC_EVENT_EXEC',
    'PROC_EVENT_UID',
    'PROC_EVENT_GID',
    'PROC_EVENT_SID',
    'PROC_EVENT_PTRACE',
    'PROC_EVENT_COMM',
    'PROC_EVENT_COREDUMP',
    'PROC_EVENT_EXIT'
]

CN_IDX_PROC = 1
CN_VAL_PROC = 1
NETLINK_CONNECTOR = 11
NLMSG_NOOP = 1
NLMSG_ERROR = 2
NLMSG_DONE = 3
NLMSG_OVERRUN = 4

PROC_CN_MCAST_LISTEN = 1
PROC_CN_MCAST_IGNORE = 2

PROC_EVENT_NONE = 0x00000000
PROC_EVENT_FORK = 0x00000001
PROC_EVENT_EXEC = 0x00000002
PROC_EVENT_UID = 0x00000004
PROC_EVENT_GID = 0x00000040
PROC_EVENT_SID = 0x00000080
PROC_EVENT_PTRACE = 0x00000100
PROC_EVENT_COMM = 0x00000200
PROC_EVENT_COREDUMP = 0x40000000
PROC_EVENT_EXIT = 0x80000000

PROC_EVENT_WHAT = {
    PROC_EVENT_NONE: "PROC_EVENT_NONE",
    PROC_EVENT_FORK: "PROC_EVENT_FORK",
    PROC_EVENT_EXEC: "PROC_EVENT_EXEC",
    PROC_EVENT_UID: "PROC_EVENT_UID",
    PROC_EVENT_GID: "PROC_EVENT_GID",
    PROC_EVENT_SID: "PROC_EVENT_SID",
    PROC_EVENT_PTRACE: "PROC_EVENT_PTRACE",
    PROC_EVENT_COMM: "PROC_EVENT_COMM",
    PROC_EVENT_COREDUMP: "PROC_EVENT_COREDUMP",
    PROC_EVENT_EXIT: "PROC_EVENT_EXIT"
}


def _init_socket(exit_event: Event, on_signal: Callable = None):
    sock = socket.socket(socket.AF_NETLINK, socket.SOCK_DGRAM, NETLINK_CONNECTOR)
    pid = sock.getsockname()[1]
    sock.bind((pid, CN_IDX_PROC))

    def signal_handler(signum, frame):
        exit_event.set()

        try:
            if on_signal:
                on_signal()
        except:
            pass

        signame = signal.Signals(signum).name
        print(f'Signal {signame} ({signum}) received')
        if sock:
            sock.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    data = struct.pack(
        "=IHHII IIIIHH I",
        16 + 20 + 4, NLMSG_DONE, 0, 0, os.getpid(),
        CN_IDX_PROC, CN_VAL_PROC, 0, 0, 4, 0,
        PROC_CN_MCAST_LISTEN
    )
    if sock.send(data) != len(data):
        raise RuntimeError("socket init failed")
    return sock


def process_events(event_types: List[int], on_signal: Callable = None) -> Generator[Tuple[str, int], None, None]:
    exit_event = Event()
    sock = _init_socket(exit_event, on_signal=on_signal)

    while not exit_event.is_set():
        try:
            data, (nlpid, nlgrps) = sock.recvfrom(1024)
        except OSError as e:
            logging.exception(e)
            continue

        # Netlink message header (struct nlmsghdr)
        msg_len, msg_type, msg_flags, msg_seq, msg_pid = struct.unpack("=IHHII", data[:16])

        if msg_type == NLMSG_NOOP:
            continue
        if msg_type in (NLMSG_ERROR, NLMSG_OVERRUN):
            break

        data = data[16:][20:]

        what, = struct.unpack("=L", data[:4])
        data = data[16:]
        if what == PROC_EVENT_NONE:
            continue
        if what in event_types:
            pid, = struct.unpack("=I", data[:4])
            what_str = PROC_EVENT_WHAT.get(what, f"PROC_EVENT_UNKNOWN({what})")
            yield what_str, pid

            if what == PROC_EVENT_FORK:
                data = data[:16]
                pid, = struct.unpack("=I", data[:4])
                yield what_str, pid
    if sock:
        sock.close()
