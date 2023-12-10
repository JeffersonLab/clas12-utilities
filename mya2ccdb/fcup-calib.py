#!/usr/bin/env python3
import os
import sys
import math
import time
import types
import atexit
import getpass
import argparse
import datetime
import functools
import concurrent.futures

import pandas
import requests
import sqlalchemy
import rcdb

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

# beam stopper calibrations:
attenuations = {
    10604 : 9.8088,
    10532 : None,    # RG-D
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

example_url_offset = 'https://epicsweb.jlab.org/wave/?start=2023-12-09T20%3A41%3A10.315&end=2023-12-09T20%3A46%3A10.315&myaDeployment=&myaLimit=100000&windowMinutes=30&title=&fullscreen=false&layoutMode=1&viewerMode=1&pv=IPM2C21A&pv=scalerS2b&IPM2C21Alabel=Beam+Current+-+2C21A+BPM+%28nA%29&IPM2C21Acolor=%230000ff&IPM2C21AyAxisLabel=&IPM2C21AyAxisMin=&IPM2C21AyAxisMax=&IPM2C21AyAxisLog&IPM2C21Ascaler=&scalerS2blabel=Raw+Faraday+Cup+%28Hz%29&scalerS2bcolor=%23ff0000&scalerS2byAxisLabel=&scalerS2byAxisMin=&scalerS2byAxisMax=&scalerS2byAxisLog&scalerS2bscaler='

example_url_stop = 'https://epicsweb.jlab.org/wave/?start=2023-12-09T21%3A46%3A29.975&end=2023-12-09T21%3A51%3A29.975&myaDeployment=&myaLimit=100000&windowMinutes=30&title=&fullscreen=false&layoutMode=1&viewerMode=1&pv=beam_stop&pv=MBSY2C_energy&MBSY2C_energylabel=Beam+Energy+%28MeV%29&MBSY2C_energycolor=%230000ff&MBSY2C_energyyAxisLabel=&MBSY2C_energyyAxisMin=&MBSY2C_energyyAxisMax=&MBSY2C_energyyAxisLog&MBSY2C_energyscaler=&beam_stoplabel=Beam+Stopper+Position&beam_stopcolor=%23ff0000&beam_stopyAxisLabel=&beam_stopyAxisMin=&beam_stopyAxisMax=&beam_stopyAxisLog&beam_stopscaler='

info = '''
Run start and end times are determined from RCDB, corresponding EPICS data is retrieved from the Mya archive, and Faraday cup calibrations are prepared for uploading to CCDB\'s /runcontrol/fcup table.

* Faraday cup offset is calculated as an average of raw scaler readings with a veto on BPMs above %.1f nA and a -%d/+%d second time window.

* Beam stopper attenuation is based on beam energy and an internal lookup table that may require updating for new experimental conditions.

* Issues detected, e.g., invalid parameters from RCDB, multiple or unkonwn beam energies, or multiple beam stopper positions in a single run, are reported and no tables are generated for affected runs.

* After a year or two, EPICS data are moved to the Mya "history" deployment and may require using the -m option.

* A Mya archive URL for investigating Faraday cup offset:  \n%s

* A Mya archive URL for investigating beam stopper attenuation:  \n%s
'''

info = info % (bpm_veto_nA,bpm_veto_seconds[0],bpm_veto_seconds[1],example_url_offset,example_url_stop)

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

class RCDB:
    def __init__(self):
        self.db = None
        if os.getenv('RCDB_CONNECTION') is None:
            print('ERROR:  Undefined $RCDB_CONNECTION.')
            sys.exit(1)
        else:
            try:
                self.db = rcdb.RCDBProvider(os.getenv('RCDB_CONNECTION'))
                self.db.get_condition_types()
            except (AttributeError,sqlalchemy.exc.ArgumentError,sqlalchemy.exc.OperationalError):
                print('Invalid $RCDB_CONNECTION: %s'%os.getenv('RCDB_CONNECTION'))
                sys.exit(1)
    def get_condition(self,run, name):
        try:
            return self.db.get_condition(run, name).value
        except AttributeError:
            print('ERROR:  %s unavailable for run %d in RCDB.'%(name, run))
            return None
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

class FcupTable:
    def __init__(self, runmin, runmax, slope, offset, atten):
        self.runmin = runmin
        self.runmax = runmax
        self.slope = slope
        self.offset = offset
        self.atten = atten
        self.filename = '%s/fcup-%d-%d.txt'%(out_dir,runmin,runmax)
    def __str__(self):
        s = '# %s-%s %s %d-%d\n'%(os.path.basename(__file__),version,timestamp,self.runmin,self.runmax)
        return s + '0 0 0 %.2f %.2f %.5f'%(self.slope, self.offset, self.atten)
    def save(self):
        with open(self.filename,'w') as f:
            f.write(str(self))
    def get_cmd(self):
        return 'ccdb -c $CCDB_CONNECTION add -r %d-%d %s'%(self.runmin,self.runmax,os.path.basename(self.filename))

def load_mya(dfs, pv, alias, args):
    start = time.perf_counter()
    url = 'https://epicsweb.jlab.org/myquery/interval?p=1&a=1&d=1'
    url += '&c=%s&m=%s&b=%s&e=%s'%(pv,args.m,args.start,args.end)
    if args.v:  print(url)
    dfs[alias] = pandas.DataFrame(requests.get(url).json().get('data'))
    dfs[alias].rename(columns={'d':'t', 'v':alias}, inplace=True)
    if args.v:  print(dfs[alias])
    if not args.q:
        print('Got %d points from Mya for %s in %.1f seconds.'
            %(len(dfs[alias].index), pv, time.perf_counter()-start))

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

def analyze(df):
    ret = types.SimpleNamespace(table=None,slope=None,atten=None,offset=None,noffsets=0,stops=[],energies=[])
    start_time = None
    offsets,fcups = [],[]
    for x in df.iterrows():
        if not math.isnan(x[1].energy):
            ret.energies.append((x[1].t,x[1].energy))
        if not math.isnan(x[1].stop):
            ret.stops.append((x[1].t,x[1].stop))
        if start_time is not None:
            if not math.isnan(x[1].fcup):
                if x[1].t > start_time + 1000*bpm_veto_seconds[0]:
                    fcups.append((x[1].t, x[1].fcup))
        if not math.isnan(x[1].bpm):
            if x[1].bpm < bpm_veto_nA:
                if start_time is None:
                    start_time = x[1].t
                    fcups = []
            elif start_time is not None:
                for k,v in fcups:
                    if k < x[1].t - 1000*bpm_veto_seconds[1]:
                        offsets.append(v)
                start_time = None
    ret.noffsets = len(offsets)
    if ret.noffsets > 0:
        ret.offset = functools.reduce(lambda x,y: x+y, offsets) / len(offsets)
    return ret

def process(args, runmin, runmax):
    span = args.db.get_timespan(runmin, runmax)
    if span is None:
        return False
    args.start = span[0].strftime('%Y-%m-%dT%H:%M:%S')
    args.end = span[1].strftime('%Y-%m-%dT%H:%M:%S')
    dfs = {}
    if not args.q:
        print('Using Mya date range:  %s (%d) -> %s (%d)'%(args.start,runmin,args.start,runmax))
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for pv,alias in pv_names.items():
            if not args.q:
                print('Reading %s from Mya ...'%pv)
            futures.append(executor.submit(load_mya,dfs,pv,alias,args))
        concurrent.futures.wait(futures)
    max_len = 0
    if [ max(max_len,len(df.index)) for df in dfs.values() ].pop() <= 2:
        print('ERROR:  No intermediate data found.  Maybe try the other deployment?')
        return False
    df = pandas.concat(dfs.values()).sort_values('t')
    if args.v:  print(df)
    if not args.q:  print('Analyzing data ...')
    start = time.perf_counter()
    result = analyze(df)
    if not args.q:
        print('Analyzing data took %.1f seconds.'%(time.perf_counter()-start))
        print('Found %d fcup offset points with an average of %s.'%
        (result.noffsets,str(result.offset)))
    for i in range(1,len(result.energies)):
        if result.energies[i][1] != result.energies[i-1][1]:
            print('ERROR:  found multiple beam energies.')
            return False
    for i in range(1,len(result.stops)):
        if result.stops[i][1] != result.stops[i-1][1]:
            print('ERROR:  found multiple beam stopper positions.')
            return False
    if result.noffsets < 5:
        print('ERROR:  only %d points found for fcup offset.'%result.noffsets)
        return False
    elif result.noffsets < 10:
        print('WARNING:  only %d points found for fcup offset.'%result.noffsets)
    atten = get_atten(runmin, result.stops[0][1], result.energies[0][1])
    if result.offset and result.noffsets > 10 and atten:
        f = FcupTable(runmin, runmax, 906.2, result.offset, atten)
        print(f)
        return f
    return False

if __name__ == '__main__':

    cli = argparse.ArgumentParser(description='Calibrate Faraday cup offset and attenuation for CCDB.')
    cli.add_argument('runs', help='run range or list, e.g., 100-200 or 1,4,7 or 1 4 7', nargs='*')
    cli.add_argument('-s', help='single calculation over all runs', default=False, action='store_true')
    cli.add_argument('-d', help='dry run, no output files', default=False, action='store_true')
    cli.add_argument('-v', help='verbose mode', default=False, action='store_true')
    cli.add_argument('-q', help='quiet mode', default=False, action='store_true')
    cli.add_argument('-m', help='Mya deployment (default=ops)', default='ops', choices=['ops','history'])
    cli.add_argument('-i', help='print detailed information', default=False, action='store_true')
    args = cli.parse_args(sys.argv[1:])

    sep = '\n'+':'*30

    if args.i:
        cli.print_usage()
        print('\n'+cli.description)
        print(sep)
        print(info)
        sys.exit(0)

    if len(args.runs) == 0:
        cli.error('runs argument is required')

    if not args.d:
        tee = Tee('./fcup-calib_%s.log'%timestamp.replace(' ','_').replace('/','-'),'w')

    try:
        if len(args.runs)>1:
            args.runs = sorted([ int(x) for x in args.runs ])
        elif args.runs[0].find('-') > 0:
            args.min,args.max = [int(x) for x in args.runs[0].split('-')]
            if args.max < args.min:
                cli.error('max is less than min')
        else:
            args.runs = sorted([ int(x) for x in args.runs[0].split(',') ])
            args.min = args.runs[0]
            args.max = args.runs[len(args.runs)-1]
    except (ValueError,TypeError):
        cli.error('Invalid "runs" argument:  '+str(args.runs))

    runs = []
    args.db = RCDB()
    atexit.register(args.db.cleanup)

    if args.s:
        runs.append(('%s-%s'%(args.min,args.max), process(args, args.min, args.max)))
    elif len(args.runs) > 1:
        for run in args.runs:
            runs.append((str(run), process(args, run, run)))
            run = args.db.db.get_next_run(run).number
    else:
        run = args.min
        while run <= args.max:
            runs.append((str(run), process(args, run, run)))
            run = args.db.db.get_next_run(run).number

    ngood = len(list(filter(lambda x : x[1], runs)))
    nbad = len(list(filter(lambda x : not x[1], runs)))

    if ngood > 0:
        print(sep+'\n: Runs Calibrated (%d)'%ngood+sep)
        [ print(r[0]) for r in filter(lambda x : x[1], runs) ]
        if not args.d:
            print(sep+'\n: To Upload'+sep)
            print('1. set CCDB_CONNECTION for clas12writer')
            print('2. cd %s\n3. chmod +x upload\n4. ./upload'%out_dir)

    if nbad > 0:
        print(sep+'\n: Runs with Errors (%d)'%nbad+sep)
        for r in filter(lambda x : not x[1], runs):
            print(r[0],'https://clasweb.jlab.org/rcdb/runs/info/'+r[0].split('-').pop(0))

    if not args.d:
        print('\nLogs saved to '+tee.name)
        if ngood > 0:
            print('CCDB tables written to %s\n'%out_dir)
            os.makedirs(out_dir)
            with open('%s/upload'%out_dir,'w') as f:
                for run in filter(lambda x : x[1], runs):
                    run[1].save()
                    f.write(run[1].get_cmd()+'\n')

