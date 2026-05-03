import json
import os
import sys
from types import SimpleNamespace

def getMatcher(handler: str):
    match handler:
        case 'contains' : return lambda a, b: b in a
        case 'startswith': return lambda a, b: a.startswith(b)
        case 'endswith'  : return lambda a, b: a.endswith(b)

def getExec():
    for item in config.handlers:
        if getMatcher(item.matcher)(url, item.pattern):
            return item.exec
    return config.default.exec

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else ""
    config = json.load(open('config.json'), object_hook=lambda d: SimpleNamespace(**d))
    exec = getExec()
    os.system(exec.format(url) + ' &')