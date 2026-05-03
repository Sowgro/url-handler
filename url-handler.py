import json
import os
import shlex
import subprocess
import sys
from types import SimpleNamespace

CONFIG_PATH = os.path.join(
    os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config')),
    'url-handler', 'config.json'
)
MATCHERS = {
    'contains':   lambda a, b: b in a,
    'startswith': lambda a, b: a.startswith(b),
    'endswith':   lambda a, b: a.endswith(b)
}

def get_exec():
    for item in config.handlers:
        if MATCHERS[item.matcher](url, item.pattern):
            return item.exec
    return config.default.exec

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else ""

    try:
        with open(CONFIG_PATH) as f:
            config = json.load(f, object_hook=lambda d: SimpleNamespace(**d))
    except FileNotFoundError:
        subprocess.Popen(['url-handler-configuration'])
        sys.exit(1)

    cmd = shlex.split(get_exec())
    cmd = [i if i != '%u' else url for i in cmd]

    if os.path.exists('/.flatpak-info'):
        subprocess.Popen(['flatpak-spawn', '--host', *cmd])
    else:
        subprocess.Popen(cmd)