#!/usr/bin/env python3
import sys
import argparse

class RcdbManager():

  _URI='mysql://rcdb@clasdb.jlab.org/rcdb'
  _IGNORE=['temperature','json_cnd','test']

  def __init__(self):
    import rcdb
    self.data={}
    self.uri=self._URI
    self.types=None
    self.db = rcdb.RCDBProvider(self.uri)

  def load(self,run):
    if int(run) in self.data:
      return
    try:
      if self.types is None:
        self.types=self.db.get_condition_types()
        while True:
          pruned=False
          for ii in range(len(self.types)):
            if self.types[ii].name in self._IGNORE:
              self.types.pop(ii)
              pruned=True
              break
          if not pruned:
            break
    except:
      print('Failed connecting to '+self.uri)
      sys.exit(1)
    found=False
    self.data[int(run)]={}
    for t in self.types:
      self.data[int(run)][t.name]=''
      try:
        self.data[int(run)][t.name]=self.db.get_condition(int(run),t.name).value
        found=True
      except:
        pass
    if not found:
      self.data[int(run)]=None
      print('Failed to retrieve any constants for run '+str(run))
    self.db.disconnect()

  def get(self,run,key):
    self.load(run)
    if int(run) in self.data and self.data[int(run)] is not None and key in self.data[int(run)]:
      return self.data[int(run)][key]
    return None

  def csvHeader(self):
    return 'run,'+','.join([t.name for t in self.types])

  def csvRun(self,run):
    if self.data.get(run) is not None:
      return str(run)+','+','.join([str(self.data[run][t.name]) for t in self.types])
    return ''

  def csv(self):
    csv=[self.csvHeader()]
    for r in sorted(self.data.keys()):
      if self.data[r] is not None:
        csv.append(self.csvRun(r))
    return '\n'.join(csv)

  def __str__(self):
    import copy
    import json
    data=copy.deepcopy(self.data)
    for run in list(data.keys()):
      if data[run] is None:
        data.pop(run)
    return json.dumps(data,default=str,indent=2,separators=(',',': '))

cli=argparse.ArgumentParser(description='Dump RCDB to a spreadsheet.')
cli.add_argument('-j',help='use JSON format (default=CSV)', default=False, action='store_true')
cli.add_argument('rmin',metavar='RUNMIN',help='minimum run number',type=int)
cli.add_argument('rmax',metavar='RUNMAX',help='maximum run number',type=int)

args=cli.parse_args(sys.argv[1:])

if args.rmax < args.rmin:
  cli.error('rmax cannot be less than rmin')

rm = RcdbManager()
run = rm.db.get_next_run(args.rmin-1)
if run is None:
  cli.error('no valid runs found')

rows = []

while True:

  if run.number >= args.rmax:
    break

  x = rm.db.get_next_run(run)

  if x is None:
    run.number += 1

  else:
    run = x
    rm.load(run.number)

if args.j:
  print(rm)
else:
  print(rm.csv())

