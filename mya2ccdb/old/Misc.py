import rcdb
from CcdbUtil import HwpCcdbEntry
from MyaData import MyaData

def _epics2ccdb(hwp):
  if hwp==1:
    return -1
  if hwp==0:
    return 1
  return 0

def getHWP(run_min,run_max):

  db=rcdb.RCDBProvider('mysql://rcdb@clasdb.jlab.org/rcdb')
  
  prev_hwp,run_start=None,None

  ret=[]

  for x in db.select_values(['half_wave_plate'],'',run_min,run_max):

    if x is None or x[0] is None or x[1] is None:
      continue

    run,hwp=int(x[0]),int(x[1])

    if run_start is None:
      run_start = run
    if prev_hwp is None:
      prev_hwp = hwp

    if prev_hwp != hwp:

      ret.append(HwpCcdbEntry(run_start,run-1,{'hwp':_epics2ccdb(prev_hwp)}))

      prev_hwp = hwp
      run_start = run

  ret.append(HwpCcdbEntry(run_start,run_max,{'hwp':_epics2ccdb(prev_hwp)}))

  for x in ret: print(str(x))

  return ret

getHWP(11608,11755)

