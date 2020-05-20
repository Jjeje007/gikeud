#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -*- python -*- 
# Copyright © 2019,2020: Venturi Jérôme : jerome dot Venturi at gmail dot com
# Distributed under the terms of the GNU General Public License v3

import time 
import sys
import locale
import gettext
import locale
import pathlib
import re

from argsparser import ClientParserHandler
from lib.utils import _format_date
from lib.utils import _format_timestamp

try:
    from pydbus import SystemBus
except Exception as exc:
    print(f'Got unexcept error while loading dbus module: {exc}')
    sys.exit(1)

try:
    from babel.dates import format_datetime
    from babel.dates import LOCALTZ
except Exception as exc:
    print(f'Got unexcept error while loading babel modules: {exc}')
    sys.exit(1)

# Dbus server run as system
bus = SystemBus()

mylocale = locale.getdefaultlocale()
# see --> https://stackoverflow.com/a/10174657/11869956 thx
#localedir = os.path.join(os.path.dirname(__file__), 'locales')
# or python > 3.4:
localedir = pathlib.Path(__file__).parent/'locales'    
lang_translations = gettext.translation('client', localedir, languages=[mylocale[0]], fallback=True)
lang_translations.install()
translate = True
_ = lang_translations.gettext


def available_version(myobject, opt, machine):
    """Display available git kernel or branch version, if any"""
    # TODO give choice to print all the version or just n version with (+the_number_which_rest)
    switch = {
        'branch'    :   {
                    'caller'    :   'get_branch_attributes',
                    'msg'       :   _('Available git branch version:'),
                    'none'      :   _('not available')
                    },
        'kernel'    :   {
                    'caller'    :   'get_kernel_attributes',
                    'msg'       :   _('Available git kernel version:'),
                    'none'      :   _('not available')
                    }
        }
    reply = getattr(myobject, switch[opt]['caller'])('available', 'None')
    if reply == 'disable':
        print('Error: git implantation is disabled.')
        return
    elif reply == '0.0' or reply == '0.0.0':
        msg = switch[opt]['none']
    else:
        version_list = reply.split(' ')
        msg_len = len(version_list)
        if msg_len > 1:
            msg = version_list[-1] + ' (+' + str(msg_len - 1) + ')'
        else:
            msg = version_list[0]
    
    if not machine:
        print('[*] {0}'.format(_(switch[opt]['msg'])))
        print(f'    - {msg}')
    else:
        print(msg)

def reset_pull_error(myobject, machine):
    """Reset pull error and forced pull"""
    msg = {
        'done'      :   _('Done.'),
        'no_error'  :   _('No error found.'),
        'network'   :   _('Found a network error which is not blocking.'),
        'running'   :   _('Git pull is running, skipping...')
        }
    reply = myobject.reset_pull_error()
    if reply == 'disable':
        print('Error: git implantation is disable')
        return
        
    if not machine:
        print('[*] Resetting pull error:')
        print('    - {0}'.format(msg[reply]))
    else:
        print(msg[reply])

def parser(args):
    """Parser for git implentation"""
    myobject  = bus.get("net.syuppod.Manager.Git")
    gitcaller = {
        'available'  :   { 'func' : available_version, 'args' : [myobject, args.available, args.machine]},
        'reset'      :   { 'func' : reset_pull_error, 'args' : [myobject, args.machine ] }
        }
    
    for key in gitcaller:
        if getattr(args, key):
            gitcaller[key]['func'](*gitcaller[key]['args'])


### MAIN ###
myargsparser = ClientParserHandler(version='dev')
args = myargsparser.parsing()
# Call parser
parser(args)

