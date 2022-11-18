import ctypes
import os
from typing import List

__all__ = [
    'cgroup_create',
    'cgroup_set',
    'cgroup_assing',
]

CG_VALUE_MAX = 100
FILENAME_MAX = 4096


class struct_control_value(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char * FILENAME_MAX),
        ("value", ctypes.c_char * CG_VALUE_MAX),
        ("dirty", ctypes.c_bool)
    ]


class struct_cgroup_controller(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char * FILENAME_MAX),
        ("values", struct_control_value * CG_VALUE_MAX),
        # ("cgroup", struct_cgroup),
        ("cgroup", ctypes.c_void_p),
        ("int", ctypes.c_int),
    ]


class struct_cgroup(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char * FILENAME_MAX),
        # ("cgroup_controller", struct_cgroup_controller * CG_VALUE_MAX),
        ("cgroup_controller", ctypes.c_void_p),
        ("index", ctypes.c_int),
        ("tasks_uid", ctypes.c_uint),
        ("tasks_gid", ctypes.c_uint),
        ("task_fperm", ctypes.c_uint),
        ("control_uid", ctypes.c_uint),
        ("control_gid", ctypes.c_uint),
        ("control_fperm", ctypes.c_uint),
        ("control_dperm", ctypes.c_uint),
    ]


def c_str(val: str):
    return val.encode('utf-8')


def cgroup_create(group_name: str, controllers: List[str] = None):
    if controllers is None:
        controllers = ["cpu", "memory", "cpuacct"]

    from ctypes.util import find_library

    libname = find_library("cgroup")
    cgroup = ctypes.CDLL(libname)
    ret = cgroup.cgroup_init()
    # cgroup.cgroup_new_cgroup.restype = struct_cgroup
    cgroup.cgroup_new_cgroup.restype = ctypes.c_void_p
    cg = cgroup.cgroup_new_cgroup(c_str(group_name))
    for controller_name in controllers:
        cgc = cgroup.cgroup_add_controller(ctypes.c_void_p(cg), c_str(controller_name))
    ret = cgroup.cgroup_create_cgroup(ctypes.c_void_p(cg), 0)
    cgroup.cgroup_free(ctypes.byref(ctypes.c_void_p(cg)))


def _mkdir(path: str):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def _write(path: str, data: str):
    with open(path, 'w') as fd:
        fd.write(str(data))


def cgroup_set(group_name: str, limit: str, val: str):
    _mkdir(f'/sys/fs/cgroup/{group_name}')
    _write(f'/sys/fs/cgroup/{group_name}/{limit}', val)


def cgroup_assing(group_name: str, pid: int):
    _mkdir(f'/sys/fs/cgroup/{group_name}')
    _write(f'/sys/fs/cgroup/{group_name}/cgroup.procs', f"{pid}")
