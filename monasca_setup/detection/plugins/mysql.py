# (C) Copyright 2015,2016 Hewlett Packard Enterprise Development Company LP

import logging
import os

import monasca_setup.agent_config
import monasca_setup.detection
from monasca_setup.detection.utils import find_process_name

log = logging.getLogger(__name__)

mysql_conf = '/root/.my.cnf'
HOST = 'localhost'
PORT = 3306
SOCKET = '/var/run/mysqld/mysqld.sock'


class MySQL(monasca_setup.detection.Plugin):

    """Detect MySQL daemons and setup configuration to monitor them.

        This plugin needs user/password info for mysql setup.
        It needs either the host ip or socket if using
        the default localhost hostname.  You cannot use
        the localhost name if using ssl.  This plugin
        accepts arguments, and if none are input it will
        try to read the default config file which is
        best placed in /root/.my.cnf in a format such as
        [client]
            user=root
            password=yourpassword
            host=padawan-ccp-c1-m1-mgmt
            ssl_ca=/etc/ssl/certs/ca-certificates.crt

    """

    def _detect(self):
        """Run detection, set self.available True if the service is detected.

        """
        process_exist = find_process_name('mysqld') is not None
        has_dependencies = self.dependencies_installed()
        has_args_or_config_file = (self.args is not None or
                                   os.path.isfile(mysql_conf))
        self.available = (process_exist and has_args_or_config_file and
                          has_dependencies)
        if not self.available:
            if not process_exist:
                log.error('MySQL process does not exist.')
            elif not has_args_or_config_file:
                log.error(('MySQL process exists but '
                           'configuration file was not found and '
                           'no arguments were given.'))
            elif not has_dependencies:
                log.error(('MySQL process exists but required dependence '
                           'PyMySQL is not installed.'))

    def _get_config(self):
        """Set the configuration to be used for connecting to mysql
        :return:
        """
        self.ssl_options = {}
        # reads default config file if no input parameters
        if self.args is None:
            self._read_config(mysql_conf)
        else:
            self.host = self.args.get('host', HOST)
            self.port = self.args.get('port', PORT)
            self.user = self.args.get('user', 'root')
            self.password = self.args.get('password', None)
            self.socket = self.args.get('socket', None)
            self.ssl_ca = self.args.get('ssl_ca', None)
            self.ssl_key = self.args.get('ssl_key', None)
            self.ssl_cert = self.args.get('ssl_cert', None)
        if self.ssl_ca is not None:
            self.ssl_options['ca'] = self.ssl_ca
        if self.ssl_key is not None:
            self.ssl_options['key'] = self.ssl_key
        if self.ssl_cert is not None:
            self.ssl_options['cert'] = self.ssl_cert
        if self.socket is None and (self.host == 'localhost' or self.host == '127.0.0.1'):
            self.socket = SOCKET

    def _read_config(self, config_file):
        """Read the configuration setting member variables as appropriate.
        :param config_file: The filename of the configuration to read and parse
        """
        log.info("\tUsing client credentials from {}".format(config_file))
        client_section = False
        self.user = None
        self.password = None
        self.host = HOST
        self.port = PORT
        self.socket = None
        self.ssl_ca = None
        self.ssl_key = None
        self.ssl_cert = None
        with open(mysql_conf, "r") as confFile:
            for row in confFile:
                if client_section:
                    if "user=" in row:
                        self.user = row.split("=")[1].strip()
                    if "password=" in row:
                        self.password = row.split("=")[1].strip()
                    if "port=" in row:
                        self.port = int(row.split("=")[1].strip())
                    if "host=" in row:
                        self.host = row.split("=")[1].strip()
                    if "socket=" in row:
                        self.socket = row.split("=")[1].strip()
                    if "ssl_ca=" in row:
                        self.ssl_ca = row.split("=")[1].strip()
                    if "ssl_key=" in row:
                        self.ssl_key = row.split("=")[1].strip()
                    if "ssl_cert=" in row:
                        self.ssl_cert = row.split("=")[1].strip()
                if "[client]" in row:
                    client_section = True

    def build_config(self):
        """Build the config as a Plugins object and return.

        """
        config = monasca_setup.agent_config.Plugins()
        # First watch the process
        config.merge(monasca_setup.detection.watch_process(['mysqld'], 'mysql'))
        log.info("\tWatching the mysqld process.")

        try:
            import pymysql
            self._get_config()
            # connection test
            pymysql.connect(host=self.host, user=self.user,
                            passwd=self.password, port=self.port,
                            unix_socket=self.socket, ssl=self.ssl_options)

            log.info("\tConnection test success.")
            config['mysql'] = {
                'init_config': None, 'instances':
                [{'name': self.host, 'server': self.host, 'port': self.port,
                  'user': self.user, 'pass': self.password,
                  'sock': self.socket, 'ssl_ca': self.ssl_ca,
                  'ssl_key': self.ssl_key, 'ssl_cert': self.ssl_cert}]}
        except ImportError as e:
            exception_msg = ('The mysql dependency PyMySQL is not '
                             'installed. {}'.format(e))
            log.exception(exception_msg)
            raise Exception(exception_msg)
        except pymysql.MySQLError as e:
            exception_msg = 'Could not connect to mysql. {}'.format(e)
            log.exception(exception_msg)
            raise Exception(exception_msg)
        except Exception as e:
            exception_msg = 'Error configuring the mysql check plugin. {}'.format(e)
            log.exception(exception_msg)
            raise Exception(exception_msg)

        return config

    def dependencies_installed(self):
        try:
            import pymysql
        except ImportError:
            return False
        return True
