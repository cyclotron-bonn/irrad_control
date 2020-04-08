import os
import sys
import logging
import paramiko
import subprocess
from collections import defaultdict
from irrad_control import package_path, config_server_script


class ProcessManager(object):
    """
    Class to handle subprocesses created within irrad_control. Enables communication via SSH2 implementation of
    the paramiko library between host PC and Raspberry Pi server to run server process which handles the data
    acquisition, XY-stage etc.
    """

    def __init__(self):
        super(ProcessManager, self).__init__()

        # Server connection related; multiple servers can exist
        self.server = {}
        self.client = {}

        # Interpreter process; only one
        self.interpreter_proc = None

        # Keep track of processes which have been started
        self.active_pids = defaultdict(dict)

        self.n_checks = 0

    def connect_to_server(self, hostname, username):

        # Update if we have no server credentials
        if hostname not in self.server:

            # Update server dict
            self.server[hostname] = username

        if hostname not in self.client:

            # Setup SSH client and connect to server
            self.client[hostname] = paramiko.SSHClient()
            self.client[hostname].set_missing_host_key_policy(paramiko.AutoAddPolicy())

            logging.info('Connecting to server {}@{}...'.format(username, hostname))

            # Try to connect
            try:
                self.client[hostname].connect(hostname=hostname, username=username)
            # Something went wrong
            except (paramiko.BadHostKeyException, paramiko.AuthenticationException, paramiko.SSHException) as e:
                # We need to add key, let user know
                msg = "Server's host key could not be verified. Try creating key on host PC via" \
                      " ssh-keygen and copy to server via ssh-copy-id!"
                raise e(msg)

            # Success
            logging.info('Successfully connected to server {}@{}!'.format(username, hostname))

        else:

            logging.info('Already connected to server {}@{}!'.format(username, hostname))

    def configure_server(self, hostname, py_version=None, py_update=False, git_pull=False, branch=False):

        # Check whether remote server already has the script in the default installation path
        remote_script = '/home/{}/irrad_control/irrad_control/configure_server.sh'.format(self.server[hostname])
        cmd_check_script = 'if [[ -f {} ]]; then echo "1"; else echo "0"; fi'.format(remote_script, self.server[hostname])
        remote_script_exists = int(self._exec_cmd(hostname=hostname, cmd=cmd_check_script, return_stdout=True)[0]) == 1

        # If no remote script is found, copy script from host PC to server
        if not remote_script_exists:
            remote_script = '/home/{}/config_server.sh'.format(self.server[hostname])
            self.copy_to_server(hostname, config_server_script, remote_script)

        # Add args to call remote script
        _rs = remote_script
        _rs += ' -v={}'.format(sys.version_info[0] if py_version is None else py_version)
        _rs += ' -u' if py_update else ''
        _rs += ' -p' if git_pull else ''
        _rs += '' if not branch else ' -b={}'.format(branch)

        # Run script to determine whether server RPi has miniconda and all packages installed
        self._exec_cmd(hostname, 'bash {}'.format(_rs), log_stdout=True)

        # Remove script if we had to copy it
        if not remote_script_exists:
            self._exec_cmd(hostname, 'rm {}'.format(remote_script))

    def start_server_process(self, hostname, port):

        host_user = self.server[hostname] + '@' + hostname

        logging.info('Attempting to start server process at host {} listening to port {}...'.format(host_user, port))

        # Check if there is a server process running on hostname
        check_server_ps = self.check_process_status(hostname=hostname, name='irrad_server')

        # A server process is already running
        if check_server_ps[hostname]:
            logging.warning("A server process is already running on {}. Only one server process can be run on a host".format(host_user))
            return check_server_ps

        self._exec_cmd(hostname, 'nohup bash /home/{}/start_irrad_server.sh {} &'.format(self.server[hostname], port))

    def start_interpreter_process(self, setup_yaml):

        logging.info('Starting interpreter process...')

        self.interpreter_proc = self._call_script(script=os.path.join(package_path, 'irrad_interpreter.py'), args=setup_yaml)

    def _call_script(self, script, args, cmd=None):

        # Call the interpreter subprocess with the same python executable that runs irrad_control
        return subprocess.Popen('{} {} {}'.format(sys.executable if not cmd else cmd, script, args),
                                shell=True,
                                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0)

    def _exec_cmd(self, hostname, cmd, log_stdout=False, return_stdout=False):
        """Execute command on server using paramikos SSH implementation"""

        # Sanity check
        if hostname not in self.client:
            logging.warning("SSH-client not connected to server. Call {}.connect_to_server method."
                            .format(self.__class__.__name__))
            return

        # Execute; this is non-blocking so we have to wait until cmd has been transmitted to server before closing
        stdin, stdout, stderr = self.client[hostname].exec_command(cmd)

        # No writing to stdin and stdout happens
        stdin.close()
        stdout.channel.shutdown_write()

        stdout_lines = []

        if log_stdout or return_stdout:
            while not stdout.channel.exit_status_ready():
                msg = stdout.readline().strip()
                if msg:
                    stdout_lines.append(msg)
                    if log_stdout:
                        logging.info(msg)

        stdout.close()
        stderr.close()

        return stdout_lines if return_stdout else None

    def copy_to_server(self, hostname, local_filepath, remote_filepath):
        """Copy local file at local_filepath to server at remote_filepath"""

        sftp = self.client[hostname].open_sftp()
        sftp.put(local_filepath, remote_filepath)
        sftp.close()

    def register_pid(self, hostname, pid, name=None):
        """Register a *PID* on a *hostname* for monitoring its 'is_alive' status"""
        self.active_pids[hostname][pid] = {'name': name, 'active': True}

    def check_process_status(self, hostname, pid=None, name=None):

        if pid is None and name is None:
            raise ValueError("Either a PID or a process name has to be given")

        if not (any(isinstance(pid, x) for x in (int, list, tuple)) or pid is None):
            raise ValueError("PID has to be integer or list/tuple of integers")

        if not (any(isinstance(name, x) for x in (str, list, tuple)) or name is None):
            raise ValueError("Name has to be string or list/tuple of strings")

        # If we're here, everything should be fine
        pid = [pid] if isinstance(pid, int) or pid is None else pid
        name = [name] if isinstance(name, str) or name is None else name

        # Bash command outputting all running PIDs / names, separated by a whitespace
        cmd = "ps -e | awk '{print $1,$4}' | grep " + "'{}'".format(("\|").join(str(x) for x in name + pid if x is not None))

        ps_dict = {hostname: {}}

        # We are checking on the status of some remote process
        if hostname in self.client:
            ps_list = self._exec_cmd(hostname=hostname, cmd=cmd, return_stdout=True)
        else:
            try:
                ps_list = subprocess.check_output(cmd, shell=True).splitlines()
            except subprocess.CalledProcessError:
                ps_list = []

        for ps in ps_list:
            cur_pid, cur_name = ps.split()
            cur_pid, cur_name = int(cur_pid), str(cur_name)
            if cur_pid in pid or cur_name in name:
                ps_dict[hostname][cur_pid] = cur_name

        return ps_dict

    def check_active_processes(self):
        """Function checking whether processes are alive"""

        # Increment that bad boy; maybe we want to terminate if number of checks get's too large
        self.n_checks += 1

        for host in self.active_pids:

            host_pids = self.check_process_status(hostname=host, pid=self.active_pids[host].keys())

            for pid in self.active_pids[host]:

                if pid in host_pids[host]:
                    self.active_pids[host][pid]['active'] = True
                    self.active_pids[host][pid]['name'] = host_pids[host][pid]
                else:
                    self.active_pids[host][pid]['active'] = False

                msg = "Process {} with PID {} is {}active.".format(self.active_pids[host][pid]['name'],
                                                                   pid, '' if self.active_pids[host][pid]['active'] else 'not ')
                logging.debug(msg)

    def kill_proc(self, hostname, pid=None, name=None):

        # We're killing a process on a server
        if hostname in self.client:
            logging.info('Killing server PC process with PID {}...'.format(pid))

            if pid is not None:
                self._exec_cmd(hostname, 'kill {}'.format(pid))

            if name is not None:
                self._exec_cmd(hostname, 'killall {}'.format(name))

        else:

            logging.info('Killing host PC process with PID {}...'.format(pid))

            subprocess.Popen(['kill', pid])
