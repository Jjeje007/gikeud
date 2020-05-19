#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -*- python -*- 
# Starting : 2019-08-08

# This is a GIt KErnel Updater Daemon
# Copyright © 2019,2020: Venturi Jérôme : jerome dot Venturi at gmail dot com
# Distributed under the terms of the GNU General Public License v3

import sys
import os
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
from lib.logger import MainLoggingHandler
from lib.logger import RedirectFdToLogger
from argsparser import DaemonParserHandler


# TODO TODO TODO don't run as root ! investigate !
# TODO : exit gracefully 
# TODO : debug log level !
# TODO threading we cannot share object attribute 
#       or it will no be update ?!?

try:
    from gi.repository import GLib
    from pydbus import SystemBus
except Exception as exc:
    print(f'Error: unexcept error while loading dbus bindings: {exc}', file=sys.stderr)
    print('Error: exiting with status \'1\'.', file=sys.stderr)
    sys.exit(1)

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

class MainDaemon(threading.Thread):
    def __init__(self, mygit, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mygit = mygit
        # Init asyncio loop
        self.scheduler = asyncio.new_event_loop()
    
    def run(self):
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
    """Main init"""
    
    # Check or create basedir and logdir directories
    for directory in 'basedir', 'logdir':
        if not pathlib.Path(pathdir[directory]).is_dir():
            try:
                pathlib.Path(pathdir[directory]).mkdir()
            except OSError as error:
                if error.errno == errno.EPERM or error.errno == errno.EACCES:
                    logger.critical(f'Got error while making directory: \'{error.strerror}: {error.filename}\'.')
                    logger.critical('Daemon is intended to be run as sudo/root.')
                    sys.exit(1)
                else:
                    logger.critical(f'Got unexcept error while making directory: \'{error}\'.')
                    sys.exit(1)
        
    # Init dbus service
    dbusloop = GLib.MainLoop()
    dbus_session = SystemBus()
                   

    # Init git watcher first so we can get pull (external) running status
    mygitwatcher = GitWatcher(pathdir, runlevel, logger.level, args.repo, name='Git Watcher Daemon',
                    daemon=True)
    
    # Init gitmanager object through GitDbus class
    # Same here: sharing not working
    mygitmanager = GitDbus(enable=True, interval=args.pull, repo=args.repo, pathdir=pathdir, 
                            runlevel=runlevel, loglevel=logger.level)
            
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
    dbus_session.publish('net.syuppod.Manager.Git', mygitmanager)
        
    # Init thread
    daemon_thread = MainDaemon(mygit, name='Main Daemon Thread', daemon=True)
    
    # Start all threads and dbus thread
    mygit['watcher'].start()
    daemon_thread.start()
    dbusloop.run()
    
    daemon_thread.join()
    mygit['watcher'].join()
       
    
if __name__ == '__main__':

    # Parse arguments
    myargsparser = DaemonParserHandler(pathdir, __version__)
    args = myargsparser.parsing()
        
    # Creating log
    mainlog = MainLoggingHandler('::main::', pathdir['prog_name'], pathdir['debuglog'], pathdir['fdlog'])
    
    if sys.stdout.isatty():
        logger = mainlog.tty_run()      # create logger tty_run()
        logger.setLevel(mainlog.logging.INFO)
        runlevel = 'tty_run'
        display_init_tty = ''
        # This is not working with konsole (kde)
        # TODO
        print('\33]0; {0} - {1}  \a'.format(prog_name, __version__), end='', flush=True)
    else:
        logger = mainlog.init_run()     # create logger init_run()
        logger.setLevel(mainlog.logging.INFO)
        runlevel = 'init_run'
        display_init_tty = 'Log are located to {0}'.format(pathdir['debuglog'])
        # TODO rewrite / change 
        # Redirect stderr to log 
        # For the moment maybe stdout as well but nothing should be print to...
        # This is NOT good if there is error before log(ger) is initialized...
        fd2 = RedirectFdToLogger(logger)
        sys.stderr = fd2
       
    if args.debug and args.quiet or args.quiet and args.debug:
        logger.info('Both debug and quiet opts has been enable, falling back to log level info.')
        logger.setLevel(mainlog.logging.INFO)
    elif args.debug:
        logger.setLevel(mainlog.logging.DEBUG)
        logger.info(f'Debug has been enable. {display_init_tty}')
        logger.debug('Message are from this form \'::module::class::method:: msg\'.')
    elif args.quiet:
        logger.setLevel(mainlog.logging.ERROR)
    
    if sys.stdout.isatty():
        logger.info('Interactive mode detected, all logs go to terminal.')
    
    # run MAIN
    main()
    
    
    
    


