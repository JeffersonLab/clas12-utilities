#!/usr/bin/env python3
#
# N. Baltzell, July 2024
#
# Detect metadata differences between CVMFS proper and its source filesystem at JLab.
#
# Syncronization happens via periodic, incremental rsyncs from the source to some
# other filesystem at JLab, which then trigger an OSG/CondorHT job *if* any changes
# are detected.  (That job is presumably the standard mechanism supported by OSG to
# populate /cvmfs/oasis.opensciencegrid.org, but the rsyncs may be JLab.)  That job
# is currently a one-shot, not monitored and not retried, and with a significant
# probability of failure.  If it fails, future rsyncs will not detect changes and
# so will not trigger the jobs, and the source filesystem then stays permanently out
# of sync with CVMFS until the affected files are modified again.
#
# Note, permissions changes do not (always?) propagate, need to remove the file, let
# it propagate, then add it back with correct permissions.  The rsync above does
# detect and sync a permissions change, so the culprit must be downstream.
#
# Note, some CVMFS attributes prevent using standard filesystem tools:
# * sticky bit doesn't exist (it's read-only)
# * group/owner is always "cvmfs"
# * world is the only thing that matters anyway (it's ready-only) 
# * timestamp resolution
#

default_src = '/scigroup/cvmfs/hallb/clas12/sw'
default_dest = '/cvmfs/oasis.opensciencegrid.org/jlab/hallb/clas12/sw'
default_ignores = ['.*/\.git/.*']

import argparse
cli = argparse.ArgumentParser('cvmfs-diff',description='Compare local source and CVMFS target filesystems.',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
cli.add_argument('-l',help='local source directory (or subpath underneath default)',metavar='PATH',default=default_src)
cli.add_argument('-c',help='CVMFS target directory',metavar='PATH',default=None)
cli.add_argument('-i',help='ignore path regex, repeatable',default=default_ignores,action='append')
cli.add_argument('-v',help='verbose mode, repeatable',action='count',default=0)
cli.add_argument('-t',help='check timestamps',action='store_true',default=False)
args = cli.parse_args()

import logging
if args.v>1:
    logging.basicConfig(level=logging.INFO,format='%(levelname)s: %(message)s')
elif args.v>0:
    logging.basicConfig(level=logging.WARNING,format='%(levelname)s: %(message)s')
else:
    logging.basicConfig(level=logging.ERROR,format='%(levelname)s: %(message)s')
if not args.l.startswith('/'):
    if args.c:
        cli.error('Option -c cannot be used with a relative path for -l.')
    args.l = default_src + '/' + args.l
if not args.c:
    args.c = default_dest + args.l[len(default_src):]
elif not args.c.startswith('/'):
    cli.error('Option -c must be an absolute path.')
import os
if not os.path.isdir(args.l):
    cli.error('Source directory invalid:  '+args.l)
if not os.path.isdir(args.c):
    cli.error('Target directory invalid:  '+args.c)
if not args.c.startswith('/cvmfs/'):
    logging.warning('Destination does not start with "/cvmfs".')

def difflink(a,b):
    # ignore dead links on the source filesystem:
    if os.path.exists(os.path.realpath(a)):
        # if it's an absolute symlink, ignore prefix:
        if os.path.isabs(os.readlink(a)):
            if os.path.realpath(a) != os.path.realpath(b):
                if os.path.realpath(a)[len(args.l):] != os.path.realpath(b)[len(args.c):]:
                    logging.getLogger().warning('%s %s'%(os.path.realpath(a)[len(args.l):],os.path.realpath(b)[len(args.c):]))
                    logging.getLogger().warning('%s %s'%(os.path.realpath(a),os.path.realpath(b)))
                    logging.getLogger().warning('ALNK: %s'%a)
                    return False
        # if it's a relative symlink, they must be equal:
        elif os.readlink(a) != os.readlink(b):
            logging.getLogger().warning('RLNK: %s'%a)
            return Falsr
    return True

def diff(a,b):
    if os.path.islink(a):
        return difflink(a,b)
    if not os.path.exists(b):
        logging.getLogger().warning('MISS: %s'%a)
        return False
    else:
        s1 = os.stat(a)
        s2 = os.stat(b)
        # require equal file sizes:
        if not os.path.isdir(a) and s1.st_size != s2.st_size:
            logging.getLogger().warning('SIZE: %s (%d!=%d)'%(a,s1.st_size,s2.st_size))
            return False
        # require equal world permissions bits:
        if (s1.st_mode&0xF) != (s2.st_mode&0xF):
            logging.getLogger().warning('MODE: %s (%d!=%d)'%(a,s1.st_mode,s2.st_mode))
            return False
        # require consistent modification times:
        if args.t and int(s1.st_mtime) > int(s2.st_mtime):
            logging.getLogger().warning('TIME: %s (%d!=%d)'%(a,s1.st_mtime,s2.st_mtime))
            return False
    return True

def ignore(path):
    import re
    for x in args.i:
        if re.match(x,path):
            return True
    return False

def walk(path):
    for dirpath, dirnames, filenames in os.walk(path):
        import itertools
        for f in itertools.chain(dirnames, filenames):
            f1 = dirpath + '/' + f
            f2 = args.c + f1[len(args.l):]
            if ignore(f1):
                continue
            if diff(f1,f2):
                logging.getLogger().info('GOOD: %s'%f1)
            else:
                yield(f1)

mismatches = list(walk(args.l))

if len(mismatches)>0:
    logging.getLogger().error('Found %d Inconsistencies:\n'%len(mismatches)+'\n'.join(mismatches))

import sys
sys.exit(len(mismatches))

