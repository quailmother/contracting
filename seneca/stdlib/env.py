from .bridge.orm import exports as orm_exports
from .bridge.hashing import exports as hash_exports
from .bridge.imports import exports as import_exports

def gather():
    env = {}
    env.update(orm_exports)
    env.update(hash_exports)
    env.update(import_exports)
    return env
