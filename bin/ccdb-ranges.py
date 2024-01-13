#!/usr/bin/env python3
import os
import sys
import argparse

info='''
Sometimes you want to know what CCDB assignments you will get for
a given run range.  But often that isn't simple to figure out from
standard CCDB tools, as it depends on the timestamp, variation and
its mothers, and the time at which different assignments were made.
This script determines those \"effective\" run ranges, i.e., what
you would actually get for a given timestamp and variation.

The simplest example:
(1) An assignment A is made covering runs 1-100.
(2) Later an assignment B is made covering runs 50-60.
(3) There are now 2 assignments but 3 effective run ranges:
    1-49, 50-60, and 61-100, two of which correspond to A.

Note, this type of "introspection" was one of the things intended
for future CCDB versions.

This script also provides a \"save\" option, which will export the
effective ranges to files that can then be modified and uploaded
to CCDB.  If needing to correct a few numbers in CCDB, across a
range of runs and multiple assignments, this can be much easier
and more robust than manually tracing timestamp/variation effects
and avoids having to find the original files or regenerate them.
'''

class Range():
    def __init__(self, run_min, run_max, assignment):
        self.run_min = run_min
        self.run_max = run_max
        self.assignment = assignment
        self.filename = None
    @staticmethod
    def header():
        return '%6s %6s %7s  %19s  %s' % ('min','max','id','created','comment')
    def __str__(self):
        return '%6d %6d %7d  %19s  %s' % (self.run_min, self.run_max,
            self.assignment.id, self.assignment.created, self.assignment.comment)
    def table_string(self):
        return '\n'.join([ ' '.join(row) for row in self.assignment.constant_set.data_table ])
    def generate_filename(self):
        path = '-'.join(self.assignment.constant_set.type_table.path.strip('/').split('/'))
        return '%s_%d-%d.txt' % (path, self.run_min, self.run_max)
    def save(self, comment=None, filename=None):
        if filename is None:
            self.filename = self.generate_filename()
        else:
            self.filename = filename
        if os.path.exists(self.filename):
            print('ERROR:  File already exists:  '+self.filename)
            print('ABORTED.')
            sys.exit(1)
        print('# Writing file:  '+self.filename)
        with open(self.filename,'w') as f:
            if comment is not None:
                f.write('#'+comment+'\n')
            f.write(self.table_string())
    def upload_command(self):
        path = self.assignment.constant_set.type_table.path
        ret = 'ccdb -c $CCDB_CONNECTION add ' + path
        ret += ' -r %d-%d %s' % (self.run_min, self.run_max, self.filename)
        return ret

cli = argparse.ArgumentParser(description='Generate effective run ranges for a given CCDB table.',
    epilog='For example:  ccdb-ranges.py -min 4090 -max 5010 -table /runcontrol/fcup')

cli.add_argument('-info', help='print some information about this tool', default=False, action='store_true')
cli.add_argument('-min', metavar='#', help='minimum run number', type=int, required='-info' not in sys.argv)
cli.add_argument('-max', metavar='#', help='maximum run number', type=int, required='-info' not in sys.argv)
cli.add_argument('-table', help='table name', type=str, required='-info' not in sys.argv)
cli.add_argument('-variation', help='variation name (default=default)', type=str, default='default')
cli.add_argument('-timestamp', metavar='MM/DD/YYYY[-HH:mm:ss]', help='timestamp (default=now)', type=str, default=None)
cli.add_argument('-dump', help='print all constant sets', default=False, action='store_true')
cli.add_argument('-save', help='save all constant sets in files in current working directory', default=False, action='store_true')
cli.add_argument('-comment', help='add a comment for CCDB to the saved files', type=str)

args = cli.parse_args(sys.argv[1:])

if args.info:
    print('\n'+''.ljust(66,"#"))
    print(cli.description+'\n'+info)
    print(''.ljust(66,"#")+'\n')
    sys.exit(0)

if args.max < args.min:
    cli.error('Invalid run range, min>max:  min=%d  max=%d.' % (args.min, args.max))

if args.timestamp is not None:
    import datetime
    try:
        args.timestamp = datetime.datetime.strptime(args.timestamp, '%m/%d/%Y-%H:%M:%s')
    except ValueError:
        try:
            args.timestamp = datetime.datetime.strptime(args.timestamp, '%m/%d/%Y')
        except ValueError:
            cli.error('Invalid timestamp:  '+args.timestamp)

import ccdb
import sqlalchemy
provider = ccdb.AlchemyProvider()
provider.connect(os.getenv('CCDB_CONNECTION'))

ranges = []

for run in range(args.min, args.max+1):
    try:
        assignment = provider.get_assignment(args.table, run, args.variation, args.timestamp)
    except ccdb.errors.TypeTableNotFound:
        cli.error('Invalid table or variation:  %s/%s.' % (args.table, args.variation))
    except ccdb.errors.DirectoryNotFound:
        cli.error('Invalid table or variation:  table=%s  variation=%s.' % (args.table, args.variation))
    except sqlalchemy.orm.exc.NoResultFound:
        cli.error('Invalid run range or no data:  min=%d  max=%d.' % (args.min, args.max))
    if len(ranges)==0 or ranges[-1].assignment.id != assignment.id:
        ranges.append( Range(run, run, assignment) )
    elif ranges[-1].run_max == run-1:
        ranges[-1].run_max = run
    else:
        raise Exception('This should be impossible.')

print('\n# Effective Run Ranges ::::::::::::::::::::::::::::::')
print('#'+Range.header()+'\n#'+'\n#'.join([str(r) for r in ranges]))
print('#:::::::::::::::::::::::::::::::::::::::::::::::::::\n')

if args.dump:
    for x in ranges:
        print('\n'+str(x)+'\n'+x.table_string())
if args.save:
    for x in ranges:
        x.save(args.comment)
    for x in ranges:
        print(x.upload_command())

