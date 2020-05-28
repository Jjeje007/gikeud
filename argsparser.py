# -*- coding: utf-8 -*-
# -*- python -*- 
# Copyright © 2019,2020: Venturi Jérôme : jerome dot Venturi at gmail dot com
# Distributed under the terms of the GNU General Public License v3

import re
import argparse
import sys
from gitmanager import check_git_dir

# TODO: add --dry-run opt to not write to statefile 
# TODO  argcomplete --> https://github.com/kislyuk/argcomplete
# TODO  make opt word not all required : like argparse default if --available you can write --a 
#       and it's match if there nothing eles which start by --a . Same here with for exemple:
#       --count : this can be both|session|overall -> for both you could write 'b' or 'bo' or 'bot' or ...

class CustomArgsCheck:
    """
    Advanced arguments checker which implant specific parsing
    """
    def __init__(self):
        # this is shared across method
        self.shared_timestamp = '(?:\:r|\:u)?(?:\:[1-5])?'
        self.shared_date = '(?:\:s|\:m|\:l|\:f)?'
    
    def _check_args_interval(self, interval):
        """
        Checking interval typo and converting to seconds
        """
        # By pass to implant ClientParserHandler args parse 
        if 'display' in interval:
            pattern = re.compile(r'^display(?:\:r|\:u|\:seconds)?(?:\:[1-5])?$')
            if not pattern.match(interval):
                self.parser.error(f'\'{interval}\' is not an valid interval !')
            return interval
        
        pattern = re.compile(r'^(?:\d+(?:d|w|h){1})+$')
        if not pattern.match(interval):
            self.parser.error(f'\'{interval}\' is not an valid interval !')
        pattern = re.compile(r'(\d+)(\w{1})')
        converted = 0
        for match in pattern.finditer(interval):
            if match.group(2) == 'h':
                converted += int(match.group(1)) * 3600
            elif match.group(2) == 'd':
                converted += int(match.group(1)) * 86400
            elif match.group(2) == 'w':
                converted += int(match.group(1)) * 604800
            else:
                # This should'nt happend :)
                self.parser.error(f'Got invalid interval while parsing: \'{match.string}\', ', 
                                  f'regex \'{match.re}\'.')
        # Ok so converted should be greater or equal to 86400 (mini git interval)
        if converted < 86400:
            self.parser.error(f'Interval \'{interval}\' too small: minimum is 24 hours / 1 day !')
        return converted
        
    def _check_args_git(self, repo):
        """
        Checking if repo is a valid git repo 
        """
        mygitdir = check_git_dir(repo)
        if not mygitdir[0]:
            if mygitdir[1] == 'dir':
                self.parser.error(f'\'{repo}\' is not a valid path !')
            elif mygitdir[1] == 'read':
                self.parser.error(f'\'{repo}\' is not a readable dir !')
            elif mygitdir[1] == 'git':
                self.parser.error(f'\'{repo}\' is not a valid git repo !')
        # Make sure we have an '/' at the end
        repo = repo.rstrip('/') 
        repo = f'{repo}/'
        return repo


class DaemonParserHandler(CustomArgsCheck):
    """Handle daemon arguments parsing"""
    def __init__(self, pathdir, version):
        prog = 'gikeud'
        self.pathdir = pathdir
        self.parser = argparse.ArgumentParser(description='Daemon which automate git kernel update.' , 
                                              epilog='By default, %(prog)s will start in log level \'info\'.'
                                              + ' Interactive mode: log to terminal. Init mode: log to' 
                                              + 'system log, debug to \'{0}\''.format(self.pathdir['debuglog'])
                                              + ' and stderr to \'{0}\'.'.format(self.pathdir['fdlog']))
        # Optionnal arguments 
        # Changing title to reflect other title 
        # thx --> https://stackoverflow.com/a/16981688/11869956
        self.parser._optionals.title = '<optional arguments>'
        self.parser.add_argument('-v', 
                            '--version', 
                            action = 'version', 
                            version = '%(prog)s: version ' + version + 
                            ' - Copyright (C) 2019-2020 Jérôme Venturi, <jerome dot venturi at gmail dot com> - License: GNU/GPL V3.')
        # Logging Options
        log_arg = self.parser.add_argument_group('<log options>')
        log_arg.add_argument('-d', 
                        '--debug', 
                        help = f'start daemon in log level \'debugg\'.', 
                        action = 'store_true')
        log_arg.add_argument('-q', 
                        '--quiet', 
                        help = 'start daemon in log level \'quiet\'.', 
                        action = 'store_true')
        # Git Options
        git_arg = self.parser.add_argument_group('<git options>')
        git_arg.add_argument('-r', 
                        '--repo', 
                        help = 'specify git kernel \'dir\' (default=\'/usr/src/linux\').',
                        default = '/usr/src/linux',
                        type=self._check_args_git,
                        metavar = 'dir')
        git_arg.add_argument('-p', 
                        '--pull', 
                        help = 'pull interval. Where \'int\' should be this form: 1w = 1 week, 1d = 1 day and 1h = 1 hour. Can be add together, for exemple: 2w1d12h, 2d1h... Minimum is 1d (1 day) and default is 1d (1 day).',
                        default = 604800,
                        type=self._check_args_interval,
                        metavar = 'int')
    def parsing(self):
        self.args = self.parser.parse_args()
        return self.args

# TODO : Interactive shell  : https://code-maven.com/interactive-shell-with-cmd-in-python

class ClientParserHandler(CustomArgsCheck):
    """Handle client arguments parsing"""
    def __init__(self, version):
        # Init super class
        super().__init__()
        prog = 'gikeud-cli'
        self.parser = argparse.ArgumentParser(description='Dbus client for gikeud daemon. Control and '
                                              ' retrieve informations from an already running daemon.')
        ## Global options
        self.parser.add_argument('-v', 
                                '--version', 
                                action = 'version', 
                                version = '%(prog)s: version ' + version + 
                                ' - Copyright (C) 2019-2020 Jérôme Venturi, <jerome dot venturi at gmail dot com> - License: GNU/GPL V3.')
        self.parser.add_argument('-m',
                                 '--machine',
                                 action = 'store_true',
                                 help = 'display output to machine language.')
        self.parser.add_argument('-q',
                                 '--quiet',
                                 action = 'store_true',
                                 help = 'disable error messages.')
        
        self.parser._optionals.title = '<optional arguments>'
        ## Gitdbus options
        git_args = self.parser.add_argument_group('<git options>')
        git_args.add_argument('--available',
                              metavar = 'avl',
                              choices = ['branch', 'kernel'],
                              help = 'Display available \'kernel\' or \'branch\' update.')
        git_args.add_argument('--reset',
                              action = 'store_true',
                              help = 'Reset pull error so daemon can resume is operation and forced pull.')
        
        
    def parsing(self):
        args = self.parser.parse_args()
        # Print usage if no arg has been given
        noarg = True
        for arg in vars(args):
            if getattr(args, arg):
                noarg = False
                break
        if noarg:
            self.parser.print_usage(file=sys.stderr)
            self.parser.exit(status=1)
        # everything is ok ;)
        return args

