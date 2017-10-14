
import contextlib
import json
import os
import re
import shlex
import signal
import socket
import subprocess
import sys
import time

from hourglass import bottle
import requests

TAG_TEMPLATE = 'THEREISASERVANT={}'
DELIMITER_PATTERN = '_p(\d+)p_'


class ServantImplGetter(object):

    def __init__(self):
        procs = ProcessUtils.find_pids_by_regex(TAG_TEMPLATE.format('\w+'))
        self._pidByTag = dict((tag, min(pids)) for tag, pids in procs.iteritems())

    def terminate(self):
        for _, pid in self._pidByTag.iteritems():
            ProcessUtils.terminate_servant_process(pid)

    def get_servant_impls(self):
        return [ServantImpl.attach(tag, pid) for tag, pid in self._pidByTag.iteritems()]


class ServantImpl(object):

    def __init__(self):
        self.name = None
        self.pid = None
        self.port = None

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return self.__dict__ != other.__dict__

    def to_str(self):
        return 'impl<name:{name}, pid:{pid}, port:{port}>'.format(**self.__dict__)

    @classmethod
    def attach(cls, tag, pid):
        ins = cls()
        name, port = cls.encode_tag(tag)
        ins.pid = pid
        ins.name = name
        ins.port = port
        return ins

    @classmethod
    def encode_tag(cls, tag):
        _ = tag.split('=')[-1]
        result = re.search(DELIMITER_PATTERN, _)
        assert result
        port_str = result.groups()[0]
        return _.replace(result.group(), ''), int(port_str)

    @classmethod
    def create(cls, name):
        ins = cls()
        ins.name = name
        port = NetworkUtils.find_free_port()
        ins.port = port
        name_and_port = '{}_p{}p_'.format(name, port)
        tag = TAG_TEMPLATE.format(name_and_port)
        env = os.environ.copy()
        env[tag.split('=')[0]] = tag.split('=')[-1]
        cmd_line = '/usr/bin/env python -m hourglass {} {}'.format(name, port)
        cmd_list = shlex.split(cmd_line)
        f_stdout = open('/tmp/{}.stdout.txt'.format(tag), 'w')
        f_stderr = open('/tmp/{}.stderr.txt'.format(tag), 'w')
        p = subprocess.Popen(cmd_list, env=env,
                             stdout=f_stdout, stderr=f_stderr, )
        ins.pid = p.pid
        return ins

    def terminate(self):
        pid = self.pid
        self.pid = None
        ProcessUtils.terminate_servant_process(pid)

    def is_alive(self):
        if self.pid is None:
            return False
        return ProcessUtils.process_exists(self.pid)


class ArgStruct(object):

    @classmethod
    def create(cls, kwargs):
        """

        Args:
            kwargs (dict):

        Returns:
            ArgStruct:
        """
        ins = cls()
        for k, v in kwargs.iteritems():
            setattr(ins, k, v)
        return ins

    def to_dict(self):
        return self.__dict__.copy()


class ServiceI(object):

    name = ''

    def health(self):
        """
        Expects the implementer to compose a dictionary that at least contains following fields:

        is_running (bool)
        up_time (float)

        Returns:
            dict:
        """
        raise NotImplementedError()

    def call(self, func, arg):
        """

        Args:
            func (str):
            arg (ArgStruct):

        Returns:
            ArgStruct:
        """
        raise NotImplementedError()


class DemoService(ServiceI):

    name = 'DemoService'

    def __init__(self):
        self.start_time = time.time()

    def health(self):
        d = {'is_running': True, 'up_time': time.time() - self.start_time}
        return d

    def call(self, func, arg):
        return ArgStruct.create({'demo': True})


class ServiceGetter(object):

    @classmethod
    def get(cls, name_or_path):
        """

        Args:
            name_or_path (str):

        Returns:
            ServiceI:
        """
        if '.' not in name_or_path:
            klass = eval(name_or_path)
        else:
            name = name_or_path.split('.')[-1]
            name_or_path = name_or_path.replace('.{}'.format(name), '')
            m = cls.import_module(name_or_path)
            assert m, 'can not import: {}'.format(name_or_path)
            klass = cls.get_symbol(m, name)
            assert klass, 'can not find class {}, from {}'.format(name, name_or_path)
        return klass()

    @classmethod
    def import_module(cls, path):
        try:
            return __import__(path, fromlist=[''])
        except ImportError, e:
            return None

    @classmethod
    def get_symbol(cls, mod, name):
        return getattr(mod, name, None)


class Servant(object):

    impl = None
    name = None

    @classmethod
    def _assert_service_name(cls, name):
        if not name:
            raise NotImplementedError('require a named service')

    @classmethod
    def create(cls, name):
        """

        Args:
            name (str)

        Returns:
            Servant:
        """
        cls._assert_service_name(name)
        ins = cls()
        ins.name = name
        list_impl = ServantImplGetter().get_servant_impls()
        for i in list_impl:
            if name == i.name:
                ins.impl = i
                return ins
        ins.impl = ServantImpl.create(name)
        ins.wait_for()
        return ins

    def __str__(self):
        return 'Servant(service: {})'.format(self.name)

    def wait_for(self, time_out=5.0, sleep=0.1, to_raise=False):
        while time_out >= 0.00001:
            try:
                self.service_health()
                return True
            except Exception, e:
                time.sleep(sleep)
            time_out -= sleep
        if to_raise:
            raise RuntimeError('service is not available, name {}, port {}'.format(self.impl.name, self.impl.port))
        return False

    def is_alive(self):
        return self.impl.is_alive()

    def terminate(self):
        self.impl.terminate()
        while self.is_alive():
            time.sleep(0.1)

    def service_health(self):
        return NetworkUtils.query_health(self.impl.port)

    def call_service(self, func, **kwargs):
        return NetworkUtils.send_request(func, self.impl.port, **kwargs)


