from pathlib import Path

def object_dir():
    return Path(".git/lfs")

def local_object_dir(oid: str):
    return Path(object_dir(), oid[0:2], oid[2:4])

def object_path(oid: str):
    return local_object_dir(oid) / oid


