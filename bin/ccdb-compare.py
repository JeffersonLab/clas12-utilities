#!/usr/bin/env python2
import os
import sys
import argparse
import datetime
import difflib
import ccdb
import sqlalchemy

cli = argparse.ArgumentParser(description='Compare two CCDB tables.',
    epilog='ccdb-compare.py -table /runcontrol/fcup -r1 5000 -r2 5000 -v2 rgb_spring2019')

cli.add_argument('-table', help='table name', type=str, required=True)
cli.add_argument('-r1', metavar='#', help='run number', type=int, required=True)
cli.add_argument('-r2', metavar='#', help='run number (default=r1)', type=int, default=None)
cli.add_argument('-v1', help='variation name (default=default)', type=str, default='default')
cli.add_argument('-v2', help='variation name (default=v1)', type=str, default=None)
cli.add_argument('-t1', metavar='MM/DD/YYYY[-HH:mm:ss]', help='timestamp (default=now)', type=str, default=None)
cli.add_argument('-t2', metavar='MM/DD/YYYY[-HH:mm:ss]', help='timestamp (default=t1)', type=str, default=None)

args = cli.parse_args(sys.argv[1:])

if args.r2 is None:
  args.r2 = args.r1
if args.v2 is None:
  args.v2 = args.v1
if args.t2 is None:
  args.t2 = args.t1

def parse_timestamp(t):
    if t is None:
        return None
    try:
        return datetime.datetime.strptime(t, '%m/%d/%Y-%H:%M:%s')
    except ValueError:
        return  datetime.datetime.strptime(t, '%m/%d/%Y')

try:
    args.t1 = parse_timestamp(args.t1)
except ValueError:
    cli.error('Invalid timestamp:  '+args.t1)
try:
    args.t2 = parse_timestamp(args.t2)
except ValueError:
    cli.error('Invalid timestamp:  '+args.t2)

provider = ccdb.AlchemyProvider()
provider.connect(os.getenv('CCDB_CONNECTION'))

def get(table,run,variation,timestamp):
    try:
        return provider.get_assignment(table, run, variation, timestamp)
    except ccdb.errors.TypeTableNotFound:
        cli.error('Invalid table or variation:  %s/%s.' % (table, variation))
    except ccdb.errors.DirectoryNotFound:
        cli.error('Invalid table or variation:  table=%s  variation=%s.' % (table, variation))
    except sqlalchemy.orm.exc.NoResultFound:
        cli.error('Invalid run or no data:  %d.' % (run))

a1 = get(args.table,args.r1,args.v1,args.t1)
a2 = get(args.table,args.r2,args.v2,args.t2)
a1 = [ ' '.join(x) for x in a1.constant_set.data_table ]
a2 = [ ' '.join(x) for x in a2.constant_set.data_table ]

for x in difflib.context_diff(a1,a2):
  print(x)

