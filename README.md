[![linux zen kernel](https://upload.wikimedia.org/wikipedia/commons/3/35/Tux.svg)](https://github.com/zen-kernel/zen-kernel)

# Gikeud
> GIt KErnel Updater Daemon

Gikeud is a python3 daemon which automate git pull for git [zen-kernel](https://github.com/zen-kernel/zen-kernel) (for the moment)
every interval (can be tweaked). It will list all available branch or kernel for update. So it can detect local branch checkout,
new installed kernel (retrieve from /lib/modules/), new running kernel. It can, also, detect external/manual pull and adapt
its interval. It intend to be run as a root service using /etc/init.d/ but for debugging puproses it can be run in a terminal. 
Any way, it as to be run as root (for the moment).

It uses dbus to expose informations to user space tools and it have an already written client (trival).
With this client (gikeud-cli), you can retrieve informations about, for exemple, available kernel depending
on which is available from git and which have been installed. And more (also more to come).

I'm using it with [conky](https://github.com/brndnmtthws/conky) to display some informations. But it have no 
dependencies against conky. So it's up to you to do whatever you want to do with these informations and from
whatever program (as long as it use dbus or gikeud-cli output).


## Dependencies

* [python](https://www.python.org/) >= 3.5 (tested: v3.6.x - v3.7.7, recommanded: v3.7.x)
* [pydbus](https://github.com/LEW21/pydbus)
* [GitPython](https://github.com/gitpython-developers/GitPython)
* [inotify_simple](https://github.com/chrisjbillington/inotify_simple)

For **pydbus** and **inotify_simple** ebuilds can be found in [Jjeje007-overlay](https://github.com/Jjeje007/Jjeje007-overlay).

## Installation / Usage

1. Clone the repo:
```bash
git clone https://github.com/Jjeje007/gikeud.git
```
2. Copy the dbus configuration file to authorize dbus request:
```bash
cp gikeud-dbus.conf /usr/share/dbus-1/system.d/
```
3. Install dependencies using emerge or pip.

### If you just want to test it:

1. Run it (i recommand to activate debug):
```bash
./main -d
```

### To use as a daemon:

1. Copy init file:
```bash
cp init /etc/init.d/gikeud
```
2. Edit lines:\
    command=\ 
   To point to: /where/is/your/git/clone/repo/main.py\
   And:\
    command_args=\
   To suit your need, more information:
```bash
./main --help
```
3. Run the daemon:
```bash
/etc/init.d/gikeud start
```

### About logs and debug

Daemon have several logs all located in /var/log/gikeud/\

Starting with git commit id: 74a72c2699a6fa33a9a5c5af58ace8700fd1a14b, new logging process have been added
to catch almost all error when running daemon in init mode (/etc/init.d/gikeud start). Unfortunately, 
it introduce a more complex log flow. The earliest errors are redirect to syslog first. So if you encounter
any issues you should first check /var/log/messages. Then: /var/log/gikeud/stderr.log and /var/log/gikeud/debug.log
(if debug is enable: -d). 

Running by hand in a terminal (so not using /etc/init.d/) is really intend to be a one shot test or for debugging.
You have to note that there is also a debugging option: --fakeinit which mimic init process (so you won't get any output
in terminal).

Daemon and terminal mode write pull log to:\
/var/log/gikeud/git.log

All logs are autorotate.

## Developpement Status

This is a work in progress so i haven't yet planned to make a release.\
The API is still in developpement and it's not yet stabilized.\
My priority is to stabilize daemon API.

## Meta

Venturi Jerôme – jerome.venturi@gmail.com

Distributed under the [GNU gpl v3 license](https://www.gnu.org/licenses/gpl-3.0.html).

## Bugs report

Please open an issue and don't forget to attach logs: stderr.log and debug.log. 

## Contributing

Pull requests and translations are welcome. For major changes, please open an issue first to discuss what you would like to change.

