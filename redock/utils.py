# Utility functions for Redock.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: September 30, 2013
# URL: https://github.com/xolox/python-redock

# Standard library modules.
import fcntl
import os.path
import pickle
import pipes
import re
import socket
import subprocess
import sys
import urllib

# External dependencies.
from netifaces import interfaces, ifaddresses
from humanfriendly import format_path
from verboselogs import VerboseLogger

# Initialize a logger for this module.
logger = VerboseLogger(__name__)

# Directory on the host system with files generated by Redock.
REDOCK_CONFIG_DIR = os.path.expanduser('~/.redock')

# The absolute pathname of the serialized runtime configuration.
CONFIG_FILE = os.path.join(REDOCK_CONFIG_DIR, 'state.pickle')

# The version number of the runtime configuration format.
CONFIG_VERSION = 1

# The absolute pathname of the text file containing the selected Ubuntu mirror.
UBUNTU_MIRROR_FILE = os.path.join(REDOCK_CONFIG_DIR, 'ubuntu-mirror.txt')

# The absolute pathname of SSH public key generated by Redock.
PUBLIC_SSH_KEY = os.path.join(REDOCK_CONFIG_DIR, 'id_rsa.pub')

# The absolute pathname of SSH private key generated by Redock.
PRIVATE_SSH_KEY = os.path.join(REDOCK_CONFIG_DIR, 'id_rsa')

class Config(object):

    # TODO The Config class as it is written now is a bit tricky. I feel
    #      like it should be a lot simpler! I hope this is possible :-)

    """
    :py:class:`Config` encapsulates the bits of runtime configuration that
    Redock needs to persist to disk (to share state in between runs of Redock).
    UNIX file locking is used to guarantee that the datafile is not written to
    simultaneously by multiple processes (that could corrupt the state).

    To use this class to update the configuration, use it like a context
    manager, like this:

    >>> config = Config()
    >>> with config as state:
    ...   state['containers'].clear()

    When used like this, ``state`` is a dictionary which is saved to disk when
    the ``with`` block ends without raising an exception.
    """

    def __init__(self):
        self.logger = logger
        self.handle = None
        self.state = {}

    def load(self, exists=True):
        """
        Load the runtime configuration from disk. If the file doesn't exist yet
        an empty configuration is returned. The configuration contains a
        version number which enables graceful upgrades to the format.

        :returns: A dictionary with runtime configuration data.
        """
        if exists:
            self.logger.verbose("Loading runtime configuration from %s ..", format_path(CONFIG_FILE))
        state = {}
        handle = self.handle
        close = False
        if (not handle) and os.path.isfile(CONFIG_FILE):
            handle = open(CONFIG_FILE)
            close = True
        if exists and handle:
            state = pickle.load(handle)
            if close:
                handle.close()
        version = state.get('version', 0)
        if version == 0:
            state['containers'] = dict()
            state['version'] = CONFIG_VERSION
        self.logger.debug("Initialized configuration: %r", state)
        return state

    def __enter__(self):
        exists = os.path.isfile(CONFIG_FILE)
        self.handle = open(CONFIG_FILE, 'r+' if exists else 'w')
        fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
        self.state = self.load(exists=exists)
        return self.state

    def __exit__(self, type, value, traceback):
        if type is None:
            self.logger.verbose("Saving configuration to %s ..", format_path(CONFIG_FILE))
            self.handle.seek(0)
            pickle.dump(self.state, self.handle)
            self.handle.truncate()
        else:
            self.logger.warn("Not saving configuration! (an exception was raised: %s)", value)
        fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close()
        self.handle = None

class RemoteTerminal(object):

    """
    Attach to a running Docker container and show the output of the command(s)
    inside the container on the host's terminal. Can be used as a context
    manager or by manually calling :py:func:`RemoteTerminal.attach()` and
    :py:func:`RemoteTerminal.detach()`.
    """

    def __init__(self, container_id):
        """
        Initialize the context manager for the ``docker attach`` process.

        :param container_id: The id of the container to attach to (a string).
        """
        self.container_id = container_id

    def attach(self):
        """
        Start the ``docker attach`` subprocess.
        """
        logger.verbose("Attaching to terminal of container %s ..", summarize_id(self.container_id))
        self.subprocess = subprocess.Popen(['docker', 'attach', self.container_id], stdin=open(os.devnull), stdout=sys.stderr)

    def detach(self):
        """
        Kill the ``docker attach`` subprocess.
        """
        logger.verbose("Detaching from container %s ..", summarize_id(self.container_id))
        self.subprocess.kill()

    def __enter__(self):
        self.attach()

    def __exit__(self, type, value, traceback):
        self.detach()

