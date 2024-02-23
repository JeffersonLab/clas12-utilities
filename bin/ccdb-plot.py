#!/usr/bin/env python3
import os
import sys
import argparse
import datetime

def get_row(table, slco):
    for row in data_table:
        good = True
        for column,value in enumerate(args.slco):
            if int(row[column]) != value:
                good = False
                break
        if good:
            return row
    return None

def get_cell(table, slco, column_index):
    row = get_row(table, slco)
    if row is not None:
        return float(row[column_index])
    return None

cli = argparse.ArgumentParser(description='Plot one variable from a CCDB table with 3 or 4 leading index columns.')
cli.add_argument('-min', metavar='#', help='minimum run number', type=int, required=True)
cli.add_argument('-max', metavar='#', help='maximum run number', type=int, required=True)
cli.add_argument('-table', help='table name', type=str, required=True)
cli.add_argument('-variable', help='variable name', type=str, required=True)
cli.add_argument('-slco', metavar='#/#/#[/#]', help='leading column values, e.g. sector/layer/component[/order]', required=True)
cli.add_argument('-ignore', help='value to discard from plot (repeatable)', default=[], type=float, action='append')
cli.add_argument('-variation', help='variation name (default=default)', type=str, default='default')
cli.add_argument('-timestamp', metavar='MM/DD/YYYY[-HH:mm:ss]', help='timestamp (default=now)', type=str, default=None)
cli.add_argument('-batch', help='do not open ROOT canvas', default=False, action='store_true')
cli.add_argument('-dump', help='print table to stdout', default=False, action='store_true')
cli.add_argument('-v', help='verbose mode', default=False, action='store_true')
args = cli.parse_args(sys.argv[1:])

if args.max < args.min:
    cli.error('Invalid run range, min>max:  min=%d  max=%d.' % (args.min, args.max))

if args.timestamp is not None:
    try:
        args.timestamp = datetime.datetime.strptime(args.timestamp, '%m/%d/%Y-%H:%M:%s')
    except ValueError:
        try:
            args.timestamp = datetime.datetime.strptime(args.timestamp, '%m/%d/%Y')
        except ValueError:
            cli.error('Invalid timestamp:  '+args.timestamp)

try:
    args.slco = [int(x) for x in args.slco.split('/')]
except:
    cli.error('Invalid s/l/c[/o]: '+args.slco)

import ccdb
provider = ccdb.AlchemyProvider()
provider.connect(os.getenv('CCDB_CONNECTION'))

try:
    column_names = [x.name for x in provider.get_type_table(args.table).columns]
except ccdb.errors.TypeTableNotFound:
    cli.error('Invalid table name:  '+args.table)
try:
    column_index = column_names.index(args.variable)
except ValueError:
    cli.error('Invalid variable name:  '+args.variable)
if column_index < 0:
    cli.error('Invalid variable name:  '+args.variable)

try:
    import matplotlib.pyplot as plt
    graph = []
    fig, (ax) = plt.subplots(1,1,figsize=(6,4))
    fig.suptitle('CCDB:  '+args.table+'.'+args.variable)
    ax.set_xlabel('Run Number')
    ax.set_ylabel('Value')
    ax.ticklabel_format(style='plain')
except ModuleNotFoundError:
    try:
        import ROOT
        graph = ROOT.TGraph()
        graph.SetLineWidth(2)
    except ModuleNotFoundError:
        cli.error('Could not find matplotlib nor ROOT for visualization.')

import sqlalchemy

for run in range(args.min, args.max+1):

    if args.v:
        print('Retrieving run #%d ...'%run)
    try:
        assignment = provider.get_assignment(args.table, run, args.variation, args.timestamp)
    except ccdb.errors.TypeTableNotFound:
        cli.error('Invalid table or variation:  %s/%s.' % (args.table, args.variation))
    except ccdb.errors.DirectoryNotFound:
        cli.error('Invalid table or variation:  table=%s  variation=%s.' % (args.table, args.variation))
    except sqlalchemy.orm.exc.NoResultFound:
        print('Warning:  no data found for run ',run)
        continue

    data_table = assignment.constant_set.data_table
    value = get_cell(data_table, args.slco, column_index)

    if value is not None and value not in args.ignore:
        if 'ROOT' in sys.modules:
            graph.AddPoint(run,value)
        else:
            graph.append((run,value))
        if args.dump:
            print(run,value)

if not args.batch:
    if 'ROOT' in sys.modules:
        graph.Draw()
        input()
    else:
        ax.plot(list(zip(*graph))[0],list(zip(*graph))[1], 'r', marker='.', linestyle='')
        plt.show()

