#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -*- python -*- 
# Starting : 2019-08-08

# This is a GIt KErnel Updater Daemon
# Copyright © 2019,2020: Venturi Jérôme : jerome dot Venturi at gmail dot com
# Distributed under the terms of the GNU General Public License v3


# TODO TODO TODO don't run as root ! investigate !
# TODO : exit gracefully 
# TODO : debug log level !

__version__ = "dev"
prog_name = 'gikeud'  

pathdir = {
    'prog_name'     :   prog_name,
    'prog_version'  :   __version__,
    'basedir'       :   '/var/lib/' + prog_name,
    'logdir'        :   '/var/log/' + prog_name,
    'debuglog'      :   '/var/log/' + prog_name + '/debug.log',
    'fdlog'         :   '/var/log/' + prog_name + '/stderr.log', 
    'statelog'      :   '/var/lib/' + prog_name + '/state.info',
    'gitlog'        :   '/var/log/' + prog_name + '/git.log'
    }

# Default basic logging, this will handle earlier error when
# daemon is run using /etc/init.d/
# It will be re-config when all module will be loaded
import sys
import logging
# Custom level name share across all logger
logging.addLevelName(logging.CRITICAL, '[Crit ]')
logging.addLevelName(logging.ERROR,    '[Error]')
logging.addLevelName(logging.WARNING,  '[Warn ]')
logging.addLevelName(logging.INFO,     '[Info ]')
logging.addLevelName(logging.DEBUG,    '[Debug]')

if not sys.stdout.isatty() or '--fakeinit' in sys.argv\
   or '-f' in sys.argv:
    if '--fakeinit' in sys.argv or '-f' in sys.argv:
        print('Running fake init.', file=sys.stderr)
    # Get RootLogger 
    root_logger = logging.getLogger()
    # So redirect stderr to syslog (for the moment)
    from lib.logger import RedirectFdToLogger
    from lib.logger import LogErrorFilter
    from lib.logger import LogLevelFilter
    fd_handler_syslog = logging.handlers.SysLogHandler(address='/dev/log',facility='daemon')
    fd_formatter_syslog = logging.Formatter('{0} %(levelname)s  %(message)s'.format(prog_name))
    fd_handler_syslog.setFormatter(fd_formatter_syslog)
    fd_handler_syslog.setLevel(40)
    root_logger.addHandler(fd_handler_syslog)
    fd2 = RedirectFdToLogger(root_logger)
    sys.stderr = fd2
    display_init_tty = 'Log are located to {0}'.format(pathdir['debuglog'])
else:
    # import here what is necessary to handle logging when 
    # running in a terminal
    from lib.logger import LogLevelFormatter
    display_init_tty = ''

import argparse
import pathlib
import time
import re
import errno
import asyncio
import threading

from gitdbus import GitDbus
from gitmanager import check_git_dir
from gitmanager import GitWatcher
from argsparser import DaemonParserHandler

try:
    from gi.repository import GLib
    from pydbus import SystemBus
except Exception as exc:
    print(f'Error: unexcept error while loading dbus bindings: {exc}', file=sys.stderr)
    print('Error: exiting with status \'1\'.', file=sys.stderr)
    sys.exit(1)



