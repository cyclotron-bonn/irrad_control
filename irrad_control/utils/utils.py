import logging
import time
import fcntl
from subprocess import check_output, CalledProcessError

from irrad_control import lock_file, package_path


def get_current_git_branch(default='main'):

    try:
        # use git default installation via subprocess
        local_branches = str(check_output(['git', 'branch'],
                                          cwd=package_path,
                                          universal_newlines=True))
        # Fancy x, = [y] notation
        active_branch, = [b.replace('*', '').strip() for b in local_branches.split('\n') if '*' in b]

        return active_branch

    except (CalledProcessError, FileNotFoundError):
        return default


def check_zmq_addr(addr):
    """
    Check address format for zmq sockets

    Parameters
    ----------
    addr: str
        String of zmq address

    Returns
    -------
    bool:
        Whether the address is valid ZMQ address
    """

    if not isinstance(addr, str):
        logging.error("Address must be string")
        return False

    addr_components = addr.split(':')

    # Not TCP or UDP
    if len(addr_components) == 2:
        protocol, endpoint = addr_components
        if endpoint[:2] != '//':
            logging.error("Incorrect address format. Must be 'protocol://endpoint'")
            return False
        elif protocol in ('tcp', 'udp'):
            logging.error("Incorrect address format. Must be 'protocol://address:port' for 'tcp/udp' protocols")
            return False
    # TCP / UDP
    elif len(addr_components) == 3:
        protocol, ip, port = addr_components
        if ip[:2] != '//':
            logging.error("Incorrect address format. Must be 'protocol://address:port' for 'tcp/udp' protocols")
            return False

        if len(ip) >= 5:
            logging.error("ip not a valid ip: {}".format(ip))
            return False

        try:
            port = int(port)
            if not 0 < port < 2 ** 16 - 1:
                raise ValueError
        except ValueError:
            logging.error("'port' must be an integer between 1 and {} (16 bit)".format(2 ** 16 - 1))
            return False
    else:
        logging.error("Incorrect address format. Must be 'protocol://endpoint")
        return False

    return True if protocol else False


def create_pub_from_ctx(ctx, addr, hwm=10, delay=0.3):
    """
    Create and return a publisher socket from a given context

    Parameters
    ----------
    ctx: zmq.Context
        context from which the publisher is created
    addr: str
        address to which the publisher is connected
    hwm: int
        high-watermark for outgoing packages
    delay: float
        delay which allows the under-the-hood connections of ZMQ to be made
    """

    # Check if the address is valid
    if not check_zmq_addr(addr):
        return

    pub = ctx.socket(1)  # zmq.PUB == 1
    pub.set_hwm(hwm)
    pub.connect(addr)

    # Allow connection to be made
    # https://stackoverflow.com/questions/19442970/zeromq-have-to-sleep-before-send
    time.sleep(delay)

    return pub


class Lock:
    """
    Unix-style lock using file lock
    Mainly used to write to one irrad_control.pid file
    when there are more then 1 DAQProcess running on host
    """
    def __enter__(self):
        self.lfh = open(lock_file)
        fcntl.flock(self.lfh.fileno(), fcntl.LOCK_EX)

    def __exit__(self):
        fcntl.lockf(self.lfh.fileno(), fcntl.LOCK_UN)
        self.lfh.close()


def duration_str_from_secs(seconds, as_tuple=False):

    days = seconds / (24 * 3600)
    hours = (days % 1) * 24
    minutes = (hours % 1) * 60
    seconds = (minutes % 1) * 60

    # Return tuple in full days, hours, minutes and seconds
    res = tuple(int(x) for x in [days, hours, minutes, seconds])

    if as_tuple:
        return res
    else:
        return ", ".join(f"{a[0]}{a[1]}" for a in zip(res, 'dhms') if a[0]) or '0s'
