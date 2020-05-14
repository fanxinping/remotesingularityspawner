"""RemoteDockerSpawner implementation"""
import os
import sys
import time
import socket
import ipaddress
from tornado import gen

import jupyterhub
from jupyterhub.spawner import Spawner
from traitlets import (
    Instance, Integer, Unicode, default
)

from jupyterhub.utils import random_port
import paramiko

def execute(channel, command):
    """Execute command and get remote PID"""

    command = command + '& pid=$!; echo PID=$pid'
    stdin, stdout, stderr = channel.exec_command(command)
    pid = int(stdout.readline().replace("PID=", ""))
    return pid, stdin, stdout, stderr

class SshConnection(object):
    """"
    The class is an adapter of a **paramiko.SSHClient used to avoid leak.
    """
    def __init__(self):
        self._client = paramiko.SSHClient()

    def __del__(self):
        if self._client:
            self._client.close()

    def connect(self, hostname, username, pkey):
        self._client.connect(hostname, username=username, pkey=pkey)

    def set_missing_host_key_policy(self, policy):
        self._client.set_missing_host_key_policy(policy)

    def exec_command(self, command):
        return self._client.exec_command(command)

class RemoteSingularitySpawner(Spawner):
    """A Spawner that just uses ssh to start remote processes."""
    singularity_exe_path = Unicode(
        default_value='singularity', config=True,
        help="The path of the executable file of singularity")
    singularity_container_path = Unicode(
        config=True,
        help="The path of the singularity container")
    nodelist = Unicode(
        config=True,
        help='The nodes the notebook instance can be spawned on. '
             'If ip address is not omitted, the vaildity of ip address will '
             'be checked. If ip address is omitted, the vaildity of hostname '
             'will be checked. The first vaild record will be set default '
             'node when spawn notebook instance. '
             'Format: "hostname1:ip_address1,hostname2:ip_address2", '
             '"hostname1:,hostname2:", ":ip_address1,:ip_address2" or '
             '"hostname1:,:ip_address2,hostname3:ip_address3"')
    home_path = Unicode(
        default_value='/home', config=True,
        help="The place where the users' home directory locate")
    default_bind_path = Unicode(
        default_value='', config=True,
        help='The extra path will be bind when spawn notebook servers'
             'Format: "/path1;/path2"')
    channel = Instance(SshConnection)
    pid = Integer(0)

    def __init__(self, **kwargs):
        super(RemoteSingularitySpawner, self).__init__(**kwargs)
        self.node_dict = {}
        self.node_list = []
        for node_record in self.nodelist.split(','):
            hostname, ip = node_record.strip().split(':')
            if hostname == '' and ip == '':
                pass
            elif hostname == '':
                try:
                    ipaddress.ip_address(ip)
                except ValueError as e:
                    self.log.debug(repr(e))
                    self.log.debug(f'ignore the node record: {node_record}')
                    continue
                self.node_dict.update({ip: ip})
                self.node_list.append(ip)
            elif ip == '':
                ip = None
                try:
                    ip = socket.gethostbyname(hostname)
                except socket.gaierror as e:
                    self.log.debug(repr(e))
                    self.log.debug(f'ignore the node record: {node_record}')
                    continue
                self.node_dict.update({hostname: ip})
                self.node_list.append(hostname)
            else:
                try:
                    ipaddress.ip_address(ip)
                except ValueError as e:
                    self.log.debug(repr(e))
                    self.log.debug(f'ignore the node record: {node_record}')
                    continue
                self.node_dict.update({hostname: ip})
                self.node_list.append(hostname)

    def load_state(self, state):
        """load pid from state"""
        super(RemoteSingularitySpawner, self).load_state(state)
        if 'pid' in state:
            self.pid = state['pid']

    def get_state(self):
        """add pid to state"""
        state = super(RemoteSingularitySpawner, self).get_state()
        if self.pid:
            state['pid'] = self.pid
        return state

    def clear_state(self):
        """clear pid state"""
        super(RemoteSingularitySpawner, self).clear_state()
        self.pid = 0

    @gen.coroutine
    def start(self):
        """Start the process"""
        self.pid = 0

        options = self.user_options
        self.log.debug(f"options: {options}")
        self.server_url = self.node_dict[options['host']]
        self.server_user = self.user.name
        self.log.debug(f"username: {self.server_user}")
        self.log.debug(f"home path: {os.path.expanduser('~')}")
        env = self.get_env()
        singularity_env = []

        for k, v in env.items():
            singularity_env.append(f"SINGULARITYENV_{k}={v}")
        dir_list = []
        if options['dirs'] != '':
            # bind dirs for user
            dir_list.extend([x.strip() for x in options['dirs'].split(';')])
        if self.default_bind_path != '':
            dir_list.extend(
                [x.strip() for x in self.default_bind_path.split(';')])
        if dir_list != []:
            singularity_env.append(
                f'SINGULARITY_BIND="{",".join(dir_list)}"')
        if jupyterhub.version_info < (0, 7):
            port = random_port()
        else:
            port = self.user.server.port

        cmd = [*singularity_env, self.singularity_exe_path, "exec",
               self.singularity_container_path]

        cmd.extend(self.cmd)
        jupyterhub_singleuser_args = self.get_args()
        # modify --ip in args to let jupyterhub-singleuser bind public ip
        for arg in jupyterhub_singleuser_args:
            if arg.startswith('--ip='):
                pass
            else:
                cmd.append(arg)
        cmd.append(f"--ip={self.server_url}")
        cmd.extend(['&>', f'/tmp/jupytersingler_{self.server_user}.log'])

        self.log.debug("Env: %s", str(env))
        self.channel = SshConnection()
        self.channel.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        rsa_file = os.path.join(os.path.join(
            self.home_path, self.server_user), '.ssh/id_rsa')
        self.log.debug(f"use the rsa file for {self.server_user}: {rsa_file}")
        k = paramiko.RSAKey.from_private_key_file(rsa_file)
        self.log.debug(f"home: {self.home_path}")
        self.log.debug(f"connecting ssh tunel server_url={self.server_url} "
                       f"username={self.server_user}")
        try:
            self.channel.connect(
                self.server_url, username=self.server_user, pkey=k)
        except Exception as e:
            self.log.debug(repr(e))
            sys.exit(1)
        self.log.info(f'cmd: {cmd}')
        self.log.info(f"Spawning {' '.join(cmd)}")
        # We use the jupyterhub-singleuser in singularity container, and
        # singularity launch the jupyterhub-singleuser, so the pid what we get
        # is singularity's, which means the ppid of jupyterhub-singleuser.
        # But it's ok to use this ppid to monitor and control the process
        # of jupyterhub-singleuser
        self.pid, stdin, stdout, stderr = execute(self.channel, ' '.join(cmd))
        self.log.info(f"Process PID is {self.pid}")

        if jupyterhub.version_info < (0, 7):
            # store on user for pre-jupyterhub-0.7:
            self.user.server.ip = self.server_url
            self.user.server.port = port
        # jupyterhub 0.7 prefers returning ip, port:
        return (self.server_url, port)

    @gen.coroutine
    def poll(self):
        """
        Poll the process
        We use kill -0 $PID to check whether the jupyterhub-singleuser is
        running on remote host. This method is only available on linux.
        """
        try:
            stdin, stdout, stderr = self.channel.exec_command(
                f"kill -0 {self.pid} &> /dev/null; echo status=$?")
        except Exception as e:
            self.log.debug(repr(e))
            return -1
        status = int(stdout.readline().replace("status=", ""))
        if status == 0:
            return None
        else:
            self.log.debug(f"Spawner on host {self.server_url} may be exit")
            return status

    @gen.coroutine
    def stop(self, now=False):
        """
        stop the subprocess
        we send singal to the process on host. softly kill will be tried three
        times before singal 9 send to the process
        """
        if self.pid == 0:
            # the jupyterhub-singleuser never be launched
            self.clear_state()
        self.log.debug(f"stop the spawner on host {self.server_url}")
        for _ in range(3):
            stdin, stdout, stderr = self.channel.exec_command(
                f"kill {self.pid}")
            time.sleep(1)
            stdin, stdout, stderr = self.channel.exec_command(
                f"kill -0 {self.pid} &> /dev/null; echo status=$?")
            status = int(stdout.readline().replace("status=", ""))
            if status == 0:
                break
        # have try three times, so send singal 9
        stdin, stdout, stderr = self.channel.exec_command(
            f"kill -9 {self.pid}")
        self.clear_state()

    @default('options_form')
    def _default_options_form(self):
        default_node = self.node_list[0]
        node_list_str = f'<option slected="selected" value="{default_node}">' \
                        f'{default_node}</option>'
        for node in self.node_list[1:]:
            node_list_str += f'<option value="{node}">{node}</option>'
        html = f"""
        Choose the host to spawn Notebook instance:
        <br>
        <select name="host">
        {node_list_str}
        </select>
        <br>
        Extra directory to mount when spawn:
        <br>
        <input name="dirs" val="" placeholder="e.g. /tmp;/home"></input>
        """
        return html

    def options_from_form(self, formdata):
        options = {}
        options["host"] = formdata["host"][0]
        options["dirs"] = formdata["dirs"][0]
        return options
