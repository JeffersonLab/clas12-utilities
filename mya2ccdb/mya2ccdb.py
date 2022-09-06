#!/usr/bin/env python
import os,re,sys,argparse,copy,argparse
from collections import OrderedDict
from MyaData import MyaData
from MyaFcup import MyaFcup
from CcdbUtil import *
#
# Use MYA EPICS archive to get Faraday cup offset, beam blocker attenuation,
# and half-wave plate status for CCDB.
#
# FIXME:  temporary data storage needs to be changed to allow more methods
#
# Note, the DAQ run number in EPICS only updates at the beginning of runs,
# so discrete (e.g. beam stopper attenuation, HWP) and averaging quantities
# must be handled differently.

# Note, with fcup scaler at ~1 kHz/nA, and beam stopper attenuation of 10X,
# then at 10 nA a 10 Hz offset is ~1% error on beam charge.  Normally the
# beam stopper would be OUT at 10 nA, or ~0.1% error per 10 Hz offset.  So
# we choose a conservative deadband of 10 Hz, sufficient for all cases.
fcup_offset_deadband=10

# Rafo suggested 100 will be safe, go a bit lower to be conservative:
slm_offset_deadband=50

cli=argparse.ArgumentParser(description='Extract fcup/hwp info from Mya archive for CCDB.')
cli.add_argument('start',help='start date (YYYY-MM-DD_HH:MM:SS)',type=str)
cli.add_argument('end',help='end date (YYYY-MM-DD_HH:MM:SS)',type=str)
cli.add_argument('-v',help='verbose mode',default=False,action='store_true')
cli.add_argument('-i',help='ignore unknown beam energies',default=False,action='store_true')
args=cli.parse_args(sys.argv[1:])

# mya date format: (Y-M-D H:M:S, with fixed widths:)
fmt='^\d\d\d\d-\d\d-\d\d_\d\d:\d\d:\d\d$'

mm=re.match(fmt,args.start)
if mm is None: cli.error('Invalid start date format: '+args.start)
mm=re.match(fmt,args.end)
if mm is None: cli.error('Invalid end date format: '+args.end)

# check up-front if the ouptuts already exists:
for x in ['fcup2ccdb.sh','hwp2ccdb.sh','slm2ccdb.sh','hwp-data','fcup-data','slm-data']:
  if os.path.exists(x):
    print('ERROR:  Output already Exists:  '+x)
    sys.exit(1)

print('Start:   '+args.start)
print('End:     '+args.end)

# convert to Mya's required date+time format:
args.start = args.start.replace('_',' ')
args.end = args.end.replace('_',' ')

myaData = MyaData(args.start,args.end)
myaData.addPv('B_DAQ:run_number')
myaData.addPv('MBSY2C_energy')
myaData.addPv('fcup_offset',2)
myaData.addPv('slm_offset',20)
myaData.addPv('beam_stop',5)
myaData.addPv('IGL1I00OD16_16')

runData=OrderedDict()
hwpData=OrderedDict()
badEnergies=set()

###################################################################
###################################################################

# Load all data from MYA archive, ignore invalids, apply deadbands,
# and register changes:
previous=None
for myaDatum in myaData.get():

  current = MyaFcup(myaDatum)

  # if data invalid, assume it's the same as the previous:
  if current.atten is None:
    if current.stopper is not None:
      if previous is not None and args.i:
        current.energy = previous.energy
      else:
        badEnergies.add((current.run,current.energy))
    if previous is not None:
      current.atten = previous.atten
  if previous is not None:
    if current.run is None:
      current.run = previous.run
    if current.hwp is None:
      current.hwp = previous.hwp
    if current.slm_offset is None:
      current.slm_offset = previous.slm_offset
    if current.offset is None:
      current.offset = previous.offset

  # for HWP, only check if run number changed:
  if previous is None or current.run != previous.run:
    hwpData[current.run]=current.hwp

  # for everything else, figure out if anything changed enough:
  changed=False

  if previous is None:
    changed=True
  else:
    # check if run number changed
    if current.run is not None:
      if previous.run is None or current.run != previous.run:
        changed=True
    # check if attenuation changed:
    if current.atten is not None:
      if previous.atten is None or abs(current.atten-previous.atten) > 0.01:
        changed=True
    # check if fcup_offset changed:
    if current.offset is not None:
      if previous.offset is None or abs(current.offset-previous.offset) > 2.0:
        changed=True
    # check if slm_offset changed:
    if current.slm_offset is not None:
      if previous.slm_offset is None or abs(current.slm_offset-previous.slm_offset) > 5.0:
        changed=True

  # if data changed, append the data for this run:
  if changed:
    if current.run not in runData:
      runData[current.run]=[]
    runData[current.run].append(current)

  # update the previous values:
  previous=current

###################################################################
###################################################################

# print any unknown beam energies:
if len(badEnergies)>0:
  print(('\nERROR:  Unknown Beam Energies:\n'+'\n'.join([str(e) for e in badEnergies])))
  sys.exit(1)

if args.v:
  # print all registered changes:
  print('\nData:::::::::::::::::::::::::::::::::::::::')
  for run,data in runData.items():
    for datum in data: print(datum)

###################################################################
###################################################################

def getOffsetAverage(data):
  x = [ datum.offset for datum in data ]
  return sum(x) / len(x)
def getSlmOffsetAverage(data):
  x = [ datum.slm_offset for datum in data ]
  return sum(x) / len(x)

