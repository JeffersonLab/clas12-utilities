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

# position threshold for beam stopper in/out: 
stopper_threshold = 10.0

# tolerance for stopper changes:
stopper_deadband = 1.0

# ignore any readings above this:
fcup_maximum_offset = 2000

# beam stopper calibrations:
# FIXME: index by run number instead of energy
attenuations = {
    10604 : 9.8088,
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

#
# Just to tee stdout to a log file:
#
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

#
# Convenience/exception wrapper for RCDB:
#
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
    def get_condition(self, run, name):
        try:
            return self.db.get_condition(run, name).value
        except AttributeError:
            return None
    def pretty_event_count(self, run):
        n = self.get_condition(run, 'event_count')
        if n is not None:
            return '%4.1e'%n
        return '  ? '
    def get_event_count(self, run):
        return self.get_condition(run, 'event_count')
    def get_start_time(self, run, expand=0):
        r = int(run)
        for i in range(expand+1):
            c = self.get_condition(r, ['run_start_time','run_end_time'][i%2])
            if c is not None:
                return c
            if i%2 == 0:
                print('WARNING:  using time from previous run')
                r = self.db.get_prev_run(r)
        return None
    def get_end_time(self, run, expand=0):
        r = int(run)
        for i in range(expand+1):
            c = self.get_condition(r, ['run_end_time','run_start_time'][i%2])
            if c is not None:
                return c
            if i%2 == 0:
                print('WARNING:  using time from next run')
                r = self.db.get_next_run(r)
        return None
    def get_time_span(self, first_run, last_run, expand=0):
        start = self.get_start_time(first_run, expand=expand)
        end = self.get_end_time(last_run, expand=expand)
        if start is None or end is None:
            return None
        return start,end
    def cleanup(self):
        try:
            self.db.disconnect()
        except AttributeError:
            pass

#
# Convenience class for CCDB table and storing results:
#
class FcupTable:
    table_name = '/runcontrol/fcup'
    def __init__(self, runmin=None, runmax=None, offset=None, offset_rms=None, atten=None, slope=906.2):
        self.runmin = runmin
        self.runmax = runmax
        self.slope = slope
        self.offset = offset
        self.offset_rms = offset_rms
        self.atten = atten
        self.stops = []
        self.energies = []
        self.span = None
        self.nevents = None
    def __str__(self):
        s = '# %s(%s) %s | %s %d-%d\n'%(os.path.basename(__file__),version,' '.join(sys.argv[1:]),timestamp,self.runmin,self.runmax)
        return s + '0 0 0 %.2f %.2f %.5f'%(self.slope, self.offset, self.atten)
    def pretty_minutes(self):
        if self.minutes() is not None:
            return '%5.1f' % self.minutes()
        else:
            return '  ?  '
    def minutes(self):
        if self.span is not None:
            return (self.span[1]-self.span[0]).seconds/60
        return None
    def pretty(self):
        return 'slope=%6.1f atten=%8.5f offset=%6.1f+/-%.1f'%(self.slope, self.atten, self.offset, self.offset_rms)
    def save(self):
        self.filename = '%s/fcup-%d-%d.txt'%(out_dir,self.runmin,self.runmax)
        with open(self.filename,'w') as f:
            f.write(str(self))
    def get_cmd(self):
        return 'ccdb -c $CCDB_CONNECTION add -r %d-%d %s'%(self.runmin,self.runmax,os.path.basename(self.filename))
    def set_atten(self):
        if len(self.stops)>0 and len(self.energies)>0:
            if self.stops[0] < stopper_threshold:
                self.atten = 1.0
            elif self.runmin>=12444 and self.runmin<=12853:
                # fix bad beam energy from MCC:
                self.atten = 9.6930
            elif self.runmin>=18305 and self.runmin<=19131:
                # RG-D with Faraday cup issues:
                self.atten = 5.79985
            else:
                for e,a in attenuations.items():
                    if math.fabs(e-self.energies[0]) < energy_tolerance_MeV:
                        self.atten = a
                        return
                print('ERROR:  Unknown beam energy:  %.2f'%self.energies[0])
    def check(self):
        if len(self.energies) > 1:
            print('ERROR:  found multiple beam energies for %d:  %s'%(self.runmin,' '.join([str(x) for x in self.energies])))
        if len(self.stops) > 1:
            print('ERROR:  found multiple beam stopper positions for %d:  %s'%(self.runmin,' '.join([str(x) for x in self.stops])))
        if self.noffsets < 5:
            print('ERROR:  only %d points found for fcup offset for %d-%d.'%(self.noffsets,self.runmin,self.runmax))
        elif self.noffsets < 10:
            print('WARNING:  only %d points found for fcup offset for %d-%d.'%(self.noffsets,self.runmin,self.runmax))
    def ignore(self, min_events=-1, min_minutes=-1):
        if min_minutes>0 and self.minutes() is not None and self.minutes()<min_minutes:
            return True
        if min_events>0 and self.nevents is not None and self.nevents<min_events:
            return True
        return False
    def fatal(self):
        return len(self.stops)>1 or len(self.energies)>1
    def good(self):
        return self.offset is not None and self.atten is not None and not self.fatal()

#
# Retrieve Mya data for one PV and return a pandas dataframe:
#
def get_mya(pv, alias, args):
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
    start = time.perf_counter()
    session.mount(url, HTTPAdapter(max_retries=retries))
    result = session.get(url, timeout=1.0, verify=False)
    df = pandas.DataFrame(result.json().get('data'))
    df.rename(columns={'d':'t', 'v':alias}, inplace=True)
    if args.v>0:
        print('Got %d points from Mya for %s in %.1f seconds.'
            %(len(df.index), pv, time.perf_counter()-start))
        if args.v>3:
            with pandas.option_context('display.max_rows', None):
                print(df)
        elif args.v>1:
            print(df)
    return df

#
# Calculate Faraday cup offset, collect energy/stopper values:
#
def analyze(df, runmin, runmax, args):
    start_time = None
    offsets,fcups = [],[]
    if args.v>2:
        print(df.to_string())
    for x in df.iterrows():
        if start_time is not None:
            if not math.isnan(x[1].fcup) and x[1].fcup<fcup_maximum_offset:
                # early time veto:
                if x[1].t > start_time + 1000*bpm_veto_seconds[0]:
                    fcups.append((x[1].t, x[1].fcup))
        if not math.isnan(x[1].bpm):
            if x[1].bpm < bpm_veto_nA:
                # start the time window:
                if start_time is None:
                    start_time = x[1].t
                    fcups = []
            elif start_time is not None:
                # end the time window:
                start_time = None
                for k,v in fcups:
                    # late time veto:
                    if k < x[1].t - 1000*bpm_veto_seconds[1]:
                        offsets.append(v)
    # allow single-sided veto at end of run:
    if start_time is not None:
        offsets.extend([x[1] for x in fcups])
    ret = FcupTable(runmin, runmax)
    ret.noffsets = len(offsets)
    ret.energies = list(set(list(df[df.energy.notnull()].energy)))
    ret.stops = list(set(list(df[df.stop.notnull()].stop)))
    for i in range(len(ret.stops)-1,0,-1):
        if math.fabs(ret.stops[i]-ret.stops[i-1]) < stopper_deadband:
            ret.stops.pop(i)
    ret.nevents = args.db.get_event_count(runmin)
    if len(offsets) > 0:
        import functools
        if args.v>1:
            print('Offsets:  '+' '.join([str(x) for x in offsets]))
        ret.offset = functools.reduce(lambda x,y: x+y, offsets) / len(offsets)
        ret.offset_rms = math.sqrt(sum([ math.pow(x-ret.offset,2) for x in offsets]) / len(offsets))
    return ret

#
# Spawn a Mya query for each PV, return analyzed FcupTable:
#
def process(args, runmin, runmax):
    ret = FcupTable(runmin, runmax)
    span = args.db.get_time_span(runmin, runmax, args.R)
    ret.span = span
    args.start = span[0].strftime('%Y-%m-%dT%H:%M:%S')
    args.end = span[1].strftime('%Y-%m-%dT%H:%M:%S')
    dfs = []
    if args.v>1:
        print('Using Mya date range:  %s (%d) -> %s (%d)'%(args.start,runmin,args.start,runmax))
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for pv,alias in pv_names.items():
            if args.v>0:
                print('Reading %s from Mya ...'%pv)
            futures.append(executor.submit(get_mya,pv,alias,args))
        for f in futures:
            concurrent.futures.wait([f])
            if f.exception() is not None:
                print(f.exception())
                sys.exit(222)
            dfs.append(f.result())
    if max([ len(x.index) for x in dfs]) <= 2:
        print('ERROR:  no data found for %d-%d.'%(runmin,runmax))
        return ret
    import pandas
    df = pandas.concat(dfs).sort_values('t')
    if args.v>0:
        print('Analyzing data ...')
        if args.v>1:
            print(df)
    start = time.perf_counter()
    ret = analyze(df, runmin, runmax, args)
    ret.span = span
    ret.set_atten()
    ret.check()
    if args.v>0:
        print('Analyzing data took %.1f seconds.'%(time.perf_counter()-start))
        print('Found %d fcup offset points with an average of %s.'%(ret.noffsets,str(ret.offset)))
        if ret.good():
            print(ret)
    return ret

#
# Plot stuff from the generated "view" file:
#
def plot(path):
    import pandas as pd
    data = pd.read_csv(path,sep='\s+',header=None)
    data = pd.DataFrame(data)
    import matplotlib.pyplot as plt
    fig, (ax1,ax2) = plt.subplots(1,2)
    fig.suptitle('Faraday Cup Calibrations')
    ax1.set_xlabel('Run Number')
    ax2.set_xlabel('Run Number')
    ax1.set_ylabel('Faraday Cup Offset  (Hz)')
    ax2.set_ylabel('Faraday Cup Attenuation')
    ax1.errorbar(data[0], data[2], yerr=data[3], fmt='r',marker='.',linestyle='')
    ax2.plot(data[0], data[4],'r',marker='.',linestyle='')
    print('Close plot window to quit.')
    plt.show()

#
# Print information, save tables for uploading to CCDB, generate "view" file:
#
def closeout(runs, args):
    sep = '\n'+':'*40
    ngood = len(list(filter(lambda x : x[1].good(), runs)))
    nignore = len(list(filter(lambda x : x[1].ignore(args.N,args.M), runs)))
    nbad = len(list(filter(lambda x : not x[1].ignore(args.N,args.M) and not x[1].good(), runs)))
    if ngood > 0:
        print(sep+'\n: Runs Calibrated (%d)'%ngood+sep)
        [ print(r[0],':',r[1].pretty()) for r in filter(lambda x : x[1].good(), runs) ]
        if not args.d:
            print(sep+'\n: To Upload'+sep)
            print('1. set CCDB_CONNECTION for clas12writer')
            print('2. cd %s\n3. chmod +x upload\n4. ./upload'%out_dir)
    if nignore > 0:
        print(sep+'\n: Runs Ignored (%d)'%nignore+sep)
        for r in filter(lambda x : x[1].ignore(args.N,args.M), runs):
            print(r[0],'[%s minutes, %s events]'%(r[1].pretty_minutes(),str(args.db.pretty_event_count(r[0]))),
                'https://clasweb.jlab.org/rcdb/runs/info/'+r[0].split('-').pop(0))
    if nbad > 0:
        print(sep+'\n: Runs with Errors (%d)'%nbad+sep)
        for r in filter(lambda x : not x[1].ignore(args.N,args.M) and not x[1].good(), runs):
            print(r[0],'[%s minutes, %s events, %d stops, %d energies]'%(r[1].pretty_minutes(),str(args.db.pretty_event_count(r[0])),len(r[1].stops),len(r[1].energies)),
                'https://clasweb.jlab.org/rcdb/runs/info/'+r[0].split('-').pop(0))
    if not args.d:
        print('\nLogs saved to '+tee.name)
        if ngood > 0:
            os.makedirs(out_dir)
            # write the CCDB tables and script:
            with open('%s/upload'%out_dir,'w') as f:
                for run in filter(lambda x : x[1].good(), runs):
                    run[1].save()
                    f.write(run[1].get_cmd()+'\n')
            # write the view data file:
            with open('%s/view'%out_dir,'w') as f:
                for run in filter(lambda x : x[1].good(), runs):
                    f.write('%d %.2f %.2f %.2f %.5f\n'%(run[1].runmin,run[1].slope,run[1].offset,run[1].offset_rms,run[1].atten))
            print('CCDB tables written to %s'%out_dir)
            print('Table for plotting written to %s/view\n'%out_dir)
            if args.g:
                # plot the results:
                plot('%s/view'%out_dir)

if __name__ == '__main__':

    cli = argparse.ArgumentParser(description='Calibrate Faraday cup offset and attenuation for CCDB.',epilog='For details, see https://clasweb.jlab.org/wiki/index.php/CLAS12_Faraday_Cup_Calibration_Procedure.  Note, after a year or two, EPICS data are moved to the Mya "history" deployment and may require using the -m option.  Example usage:  "fcup-calib.py -m history 17100,17101"') 
    cli.add_argument('runs', help='run range or list, e.g., 100-200 or 1,4,7 or 1 4 7', nargs='*')
    cli.add_argument('-d', help='dry run, no output files', default=False, action='store_true')
    cli.add_argument('-v', help='increase verbosity', default=0, action='count')
    cli.add_argument('-g', help='graphics mode (optionally, specify path to previously generated view file)', metavar='path', default=False, const=True, nargs='?')
    cli.add_argument('-R', help='ignore missing times in RCDB (use beginning/end of next/previous run instead, when necesary)', default=0, const=1, action='store_const')
    cli.add_argument('-N', help='ignore runs with fewer events than this', metavar='events', default=-1, type=int)
    cli.add_argument('-M', help='ignore runs lasting fewer minutes than this', metavar='minutes', default=-1, type=float)
    cli.add_argument('-m', help='Mya deployment (default=ops)', default='ops', choices=['ops','history'])
    cli.add_argument('-s', help='single calculation over all runs', default=False, action='store_true')
    args = cli.parse_args(sys.argv[1:])

    if isinstance(args.g, str):
        plot(args.g)
        sys.exit(1)

    if len(args.runs) == 0:
        cli.error('runs argument is required')

    if not args.d:
        tee = Tee('./fcup-calib_%s.log'%timestamp.replace(' ','_').replace('/','-'),'w')

    try:
        if args.runs[0].isdigit():
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
        cli.error('invalid "runs" argument:  '+str(args.runs))

    import atexit
    args.db = RCDB()
    atexit.register(args.db.cleanup)

    runs = []

    if args.s:
        # single calibration over inclusive, full time range:
        runs.append(('%s-%s'%(args.min,args.max), process(args, args.min, args.max)))
    elif args.runs:
        # one calibration per run from user-specified list:
        for run in args.runs:
            runs.append((str(run), process(args, run, run))) 
    else:
        # one calibration per run in RCDB: 
        run = args.min
        while run <= args.max:
            runs.append((str(run), process(args, run, run)))
            run = args.db.db.get_next_run(run).number

    closeout(runs, args)

