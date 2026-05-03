import os
import sys

url = sys.argv[1]

if url.startswith('https://open.spotify.com/'):
    os.system(f'flatpak run com.spotify.Client {url} &')
else:
    os.system(f'firefox {url} &')