class MainDaemon(threading.Thread):
    def __init__(self, mygit, *args, **kwargs):
        self.logger_name = f'::{__name__}::MainDaemonThread::'
        logger = logging.getLogger(f'{self.logger_name}init::')
        super().__init__(*args, **kwargs)
        self.mygit = mygit
        # Init asyncio loop
        self.scheduler = asyncio.new_event_loop()
        # TEST Change te log level of asyncio 
        # to be the same as RootLogger
        currentlevel = logger.getEffectiveLevel()
        logger.debug(f'Setting log level for asyncio to: {currentlevel}')
        logging.getLogger('asyncio').setLevel(currentlevel)
    
    def run(self):
        logger = logging.getLogger(f'{self.logger_name}run::')
        logger.info('Start up completed.')
        while True:
            # TEST workaround but it have more latency 
            if self.mygit['watcher'].tasks['pull']['inprogress']:
                self.mygit['manager'].pull_state = True
            else:
                self.mygit['manager'].pull_state = True
            ### End workaround
            # TEST now watcher will handle update call depending on condition 
            # TEST Only update every 30s 
            if self.mygit['manager'].update:
                # pull have been run, request refresh 
                if self.mygit['watcher'].tasks['pull']['requests']['pending'] \
                    and not self.mygit['manager'].pull['status'] \
                    and not self.mygit['watcher'].tasks['pull']['inprogress'] \
                    and not self.mygit['watcher'].repo_read:
                    # Wait until there is nothing more to read (so pack all the request together)
                    # TODO we could wait 10s before processing ? (so make sure every thing is packed)
                    # Any way this have to be more TEST-ed
                    # Ok enumerate request(s) on pull and save latest
                    # This will 'block' to the latest know request (know in main)
                    pull_requests = self.mygit['watcher'].tasks['pull']['requests']['pending'].copy()
                    msg = ''
                    if len(pull_requests) > 1:
                        msg = 's'
                    logger.debug(f'Got refresh request{msg}'
                                    + ' (id{0}={1})'.format(msg, '|'.join(pull_requests)) 
                                    + ' for git pull informations.')
                    # Immediatly send back latest request proceed so watcher can remove all the already proceed
                    # requests
                    self.mygit['watcher'].tasks['pull']['requests']['completed'] = pull_requests[-1]
                    # TEST Don't recompute here
                    self.mygit['manager'].pull['recompute'] = False
                    self.mygit['manager'].check_pull()
                    self.mygit['manager'].get_all_kernel()
                    self.mygit['manager'].get_branch('remote')
                    self.mygit['manager'].update = False
                # Other git repo related request(s)
                if self.mygit['watcher'].tasks['repo']['requests']['pending'] \
                    and not self.mygit['watcher'].repo_read:
                    # Same here as well
                    repo_requests = self.mygit['watcher'].tasks['repo']['requests']['pending'].copy()
                    msg = ''
                    if len(repo_requests) > 1:
                        msg = 's'
                    logger.debug(f'Got refresh request{msg}'
                                    + ' (id{0}={1})'.format(msg, '|'.join(repo_requests)) 
                                    + ' for git repo informations.')
                    # Same here send back latest request id (know here)
                    self.mygit['watcher'].tasks['repo']['requests']['completed'] = repo_requests[-1]
                    self.mygit['manager'].get_branch('local')
                    self.mygit['manager'].get_available_update('branch')
                    # Other wise let's modules related handle this
                    # by using update_installed_kernel()
                    if not self.mygit['watcher'].tasks['mod']['requests']['pending']:
                        self.mygit['manager'].get_available_update('kernel')
                    self.mygit['manager'].update = False
                # For '/lib/modules/' related request (installed kernel)
                if self.mygit['watcher'].tasks['mod']['requests']['pending'] \
                    and not self.mygit['watcher'].mod_read:
                    # Also here
                    mod_requests = self.mygit['watcher'].tasks['mod']['requests']['pending'].copy()
                    msg = ''
                    if len(mod_requests) > 1:
                        msg = 's'
                    logger.debug(f'Got refresh request{msg}'
                                    + ' (id{0}={1})'.format(msg, '|'.join(mod_requests)) 
                                    + ' for modules informations.')
                    if self.mygit['watcher'].tasks['mod']['created']:
                        logger.debug('Found created: {0}'.format(' '.join(
                                                            self.mygit['watcher'].tasks['mod']['created'])))
                    if self.mygit['watcher'].tasks['mod']['deleted']:
                        logger.debug('Found deleted: {0}'.format(' '.join(
                                                            self.mygit['watcher'].tasks['mod']['deleted'])))
                    # Any way pass every thing to update_installed_kernel()
                    self.mygit['manager'].update_installed_kernel(
                                                deleted=self.mygit['watcher'].tasks['mod']['deleted'],
                                                added=self.mygit['watcher'].tasks['mod']['created'])
                    # Wait until update_installed_kernel() otherwise watcher will erase 'deleted' and
                    # 'created'...
                    self.mygit['watcher'].tasks['mod']['requests']['completed'] = mod_requests[-1]
                    self.mygit['manager'].get_available_update('kernel')
                    self.mygit['manager'].update = False
            else:
                if self.mygit['manager'].remain <= 0:
                    # TODO : lower  this to have more sensibility ?
                    self.mygit['manager'].remain = 30
                    self.mygit['manager'].update = True
                self.mygit['manager'].remain -= 1
            # pull
            if self.mygit['manager'].pull['remain'] <= 0 and not self.mygit['manager'].pull['status'] \
                and not self.mygit['watcher'].tasks['pull']['inprogress']:
                # TEST recompute here
                self.mygit['manager'].pull['recompute'] = True
                # Is an external git command in progress ? / recompute remain / bypass if network problem
                if self.mygit['manager'].check_pull():
                    # Pull async and non blocking 
                    self.scheduler.run_in_executor(None, self.mygit['manager'].dopull, ) # -> ', )' = same here
            self.mygit['manager'].pull['remain'] -= 1
            self.mygit['manager'].pull['elapsed'] += 1
            
            time.sleep(1)




def main():
    """
    Main init
    """
    
    # Init dbus service
    dbusloop = GLib.MainLoop()
    dbus_session = SystemBus()
                   
    # Init git watcher first so we can get pull (external) running status
    mygitwatcher = GitWatcher(pathdir, name='Git Watcher Daemon', daemon=True)
    
    # Init gitmanager object through GitDbus class
    mygitmanager = GitDbus(interval=args.pull, pathdir=pathdir)
            
    # Get running kernel
    mygitmanager.get_running_kernel()
    
    # Update all attributes
    # Recompute enable
    mygitmanager.pull['recompute'] = True
    mygitmanager.check_pull(init_run=True) # We need this to print logger.info only one time
    mygitmanager.get_installed_kernel()
    mygitmanager.get_all_kernel()
    mygitmanager.get_available_update('kernel')
    mygitmanager.get_branch('all')
    mygitmanager.get_available_update('branch')
        
    # Adding objects to manager
    mygit = { }
    mygit['manager'] = mygitmanager
    mygit['watcher'] = mygitwatcher
        
    # Adding dbus publisher
    dbus_session.publish('net.gikeud.Manager.Git', mygitmanager)
        
    # Init thread
    daemon_thread = MainDaemon(mygit, name='Main Daemon Thread', daemon=True)
    
    # Start all threads and dbus thread
    mygit['watcher'].start()
    daemon_thread.start()
    dbusloop.run()
    
    daemon_thread.join()
    mygit['watcher'].join()
       
    