class _EnvironmentGeneratorRegistry(type):

    _class_by_name = dict()

    @staticmethod
    def keys():
        return _EnvironmentGeneratorRegistry._class_by_name.keys()

    @staticmethod
    def add(k, v):
        _EnvironmentGeneratorRegistry._class_by_name[k] = v

    def __new__(cls, name, bases, attrs):
        klass = super(_EnvironmentGeneratorRegistry, cls).__new__(cls, name, bases, attrs)
        if name != 'EnvironmentGeneratorI':
            cls._class_by_name[name] = klass
        return klass


class EnvironmentGeneratorI(object):

    __metaclass__ = _EnvironmentGeneratorRegistry

    def generate(self):
        """

        Returns:
            dict: an environment dict that can be passed to subprocess.Popen()
        """
        raise NotImplementedError()


class EnvGeneratorUsingJsonFile(EnvironmentGeneratorI):

    def generate(self):
        return dict()


class EnvUtils(object):

    @staticmethod
    def get_protocol(path):
        return path.split('//')[0].lower()

    @staticmethod
    def register_generators(dot_paths):
        for _ in dot_paths:
            __import__(_, fromlist=[''])

    @staticmethod
    def get_generator_names():
        return _EnvironmentGeneratorRegistry.keys()


class NetworkUtils(object):

    host_url = 'http://localhost'

    @staticmethod
    def find_free_port():
        with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.bind(('', 0))
            return s.getsockname()[1]

    @classmethod
    def send_request(cls, func, port, **kwargs):
        url = '{}:{}/call/{}'.format(cls.host_url, port, func)
        r = requests.request('GET', url, json=kwargs)
        assert r.status_code == 200
        return json.loads(r.text)

    @classmethod
    def query_health(cls, port):
        url = '{}:{}/health'.format(cls.host_url, port)
        r = requests.request('GET', url)
        assert r.status_code == 200
        return json.loads(r.text)


class ProcessUtils(object):

    @classmethod
    def terminate_servant_process(cls, pid, block=False):
        if block:
            while cls.process_exists(pid):
                os.kill(pid, signal.SIGINT)
        else:
            os.kill(pid, signal.SIGINT)

    @staticmethod
    def process_exists(pid):
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    @classmethod
    def find_pid_by_tag(cls, tag):
        """

        Args:
            tag (str): a string (env var) set when the process starts
                       bash -c "USD=45 /usr/bin/env python"

        Returns:
            int: -1 if not found
        """
        for _ in os.listdir('/proc'):
            if not _.isdigit():
                continue
            env_file_path = os.path.join('/proc', _, 'environ')
            if not (os.path.exists(env_file_path) and os.access(env_file_path, os.R_OK)):
                continue
            if tag in cls._read_env(env_file_path):
                return int(_)
        return -1

    @classmethod
    def find_pids_by_regex(cls, pattern):
        """

        Args:
            pattern (str):

        Returns:
            dict:
        """
        procs = dict()
        defunct_pids = cls.find_defunct_processes()
        for _ in os.listdir('/proc'):
            if not _.isdigit():
                continue
            pid = int(_)
            if pid in defunct_pids:
                continue
            env_file_path = os.path.join('/proc', _, 'environ')
            if not (os.path.exists(env_file_path) and os.access(env_file_path, os.R_OK)):
                continue
            result = cls._search_env(env_file_path, pattern)
            if result:
                k = result.group()
                a_list = procs.get(k, list())
                a_list.append(pid)
                procs[k] = a_list
        return procs

    @staticmethod
    def find_defunct_processes():
        p = subprocess.Popen(['ps', 'aux'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.wait()
        pids = set()
        for l in p.stdout.readlines():
            if '<defunct>' not in l:
                continue
            r = re.search('\d+', l)
            if r:
                pids.add(int(r.group()))
        return pids

    @staticmethod
    def _read_env(env_file_path):
        with open(env_file_path, 'r') as fp:
            return fp.read()

    @staticmethod
    def _search_env(env_file_path, pattern):
        with open(env_file_path, 'r') as fp:
            text = fp.read()
        return re.search(pattern, text)


class Runner(object):

    @staticmethod
    def parse_args():
        assert len(sys.argv) == 3
        return sys.argv[1], int(sys.argv[2])

    @staticmethod
    def main(name_, port_):
        service = ServiceGetter.get(name_)

        def compute(args):
            return sum(args) / float(len(args)) + 3.14 if args else 0.0

        @bottle.route('/call/<func>')
        def call(func):
            json_blob = bottle.request.json
            arg_dict = dict()
            if json_blob is not None:
                arg_dict.update(json_blob)
            result = service.call(func, ArgStruct.create(arg_dict))
            return json.dumps(result.to_dict())

        @bottle.route('/health')
        def health():
            return json.dumps(service.health())

        bottle.run(host='localhost', port=port_)
        sys.exit(0)
