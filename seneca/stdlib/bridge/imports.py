import importlib

def import_contract(s: str):
    return importlib.import_module(s)


exports = {
    'importing.contract': import_contract
}