###################################################################
###################################################################

offsets,attens,slm_offsets=[],[],[]

# register attenuation changes:
tmp = copy.deepcopy(runData)
firstRun,firstData = tmp.popitem(False)
if len(tmp)==0:
  attens.append(FcupCcdbEntry(firstRun,firstRun,{'atten':firstData[0].atten}))
while len(tmp)>0:
  thisRun,thisData = tmp.popitem(False)
  # consider only the first attenuation in each run:
  runs=None
  if len(tmp)==0:
    runs = [firstRun,thisRun]
  elif abs(firstData[0].atten-thisData[0].atten)>0.1:
    runs = [firstRun,thisRun-1]
  if runs is not None:
    attens.append(FcupCcdbEntry(runs[0],runs[1],{'atten':firstData[0].atten}))
    firstRun,firstData = thisRun,thisData

# register offset changes, with a running-average:
tmp = copy.deepcopy(runData)
firstRun,firstData = tmp.popitem(False)
if len(tmp)==0:
  offsets.append(FcupCcdbEntry(firstRun,firstRun,{'offset':round(getOffsetAverage(firstData),1)}))

while len(tmp)>0:
  lastRun,lastData = tmp.popitem(False)
  firstOffset = getOffsetAverage(firstData)
  lastOffset = getOffsetAverage(lastData)
  if abs(lastOffset-firstOffset) > fcup_offset_deadband or len(tmp)==0:
    offsets.append(FcupCcdbEntry(firstRun,lastRun-1,{'offset':round(firstOffset,1)}))
    firstRun,firstData = lastRun,lastData

# register slm_offset changes, with a running-average:
tmp = copy.deepcopy(runData)
firstRun,firstData = tmp.popitem(False)
if len(tmp)==0:
  slm_offsets.append(SlmCcdbEntry(firstRun,firstRun,{'offset':round(getSlmOffsetAverage(firstData),1)}))
while len(tmp)>0:
  lastRun,lastData = tmp.popitem(False)
  firstOffset = getSlmOffsetAverage(firstData)
  lastOffset = getSlmOffsetAverage(lastData)
  if abs(lastOffset-firstOffset) > slm_offset_deadband or len(tmp)==0:
    slm_offsets.append(SlmCcdbEntry(firstRun,lastRun-1,{'offset':round(firstOffset,1)}))
    firstRun,firstData = lastRun,lastData

# set last change's upper run limit to infinity:
offsets[len(offsets)-1].runMax=None
attens[len(attens)-1].runMax=None
slm_offsets[len(slm_offsets)-1].runMax=None

###################################################################
###################################################################

print('\nFaraday Cup Offsets::::::::::::::::::::::::')
print('\n'.join([str(x) for x in offsets]))
print('\nBeam Blocker Attenuations::::::::::::::::::')
print('\n'.join([str(x) for x in attens]))
print('')
print('\nSLM Offsets::::::::::::::::::::::::::::::::')
print('\n'.join([str(x) for x in slm_offsets]))
print('')
print('')

###################################################################
###################################################################

fcmd=open('fcup2ccdb.sh','w')
tmp = copy.deepcopy(runData)
runStart=tmp.keys()[0]
previous=None
while len(tmp.keys())>0:
  run,data = tmp.popitem(False)
  offset,atten=None,None
  for ii in range(len(offsets)):
    if offsets[ii].contains(run):
      offset=offsets[ii].data
      break
  for ii in range(len(attens)):
    if attens[ii].contains(run):
      atten=attens[ii].data
      break
  data=dict(offset,**atten)
  if previous is not None and previous!=data or len(tmp.keys())==0:
    if previous is None:
      previous=data
    f=FcupCcdbEntry(runStart,run-1,previous)
    if len(tmp.keys())==0:
      f.runMax=None
    runStart=run
    print(f)
    f.writeFile(directory='./fcup-data')
    fcmd.write(f.getCommand()+'\n')
  previous=data
fcmd.close()

fcmd=open('slm2ccdb.sh','w')
tmp = copy.deepcopy(runData)
runStart=tmp.keys()[0]
previous=None
while len(tmp.keys())>0:
  run,data = tmp.popitem(False)
  offset,atten=None,None
  for ii in range(len(slm_offsets)):
    if slm_offsets[ii].contains(run):
      offset=slm_offsets[ii].data
      break
  data=dict(offset)
  if previous is not None and previous!=data or len(tmp.keys())==0:
    if previous is None:
      previous=data
    f=SlmCcdbEntry(runStart,run-1,previous)
    if len(tmp.keys())==0:
      f.runMax=None
    runStart=run
    print(f)
    f.writeFile(directory='./slm-data')
    fcmd.write(f.getCommand()+'\n')
  previous=data
fcmd.close()

###################################################################
###################################################################

fcmd=open('hwp2ccdb.sh','w')
runStart,hwpStart=hwpData.popitem(False)
while len(hwpData)>0:
  run,hwp = hwpData.popitem(False)
  if hwp != hwpStart or len(hwpData) == 0:
    if hwp != hwpStart:
      runEnd = run - 1
    else:
      runEnd = run
    entry = HwpCcdbEntry(runStart,runEnd,data={'hwp':hwpStart})
    print(entry)
    entry.writeFile(directory='./hwp-data')
    fcmd.write(entry.getCommand()+'\n')
    runStart,hwpStart = run,hwp
fcmd.close()

print('')

