#!/usr/bin/env python3
import os
import sys
import math
import time
import argparse
import datetime

version = 'v1.0'
timestamp = datetime.datetime.now().strftime('%y/%m/%d %H:%M:%S')
out_dir = './fcup-calib_%s'%timestamp.replace(' ','_').replace('/','-')
pv_names = {'scalerS2b':'fcup','beam_stop':'stop','IPM2C21A':'bpm','MBSY2C_energy':'energy'}

# beam current veto parameters:
bpm_veto_nA = 0.1
bpm_veto_seconds = [5.0,10.0]

# tolerance for choosing stopper attenuation:
energy_tolerance_MeV = 10.0

# position threshold for beam stopper: 
stopper_threshold = 10.0

# ignore any readings above this:
fcup_maximum_offset = 2000

# beam stopper calibrations:
# FIXME: index by run number instead of energy
attenuations = {
    10604 : 9.8088,
    10532 : 5.79985,     # RG-D
    10547 : 9.1508,  # RG-C
    10409 : 9.6930,
    10405 : 9.6930,  # unmeasured during BONuS, copied from 10409
    10375 : 9.6930,  # bogus beam energy from ACC during BONuS
    10339 : 9.6930,  # unmeasured during BONuS, copied from 10409
    10389 : 9.6930,  # unmeasured during BONuS, copied from 10409
    10197 : 9.6930,  # bogus beam energy from ACC, actually 10339
    10200 : 9.96025,
     7546 :14.89565,
     6535 :16.283,
     6423 :16.9726,
     2212 : 1.0,
}

# hack to tee stdout to a log file:
class Tee(object):
    def __init__(self, name, mode):
        self.name = name
        self.file = open(name, mode)
        self.stdout = sys.stdout
        sys.stdout = self
    def __del__(self):
        self.file.close()
    def write(self, data):
        self.file.write(data)
        self.stdout.write(data)
    def flush(self):
        self.file.flush()

# Convenience/exception wrapper for RCDB:
class RCDB:
    def __init__(self):
        import sqlalchemy
        import rcdb
        self.db = None
        self.url = 'mysql://rcdb@clasdb-farm.jlab.org/rcdb'
        try:
            self.db = rcdb.RCDBProvider(self.url)
            self.db.get_condition_types()
        except (AttributeError,sqlalchemy.exc.ArgumentError,sqlalchemy.exc.OperationalError):
            print('Could not connect to RCDB at '+self.url)
            sys.exit(1)
    def get_condition(self,run, name):
        try:
            return self.db.get_condition(run, name).value
        except AttributeError:
            print('ERROR:  %s unavailable for run %d in RCDB.'%(name, run))
            return None
    def get_event_count(self, run):
        return self.get_condition(run, 'event_count')
    def get_timespan(self, first_run, last_run):
        start = self.get_condition(first_run, 'run_start_time')
        end = self.get_condition(last_run, 'run_end_time')
        if start is None or end is None:
            return None
        if start >= end:
            print('ERROR:  Invalid range:  %s (%d) -> %s (%d)'%(start,first_run,end,last_run))
            return None
        return start,end
    def cleanup(self):
        try:
            self.db.disconnect()
        except AttributeError:
            pass

# Convenience class for CCDB table and storing results:
class FcupTable:
    table_name = '/runcontrol/fcup'
    def __init__(self, runmin=None, runmax=None, offset=None, offset_rms=None, atten=None, slope=906.2):
        self.runmin = runmin
        self.runmax = runmax
        self.slope = slope
        self.offset = offset
        self.offset_rms = offset_rms
        self.atten = atten
        self.span = None
    def __str__(self):
        s = '# %s-%s %s %d-%d\n'%(os.path.basename(__file__),version,timestamp,self.runmin,self.runmax)
        return s + '0 0 0 %.2f %.2f %.5f'%(self.slope, self.offset, self.atten)
    def status(self):
        return self.offset is not None and self.atten is not None
    def minutes(self):
        if self.span is not None:
            return '%.1f'%((self.span[1]-self.span[0]).seconds/60)
        return '?'
    def pretty(self):
        return '%.2f %.2f(%.2f) %.5f'%(self.slope, self.offset, self.offset_rms, self.atten)
    def save(self):
        self.filename = '%s/fcup-%d-%d.txt'%(out_dir,self.runmin,self.runmax)
        with open(self.filename,'w') as f:
            f.write(str(self))
    def get_cmd(self):
        return 'ccdb -c $CCDB_CONNECTION add -r %d-%d %s'%(self.runmin,self.runmax,os.path.basename(self.filename))

