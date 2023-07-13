#!/usr/bin/env python2
import os
import sys
import argparse
import datetime
import difflib
import ccdb
import sqlalchemy

cli = argparse.ArgumentParser(description='Compare two CCDB tables, printing the result in the standard \"diff\" format.',
    epilog='Example:  ccdb-diff.py -table /runcontrol/fcup -r1 5000 -r2 5000')

cli.add_argument('-table', help='table name', type=str, required=True)
cli.add_argument('-r1', metavar='#', help='first run number', type=int, required=True)
cli.add_argument('-r2', metavar='#', help='second run number (default=same as r1)', type=int, default=None)
cli.add_argument('-v1', metavar='VARIATION', help='first variation (default=default)', type=str, default='default')
cli.add_argument('-v2', metavar='VARIATION', help='second variation (default=same as v1)', type=str, default=None)
cli.add_argument('-t1', metavar='MM/DD/YYYY[-HH:mm:ss]', help='timestamp (default=now)', type=str, default=None)
cli.add_argument('-t2', metavar='MM/DD/YYYY[-HH:mm:ss]', help='timestamp (default=same as t1)', type=str, default=None)

args = cli.parse_args(sys.argv[1:])

if args.r2 is None:
    args.r2 = args.r1
if args.v2 is None:
    args.v2 = args.v1
if args.t2 is None:
    args.t2 = args.t1

if args.r1==args.r2 and args.v1==args.v2 and args.t1==args.t2:
    cli.error('Nothing worth comparing; the requested assignment queries are identical.')

def parse_timestamp(t):
    if t is None:
        return None
    try:
        return datetime.datetime.strptime(t, '%m/%d/%Y-%H:%M:%s')
    except ValueError:
        try:
            return datetime.datetime.strptime(t, '%m/%d/%Y')
        except ValueError:
            cli.error('Invalid timestamp format:  '+t)

def get_assignment(provider,table,run,variation,timestamp):
    try:
        return provider.get_assignment(table, run, variation, timestamp)
    except ccdb.errors.TypeTableNotFound:
        cli.error('Invalid table:  %s' % table)
    except ccdb.errors.DirectoryNotFound:
        cli.error('Invalid directory:  %s' % table)
    except ccdb.errors.VariationNotFound:
        cli.error('Invalid variation:  %s' % variation)
    except sqlalchemy.orm.exc.NoResultFound:
        cli.error('No data found for %s and run %d at timestamp %s' % (table,run,timestamp))

# convert to datetime objects for CCDB:
args.t1 = parse_timestamp(args.t1)
args.t2 = parse_timestamp(args.t2)

# retrieve the two assignemnts from CCDB:
provider = ccdb.AlchemyProvider()
provider.connect(os.getenv('CCDB_CONNECTION'))
a1 = get_assignment(provider, args.table, args.r1, args.v1, args.t1)
a2 = get_assignment(provider, args.table, args.r2, args.v2, args.t2)

# convert to lists of strings for difflib:
a1 = [ ' '.join(x) for x in a1.constant_set.data_table ]
a2 = [ ' '.join(x) for x in a2.constant_set.data_table ]

# finally, just print the diff:
for x in difflib.unified_diff(a1,a2):
    print(x)

provider.disconnect()
