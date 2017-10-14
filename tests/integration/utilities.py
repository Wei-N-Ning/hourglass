import subprocess
import os


class ProcessHelper(object):

    def __init__(self):
        self._processes = list()

    def clear(self):
        for p in self._processes:
            if p and p.poll() is not None:
                p.terminate()

    def create_process(self, tag):
        env = os.environ.copy()
        env[tag.split('=')[0]] = tag.split('=')[-1]
        p = subprocess.Popen('/usr/bin/env sleep 5'.format(tag),
                             shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             env=env)
        self._processes.append(p)
        return p