def select_ubuntu_mirror(force=False):
    """
    Find an Ubuntu mirror that is geographically close to the current
    location for use inside Docker containers. We remember the choice in a
    file on the host system so that we always configure the same mirror in
    Docker containers (if you change the mirror, ``apt-get`` has to
    download all package metadata again, wasting a lot of time).
    """
    create_configuration_directory()
    if not os.path.isfile(UBUNTU_MIRROR_FILE):
        url = 'http://mirrors.ubuntu.com/mirrors.txt'
        logger.debug("Finding nearby Ubuntu package mirror using %s ..", url)
        mirror = urllib.urlopen(url).readline().strip()
        with open(UBUNTU_MIRROR_FILE, 'w') as handle:
            handle.write('%s\n' % mirror)
    with open(UBUNTU_MIRROR_FILE) as handle:
        mirror = handle.read().strip()
        logger.debug("Selected Ubuntu package mirror: %s", mirror)
    return mirror

def get_ssh_public_key():
    """
    Get the contents of the SSH public key generated by Redock for use inside
    containers. If the SSH key pair hasn't been generated yet, it will be
    generated using :py:func:`generate_ssh_key_pair()`.

    :returns: The contents of the ``id_rsa.pub`` file.
    """
    if not os.path.isfile(PUBLIC_SSH_KEY):
        generate_ssh_key_pair()
    with open(PUBLIC_SSH_KEY) as handle:
        return handle.read().strip()

def generate_ssh_key_pair():
    """
    Generate an SSH key pair for communication between the host system and
    containers created with Redock. Requires the ``ssh-keygen`` program.
    """
    create_configuration_directory()
    logger.verbose("Checking if we need to generate a new SSH key pair ..")
    if os.path.isfile(PRIVATE_SSH_KEY):
        logger.verbose("SSH key pair was previously generated: %s", format_path(PRIVATE_SSH_KEY))
        return
    logger.info("No existing SSH key pair found, generating new key: %s", format_path(PRIVATE_SSH_KEY))
    command = ['ssh-keygen', '-t', 'rsa', '-f', PRIVATE_SSH_KEY, '-N', '', '-C', 'root@%s' % socket.gethostname()]
    ssh_keygen = subprocess.Popen(command)
    if ssh_keygen.wait() != 0:
        msg = "Failed to generate SSH key pair! (command exited with code %d: %s)"
        raise Exception, msg % (ssh_keygen.returncode, quote_command_line(command))

def find_local_ip_addresses():
    """
    To connect to a running Docker container over TCP we need to connect to a
    specific port number on an IP address associated with a local network
    interface on the host system (specifically *not* a loop back interface).

    :returns: A :py:class:`set` of IP addresses associated with local network
              interfaces.
    """
    ip_addresses = set()
    for name in sorted(interfaces(), key=str.lower):
        for addresses in ifaddresses(name).values():
            for properties in addresses:
                address = properties.get('addr')
                # As mentioned above we're specifically *not* interested in loop back interfaces.
                if address.startswith('127.'):
                    continue
                # I'm not interested in IPv6 addresses right now.
                if ':' in address:
                    continue
                if address:
                    ip_addresses.add(address)
    return ip_addresses

def apt_get_install(*packages):
    """
    Generate a command to install the given packages with ``apt-get``.

    :param packages: The names of the package(s) to be installed.
    :returns: The ``ap-get`` command line as a single string.
    """
    command = ['DEBIAN_FRONTEND=noninteractive',
               'apt-get', 'install', '-q', '-y',
               '--no-install-recommends']
    return quote_command_line(command + list(packages))

def quote_command_line(command):
    """
    Quote the tokens in a shell command line.

    :param command: A list with the command name and arguments.
    :returns: The command line as a single string.
    """
    return ' '.join(pipes.quote(s) for s in command)

def summarize_id(id):
    """
    Docker uses hexadecimal strings of 65 characters to uniquely identify
    containers, images and other objects. Docker's API almost always reports
    full IDs of 65 characters, but the ``docker`` program abbreviates these IDs
    to 12 characters in the user interface. We do the same because it makes the
    output more user friendly.

    :param id: A hexadecimal ID of 65 characters.
    :returns: A summarized ID of 12 characters.
    """
    return id[:12]

def slug(text):
    """
    Convert text to a "slug". Used by
    :py:attr:`redock.api.Container.ssh_alias`.

    :param text: The original text, e.g. "Some Random Text!".
    :returns: The slug text, e.g. "some-random-text".
    """
    slug = re.sub('[^a-z0-9]+', '-', text.lower())
    return slug.strip('-')

def create_configuration_directory():
    """
    Make sure Redock's local configuration directory exists.
    """
    if not os.path.isdir(REDOCK_CONFIG_DIR):
        logger.info("Creating directory: %s", format_path(REDOCK_CONFIG_DIR))
        os.makedirs(REDOCK_CONFIG_DIR)

# vim: ts=4 sw=4 et
