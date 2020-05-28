# -*- coding: utf-8 -*-
# -*- python -*- 
# Copyright © 2019,2020: Venturi Jérôme : jerome dot Venturi at gmail dot com
# Distributed under the terms of the GNU General Public License v3

import sys
from gitmanager import GitHandler
import logging

# TODO try to return list / dict over str ?? 

class GitDbus(GitHandler):
    """
        <node>
            <interface name='net.gikeud.Manager.Git'>
                <method name='get_kernel_attributes'>
                    <arg type='s' name='kernel_key' direction='in'/>
                    <arg type='s' name='kernel_subkey' direction='in'/>
                    <arg type='s' name='response' direction='out'/>
                </method>
                <method name='get_branch_attributes'>
                    <arg type='s' name='branch_key' direction='in'/>
                    <arg type='s' name='branch_subkey' direction='in'/>
                    <arg type='s' name='response' direction='out'/>
                </method>
                <method name='reset_pull_error'>
                    <arg type='s' name='response' direction='out'/>
                </method>
            </interface>
        </node>
    """
    def __init__(self, **kwargs):
        # Delegate kwargs arguments checking in GitHandler (gitmanager module)
        super().__init__(**kwargs)
        # check if we have pull_state (from gitmanager -> GitWatcher object)
        # This intend to detect external (but also internal) git pull running
        self.pull_state = False #kwargs.get('pull_state', 'disabled')
        # Init logger (even if there is already a logger in GitHandler)
        # better to have a separate logger
        # Don't override self.logger_name from GitHandler
        self.named_logger = f'::{__name__}::GitDbus::'
        logger = logging.getLogger(f'{self.named_logger}init::')
    

    def get_kernel_attributes(self, key, subkey):
        """
        Retrieve specific kernel attribute and return through dbus
        """
        logger = logging.getLogger(f'{self.named_logger}get_kernel_attributes::')
        logger.debug(f'Requesting: {key} | {subkey}')
        
        if subkey == 'None':
            logger.debug('Returning: {0} (as string).'.format(' '.join(self.kernel[key])))
            return str(' '.join(self.kernel[key]))
        logger.debug('Returning: {0} (as string).'.format(' '.join(self.kernel[key][subkey])))
        return str(' '.join(self.kernel[key][subkey]))
    

    def get_branch_attributes(self, key, subkey):
        """
        Retrieve specific branch attribute and return through dbus
        """
        logger = logging.getLogger(f'{self.named_logger}get_branch_attributes::')
        logger.debug(f'Requesting: {key} | {subkey}')
        
        if subkey == 'None':
            logger.debug('Returning: {0} (as string).'.format(' '.join(self.branch[key])))
            return str(' '.join(self.branch[key]))
        logger.debug('Returning: {0} (as string).'.format(' '.join(self.branch[key][subkey])))
        return str(' '.join(self.branch[key][subkey]))
    

    def reset_pull_error(self):
        """
        Reset pull error and forced pull
        """
        logger = logging.getLogger(f'{self.named_logger}reset_pull_error::')
        logger.debug('Got request.')
        
        if self.pull['status']:
            logger.debug('Failed: already running (internal).')
            return 'running'
        
        #if not self.pull_state == 'disabled':
        if self.pull_state:
            logger.debug('Failed: already running (external).')
            return 'running'
        #else:
            #logger.debug('External git pull running checker is disabled.')
            # don't return 'running' as we don't know state so just pass to next
        
        if not self.pull['state'] == 'Failed':
            logger.debug('Failed: no error found.')
            return 'no_error'
        
        if self.pull['state'] == 'Failed' and self.pull['network_error']:
            logger.debug('Failed: network related error.')
            return 'network'
        
        # Ok everything should be good ;)
        logger.debug('Succeed: error reseted.')
        logger.warning('Resetting pull error as requested by dbus client.')
        self.pull['state'] = 'Success'
        self.stateinfo.save('pull state', 'pull state: Success')
        return 'done'
