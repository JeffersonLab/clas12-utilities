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
# is currently a one-shot, not monitored and not retried, and with a large probability
# of failure, then future rsyncs not triggering any more CVMFS updates for the
# associated files until they're changed again.  Hence this silly script ...
#
# Note, some CVMFS attributes prevent using standard filesystem tools:
# * sticky bit doesn't exist (it's read-only)
# * group/owner is always "cvmfs"
# * world is the only thing that matters anyway (it's ready-only) 
# * timestamp resolution
#

default_src = '/scigroup/cvmfs/hallb/clas12/sw'
default_dest = '/cvmfs/oasis.opensciencegrid.org/jlab/hallb/clas12/sw'

ignores = ['.*/rgm_fall2021-ai.yaml$','.*/\.git/.*','.*/gibuu/.*']

import argparse
cli = argparse.ArgumentParser('cvmfs-diff',description='Compare source and destination CVMFS filesystems.',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
cli.add_argument('-s',help='source path (or subpath underneath default)',metavar='PATH',default=default_src)
cli.add_argument('-d',help='destination path on CVMFS',metavar='PATH',default=default_dest)
cli.add_argument('-t',help='check timestamps',action='store_true')
cli.add_argument('-v',help='verbose mode, repeatable',action='count',default=0)
cli.add_argument('-i',help='regex for ignoring paths, repeatable',default=[],action=append)
args = cli.parse_args()
ignores.extend(args.i)

import logging
if args.v>1:
    logging.basicConfig(level=logging.INFO,format='%(levelname)s: %(message)s')
elif args.v>0:
    logging.basicConfig(level=logging.WARNING,format='%(levelname)s: %(message)s')
else:
    logging.basicConfig(level=logging.ERROR,format='%(levelname)s: %(message)s')

import sys
import os
if not args.s.startswith('/'):
    args.d = default_dest + '/' + args.s
    args.s = default_src + '/' + args.s
if not os.path.isdir(args.s):
    cli.error('Source path is not a directory or does not exist:  '+args.s)
if not os.path.isdir(args.d):
    cli.error('Destination path is not a directory or does not exist:  '+args.d)
if not args.d.startswith('/cvmfs/'):
    logging.warning('Destination does not start with "/cvmfs".')

def diff(a,b):
    if not os.path.exists(b):
        logging.getLogger().warning('MISS: %s'%a)
        return False
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
    for x in ignores:
        if re.match(x,path):
            return True
    return False

# walk the source filesystem, check for and store mismatches: 
mismatches = []
for dirpath, dirnames, filenames in os.walk(args.s):
    import re
    import itertools
    for f in itertools.chain(dirnames, filenames):
        f1 = dirpath + '/' + f
        f2 = args.d + f1[len(args.s):]
        if ignore(f1):
            continue
        if diff(f1,f2):
            logging.getLogger().info('GOOD: %s'%f1)
        else:
            mismatches.append(f1)

if len(mismatches)>0:
    logging.getLogger().error('Found %d Inconsistencies:\n'%len(mismatches)+'\n'.join(mismatches))

sys.exit(len(mismatches))

