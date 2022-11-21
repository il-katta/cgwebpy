import ctypes
import os
from typing import List, Dict

__all__ = [
    'cgroup_create',
    'cgroup_set',
    'cgroup_assing',
    'cgroup_exists',
    'cgroup_controllers_ls',
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


class struct_cgroup_mount_point(ctypes.Structure):
    _fields_ = [
        # Name of the controller.
        ("name", ctypes.c_char * FILENAME_MAX),
        # Mount point of the controller.
        ("path", ctypes.c_char * FILENAME_MAX),
    ]


# enum cgroup_file_type {
# 	CGROUP_FILE_TYPE_FILE,		/**< File. */
# 	CGROUP_FILE_TYPE_DIR,		/**< Directory. */
# 	CGROUP_FILE_TYPE_OTHER,		/**< Directory. @todo really? */
# };
class strunct_cgroup_file_info(ctypes.Structure):
    _fields_ = [
        # Type of the entity.
        ("type", ctypes.c_int),  # cgroup_file_type
        # Name of the entity.
        ("path", ctypes.c_char_p),
        # Name of its parent.
        ("parent", ctypes.c_char_p),
        # Full path to the entity. To get path relative to the root of the
        # walk, you must store its @c full_path (or its length)
        # and calculate the relative path by yourself.
        ("full_path", ctypes.c_char_p),
        # Depth of the entity, how many directories below the root of walk it is.
        ("depth", ctypes.c_short)
    ]


def c_str(val: str):
    return val.encode('utf-8')


def cgroup_lib():
    from ctypes.util import find_library

    libname = find_library("cgroup")
    if not libname:
        raise Exception("cgroup library not found")
    cgroup = ctypes.CDLL(libname)
    ret = cgroup.cgroup_init()
    if ret != 0:
        raise Exception(f"cgroup init failed with code {ret}")

    # cgroup.cgroup_new_cgroup.restype = struct_cgroup
    cgroup.cgroup_new_cgroup.restype = ctypes.c_void_p
    return cgroup


def cgroup_exists(group_name: str) -> bool:
    return os.path.exists(f'/sys/fs/cgroup/{group_name}')


def cgroup_create(group_name: str, controllers: List[str] = None):
    if controllers is None:
        controllers = ["cpu", "memory", "cpuacct"]
    cgroup = cgroup_lib()

    cg = cgroup.cgroup_new_cgroup(c_str(group_name))
    # TODO: test id cg is null and then error
    for controller_name in controllers:
        cgc = cgroup.cgroup_add_controller(ctypes.c_void_p(cg), c_str(controller_name))
    ret = cgroup.cgroup_create_cgroup(ctypes.c_void_p(cg), 0)
    if ret != 0:
        raise Exception(f"cgroup_create_cgroup(...) failed with code {ret}")
    cgroup.cgroup_free(ctypes.byref(ctypes.c_void_p(cg)))


def cgroup_controllers_ls() -> Dict[str, str]:
    cgroup = cgroup_lib()
    handle = ctypes.c_void_p()
    controller = struct_cgroup_mount_point()
    ret = cgroup.cgroup_get_controller_begin(ctypes.byref(handle), ctypes.byref(controller))
    controllers = {}
    while ret == 0:
        controllers[controller.name.decode('UTF-8')] = controller.path.decode('UTF-8')

        ret = cgroup.cgroup_get_controller_next(ctypes.byref(handle), ctypes.byref(controller))
    cgroup.cgroup_get_controller_end(ctypes.byref(handle))
    return controllers


def _mkdir(path: str):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def _write(path: str, data: str):
    with open(path, 'w') as fd:
        fd.write(str(data))


def _cgroup_path(controller: str = "cpu"):
    cc = cgroup_controllers_ls()
    return cc[controller]


def cgroup_set(group_name: str, limit: str, val: str, controller: str = "cpu"):
    ctr_path = _cgroup_path(controller)
    _mkdir(f'{ctr_path}/{group_name}')
    _write(f'{ctr_path}/{group_name}/{limit}', val)


def cgroup_assing(group_name: str, pid: int, controller: str = "cpu"):
    ctr_path = _cgroup_path(controller)
    _mkdir(f'/{ctr_path}/{group_name}')
    _write(f'/{ctr_path}/{group_name}/cgroup.procs', f"{pid}")