def load_mya(dfs, pv, alias, args):
    start = time.perf_counter()
    url = 'https://epicsweb.jlab.org/myquery/interval?p=1&a=1&d=1'
    url += '&c=%s&m=%s&b=%s&e=%s'%(pv,args.m,args.start,args.end)
    if args.v>2:
        print(url)
    import requests
    from requests.adapters import HTTPAdapter,Retry
    import pandas
    requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
    retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[500,502,503,504])
    session = requests.Session()
    session.mount(url, HTTPAdapter(max_retries=retries))
    result = session.get(url, timeout=1.0, verify=False)
    dfs[alias] = pandas.DataFrame(result.json().get('data'))
    dfs[alias].rename(columns={'d':'t', 'v':alias}, inplace=True)
    if args.v>0:
        print('Got %d points from Mya for %s in %.1f seconds.'
            %(len(dfs[alias].index), pv, time.perf_counter()-start))
        if args.v>1:
            print(dfs[alias])

def get_atten(run, stopper, energy):
    if stopper < stopper_threshold:
        return 1.0
    else:
        if run>=12444 and run<=12853:
            # fix bad beam energy from MCC:
            energy = 10405
        for e,a in attenuations.items():
            if math.fabs(e-energy) < energy_tolerance_MeV:
                return a
    print('ERROR:  Unknown beam energy:  %.2f'%energy)
    return None

def analyze(df, args):
    import types
    start_time = None
    offsets,fcups = [],[]
    if args.v>2:
        print(df.to_string())
    for x in df.iterrows():
        if start_time is not None:
            if not math.isnan(x[1].fcup) and x[1].fcup<fcup_maximum_offset:
                if x[1].t > start_time + 1000*bpm_veto_seconds[0]:
                    fcups.append((x[1].t, x[1].fcup))
        if not math.isnan(x[1].bpm):
            if x[1].bpm < bpm_veto_nA:
                if start_time is None:
                    start_time = x[1].t
                    fcups = []
            elif start_time is not None:
                start_time = None
                for k,v in fcups:
                    if k < x[1].t - 1000*bpm_veto_seconds[1]:
                        offsets.append(v)
    ret = FcupTable()
    ret.noffsets = len(offsets)
    ret.energies = list(set(list(df[df.energy.notnull()].energy)))
    ret.stops = list(set(list(df[df.stop.notnull()].stop)))
    if ret.noffsets > 0:
        import functools
        if args.v>1:
            print('Offsets:  '+' '.join([str(x) for x in offsets]))
        ret.offset = functools.reduce(lambda x,y: x+y, offsets) / len(offsets)
        ret.offset_rms = math.sqrt(sum([ math.pow(x-ret.offset,2) for x in offsets]) / len(offsets))
    return ret

def process(args, runmin, runmax):
    ret = FcupTable()
    span = args.db.get_timespan(runmin, runmax)
    if span is None:
        return ret
    args.start = span[0].strftime('%Y-%m-%dT%H:%M:%S')
    args.end = span[1].strftime('%Y-%m-%dT%H:%M:%S')
    dfs = {}
    if args.v>1:
        print('Using Mya date range:  %s (%d) -> %s (%d)'%(args.start,runmin,args.start,runmax))
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for pv,alias in pv_names.items():
            if args.v>0:
                print('Reading %s from Mya ...'%pv)
            futures.append(executor.submit(load_mya,dfs,pv,alias,args))
        concurrent.futures.wait(futures)
        for f in futures:
            if f.exception() is not None:
                print(f.exception())
                sys.exit(222)
    if max([ len(x.index) for x in dfs.values()]) <= 2:
        print('ERROR:  no data found for %d-%d.'%(runmin,runmax))
        return ret
    import pandas
    df = pandas.concat(dfs.values()).sort_values('t')
    if args.v>0:
        print('Analyzing data ...')
        if args.v>1:  print(df)
    start = time.perf_counter()
    ret = analyze(df, args)
    ret.runmin = runmin
    ret.runmax = runmax
    ret.span = span
    if args.v>0:
        print('Analyzing data took %.1f seconds.'%(time.perf_counter()-start))
        print('Found %d fcup offset points with an average of %s.'%
        (ret.noffsets,str(ret.offset)))
    if len(ret.energies) > 1:
        print('ERROR:  found multiple beam energies for %d:  %s'%(runmin,' '.join([str(x) for x in ret.energies])))
        return ret
    if len(ret.stops) > 1:
        print('ERROR:  found multiple beam stopper positions for %d:  %s'%(runmin,' '.join([str(x) for x in ret.stops])))
        return ret
    if ret.noffsets < 5:
        print('ERROR:  only %d points found for fcup offset for %d-%d.'%(ret.noffsets,runmin,runmax))
        return ret
    elif ret.noffsets < 10:
        print('WARNING:  only %d points found for fcup offset for %d-%d.'%(ret.noffsets,runmin,runmax))
    ret.atten = get_atten(runmin, ret.stops[0], ret.energies[0])
    if ret.status() and args.v>0:
        print(ret)
    return ret

def plot(path):
    import pandas as pd
    data = pd.read_csv(path,sep='\s+',header=None)
    data = pd.DataFrame(data)
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    ax.set_ylabel('Faraday Cup Offset  (Hz)')
    ax.set_xlabel('Run Number')
    x = data[0]
    y = data[2]
    ey = data[3]
    plt.plot(x, y,'r',marker='.',linestyle='')
    plt.errorbar(x, y, xerr=None, yerr=ey, fmt='r',marker='.',linestyle='')
    print('Close plot window to quit.')
    plt.show()

