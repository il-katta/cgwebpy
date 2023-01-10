import ctypes
import logging
import os
from typing import List, Dict

__all__ = ['cgroup_create', 'cgroup_set', 'cgroup_assing', 'cgroup_exists', 'cgroup_controllers_ls', ]

CG_VALUE_MAX = 100
FILENAME_MAX = 4096
CG_CONTROLLER_MAX = 100


class struct_control_value(ctypes.Structure):
    _fields_ = [("name", ctypes.c_char * FILENAME_MAX), ("value", ctypes.c_char * CG_VALUE_MAX),
        ("dirty", ctypes.c_bool)]


class struct_cgroup(ctypes.Structure):
    pass


class struct_cgroup_controller(ctypes.Structure):
    _fields_ = [("name", ctypes.c_char * FILENAME_MAX), # ("values", struct_control_value * CG_VALUE_MAX),
        ("cgroup", ctypes.POINTER(struct_cgroup)), ("cgroup", ctypes.c_void_p), ("int", ctypes.c_int), ]


struct_cgroup._fields_ = [("name", ctypes.c_char * FILENAME_MAX),
    ("cgroup_controller", ctypes.POINTER(struct_cgroup_controller) * CG_VALUE_MAX), ("index", ctypes.c_int),
    ("tasks_uid", ctypes.c_uint), ("tasks_gid", ctypes.c_uint), ("task_fperm", ctypes.c_uint),
    ("control_uid", ctypes.c_uint), ("control_gid", ctypes.c_uint), ("control_fperm", ctypes.c_uint),
    ("control_dperm", ctypes.c_uint), ]


class struct_cgroup_mount_point(ctypes.Structure):
    _fields_ = [# Name of the controller.
        ("name", ctypes.c_char * FILENAME_MAX), # Mount point of the controller.
        ("path", ctypes.c_char * FILENAME_MAX), ]


# enum cgroup_file_type {
# 	CGROUP_FILE_TYPE_FILE,		/**< File. */
# 	CGROUP_FILE_TYPE_DIR,		/**< Directory. */
# 	CGROUP_FILE_TYPE_OTHER,		/**< Directory. @todo really? */
# };
class strunct_cgroup_file_info(ctypes.Structure):
    _fields_ = [# Type of the entity.
        ("type", ctypes.c_int),  # cgroup_file_type
        # Name of the entity.
        ("path", ctypes.c_char_p), # Name of its parent.
        ("parent", ctypes.c_char_p), # Full path to the entity. To get path relative to the root of the
        # walk, you must store its @c full_path (or its length)
        # and calculate the relative path by yourself.
        ("full_path", ctypes.c_char_p), # Depth of the entity, how many directories below the root of walk it is.
        ("depth", ctypes.c_short)]


class struct_cgroup_group_spec(ctypes.Structure):
    _fields_ = [("path", ctypes.c_char * FILENAME_MAX), ("controllers", ctypes.c_char_p * CG_CONTROLLER_MAX), ]


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

    # cgroup.cgroup_new_cgroup.restype = ctypes.c_void_p
    # cgroup.create_cgroup_from_name_value_pairs.restype = ctypes.c_void_p
    cgroup.cgroup_new_cgroup.restype = ctypes.POINTER(struct_cgroup)
    cgroup.create_cgroup_from_name_value_pairs.restype = ctypes.POINTER(struct_cgroup)
    return cgroup


def cgroup_exists(group_name: str) -> bool:
    return os.path.exists(f'/sys/fs/cgroup/{group_name}')


def cgroup_create(group_name: str, controllers: List[str] = None):
    if controllers is None:
        controllers = ["cpu", "memory", "cpuacct"]
    cgroup = cgroup_lib()
    logging.debug(f"cgroup_create: creating group '{group_name}' with {','.join(controllers)} controllers")
    cg = cgroup.cgroup_new_cgroup(c_str(group_name))
    # TODO: test id cg is null and then error
    for controller_name in controllers:
        cgc = cgroup.cgroup_add_controller(cg, c_str(controller_name))
    ret = cgroup.cgroup_create_cgroup(cg, 0)
    if ret != 0:
        raise Exception(f"cgroup_create_cgroup(...) failed with code {ret}")
    cgroup.cgroup_free(ctypes.byref(cg))


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


def cgroup_set(group_name: str, limit: str, val: str, controller: str = "cpu"):
    logging.debug(f"cgroup_set: setting '{group_name}/{limit}' = '{val}'")
    cgroup = cgroup_lib()
    name_value = struct_control_value()
    name_value.name = c_str(limit)
    name_value.value = c_str(val)
    name_value.dirty = ctypes.c_bool(False)
    cgroup.cgroup_init()
    dst_cgroup = cgroup.cgroup_new_cgroup(c_str(group_name))
    src_cgroup = cgroup.create_cgroup_from_name_value_pairs(c_str("tmp"), ctypes.byref(name_value), ctypes.c_int(1))
    ret = cgroup.cgroup_copy_cgroup(dst_cgroup, src_cgroup)
    if ret != 0:
        raise Exception("cgroup_copy_cgroup failed")

    ret = cgroup.cgroup_modify_cgroup(dst_cgroup)
    if ret != 0:
        raise Exception("cgroup_modify_cgroup failed")

    cgroup.cgroup_free(ctypes.byref(src_cgroup))
    cgroup.cgroup_free(ctypes.byref(dst_cgroup))


def cgroup_assing(group_name: str, pid: int, controllers: List[str]):
    cgroup = cgroup_lib()
    ret = cgroup.cgroup_change_cgroup_path(c_str(group_name), ctypes.c_int(pid),
        (ctypes.c_char_p * CG_CONTROLLER_MAX)(*[c_str(c) for c in controllers]))
    if ret != 0:
        raise Exception("cgroup_assing failed")