if __name__ == '__main__':

    # Ok so first parse argvs
    myargsparser = DaemonParserHandler(pathdir, __version__)
    args = myargsparser.parsing()
    
    # Add repo to pathdid
    pathdir['repo'] = args.repo
    
    # Check or create basedir and logdir directories
    # Print to stderr as we have a redirect for init run 
    for directory in 'basedir', 'logdir':
        if not pathlib.Path(pathdir[directory]).is_dir():
            try:
                pathlib.Path(pathdir[directory]).mkdir()
            except OSError as error:
                if error.errno == errno.EPERM or error.errno == errno.EACCES:
                    print('Got error while making directory:' 
                          + f' \'{error.strerror}: {error.filename}\'.', file=sys.stderr)
                    print('Daemon is intended to be run as sudo/root.', file=sys.stderr)
                else:
                    print('Got unexcept error while making directory:' 
                          + f' \'{error}\'.', file=sys.stderr)
            print('Exiting with status \'1\'.', file=sys.stderr)
            sys.exit(1)
    
    # Now re-configure logging
    if sys.stdout.isatty() and not args.fakeinit:
        # configure the root logger
        logger = logging.getLogger()
        # Rename root logger
        logger.root.name = f'{__name__}'
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(LogLevelFormatter())
        logger.addHandler(console_handler)
        # Default to info
        logger.setLevel(logging.INFO)
        # Working with xfce4-terminal and konsole if set to '%w'
        print(f'\33]0;{prog_name} - version: {__version__}\a', end='', flush=True)
    else:
        # Reconfigure root logger only at the end 
        # this will keep logging error to syslog
        # Add debug handler only if debug is enable
        handlers = { }
        if args.debug and not args.quiet:
            # Ok so it's 5MB each, rotate 3 times = 15MB TEST
            debug_handler = logging.handlers.RotatingFileHandler(pathdir['debuglog'], maxBytes=5242880, backupCount=3)
            debug_formatter   = logging.Formatter('%(asctime)s  %(name)s  %(message)s')
            debug_handler.setFormatter(debug_formatter)
            # For a better debugging get all level message to debug
            debug_handler.addFilter(LogLevelFilter(50))
            debug_handler.setLevel(10)
            handlers['debug'] = debug_handler
                
        # Other level goes to Syslog
        syslog_handler   = logging.handlers.SysLogHandler(address='/dev/log',facility='daemon')
        syslog_formatter = logging.Formatter('{0} %(levelname)s  %(message)s'.format(prog_name))
        syslog_handler.setFormatter(syslog_formatter)
        # Filter stderr output
        syslog_handler.addFilter(LogErrorFilter(stderr=False))
        syslog_handler.setLevel(20)
        handlers['syslog'] = syslog_handler
        
        # Catch file descriptor stderr
        # Same here 5MB, rotate 3x = 15MB
        fd_handler = logging.handlers.RotatingFileHandler(pathdir['fdlog'], maxBytes=5242880, backupCount=3)
        fd_formatter   = logging.Formatter('%(asctime)s  %(message)s') #, datefmt)
        fd_handler.setFormatter(fd_formatter)
        fd_handler.addFilter(LogErrorFilter(stderr=True))
        # Level is error : See class LogErrorFilter
        fd_handler.setLevel(40)
        handlers['fd'] = fd_handler
        
        # reconfigure the root logger
        logger = logging.getLogger()
        # Rename root logger
        logger.root.name = f'{__name__}'
        # Add handlers
        for handler in handlers.values():
            logger.addHandler(handler)
        # Set log level
        logger.setLevel(logging.INFO)
        # redirect again but now not to syslog but to file ;)
        # First remove root_logger handler otherwise it will still send message to syslog
        root_logger.removeHandler(fd_handler_syslog)
        fd2 = RedirectFdToLogger(logger)
        sys.stderr = fd2
    
    # default level is INFO
    if args.debug and args.quiet:
        logger.info('Both debug and quiet opts has been enable,' 
                    + ' falling back to log level info.')
    elif args.debug:
        logger.setLevel(logging.DEBUG)
        logger.info(f'Debug has been enable. {display_init_tty}')
        logger.debug('Message are from this form \'::module::class::method:: msg\'.')
    elif args.quiet:
        logger.setLevel(logging.ERROR)
    
    if sys.stdout.isatty() and not args.fakeinit:
        logger.info('Interactive mode detected, all logs go to terminal.')
    
    # run MAIN
    main()
    
    
    
    