if __name__ == '__main__':

    cli = argparse.ArgumentParser(description='Calibrate Faraday cup offset and attenuation for CCDB.',epilog='For details, see https://clasweb.jlab.org/wiki/index.php/CLAS12_Faraday_Cup_Calibration_Procedure.  Note, after a year or two, EPICS data are moved to the Mya "history" deployment and may require using the -m option.  Example usage:  "fcup-calib.py -m history 17100,17101"') 
    cli.add_argument('runs', help='run range or list, e.g., 100-200 or 1,4,7 or 1 4 7', nargs='*')
    cli.add_argument('-s', help='single calculation over all runs', default=False, action='store_true')
    cli.add_argument('-d', help='dry run, no output files', default=False, action='store_true')
    cli.add_argument('-v', help='verbose mode (multiple allowed)', default=0, action='count')
    cli.add_argument('-g', help='graphics mode (optionally, specify path to previously generated view file', metavar='VIEW', default=False, const=True, nargs='?')
    cli.add_argument('-m', help='Mya deployment (default=ops)', default='ops', choices=['ops','history'])
    args = cli.parse_args(sys.argv[1:])

    if isinstance(args.g, str):
        plot(args.g)
        sys.exit(0)

    if len(args.runs) == 0:
        cli.error('runs argument is required')
    if not args.d:
        tee = Tee('./fcup-calib_%s.log'%timestamp.replace(' ','_').replace('/','-'),'w')

    try:
        if len(args.runs)>1 or args.runs[0].isdigit():
            # it's a space-separated list of runs
            args.runs = sorted([ int(x) for x in args.runs ])
            args.min = args.runs[0]
            args.max = args.runs[len(args.runs)-1]
        elif ',' in args.runs[0]:
            # it's a comma-separated list of runs
            args.runs = sorted([ int(x) for x in args.runs[0].split(',') ])
            args.min = args.runs[0]
            args.max = args.runs[len(args.runs)-1]
        elif '-' in args.runs[0]:
            # it's a dash-separated run range
            args.min,args.max = [int(x) for x in args.runs[0].split('-')]
            args.runs = None
            if args.max < args.min:
                cli.error('max is less than min')
        else:
            raise ValueError()
    except (ValueError,TypeError):
        cli.error('Invalid "runs" argument:  '+str(args.runs))

    args.db = RCDB()
    import atexit
    atexit.register(args.db.cleanup)
    runs = []

    if args.s:
        # single calibration over inclusive, full time range:
        runs.append(('%s-%s'%(args.min,args.max), process(args, args.min, args.max)))
    elif args.runs:
        # one calibration per run from user-specified list:
        for run in args.runs:
            runs.append((str(run), process(args, run, run)))
            run = args.db.db.get_next_run(run).number
    else:
        # one calibration per run in RCDB: 
        run = args.min
        while run <= args.max:
            runs.append((str(run), process(args, run, run)))
            run = args.db.db.get_next_run(run).number

    # print a bunch of stuff:
    sep = '\n'+':'*40
    ngood = len(list(filter(lambda x : x[1].status(), runs)))
    nbad = len(list(filter(lambda x : not x[1].status(), runs)))
    if ngood > 0:
        print(sep+'\n: Runs Calibrated (%d)'%ngood+sep)
        [ print(r[0],':',r[1].pretty()) for r in filter(lambda x : x[1].status(), runs) ]
        if not args.d:
            print(sep+'\n: To Upload'+sep)
            print('1. set CCDB_CONNECTION for clas12writer')
            print('2. cd %s\n3. chmod +x upload\n4. ./upload'%out_dir)
    if nbad > 0:
        print(sep+'\n: Runs with Errors (%d)'%nbad+sep)
        for r in filter(lambda x : not x[1].status(), runs):
            print(r[0],'[%s minutes]'%(r[1].minutes()),'https://clasweb.jlab.org/rcdb/runs/info/'+r[0].split('-').pop(0))
    if not args.d:
        print('\nLogs saved to '+tee.name)
        if ngood > 0:
            os.makedirs(out_dir)
            with open('%s/upload'%out_dir,'w') as f:
                for run in filter(lambda x : x[1].status(), runs):
                    run[1].save()
                    f.write(run[1].get_cmd()+'\n')
            with open('%s/view'%out_dir,'w') as f:
                for run in filter(lambda x : x[1].status(), runs):
                    f.write('%d %.2f %.2f %.2f %.5f\n'%(run[1].runmin,run[1].slope,run[1].offset,run[1].offset_rms,run[1].atten))
            print('CCDB tables written to %s'%out_dir)
            print('Table for plotting written to %s/view\n'%out_dir)
            if args.g:
                plot('%s/view'%out_dir)

