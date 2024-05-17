#!/usr/bin/env python3
import os
import sys
import math
import time
import datetime

# FIXME:  too much noise from sqlalchemy to use logging module

version = 'v1.0'
timestamp = datetime.datetime.now().strftime('%y/%m/%d %H:%M:%S')
pv_names = {'scalerS2b':'fcup','beam_stop':'stop','IPM2C21A':'bpm','MBSY2C_energy':'energy'}

# Beam current veto parameters:
bpm_veto_nA = 0.1
bpm_veto_seconds = [10.0,10.0]

# Tolerance for choosing stopper attenuation:
energy_tolerance_MeV = 10.0

# Position threshold for beam stopper in/out: 
stopper_threshold = 10.0

# Tolerance for stopper changes:
stopper_deadband = 1.0

# Ignore any readings above this:
fcup_maximum_offset = 2000

# Minimum number of offset readings required:
minimum_offsets = 5

# Beam stopper attenuation:
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
     6394 :14.2513,
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
            print('ERROR:    Could not connect to RCDB at '+self.url)
            sys.exit(1)
    def get_condition(self, run, name):
        try:
            return self.db.get_condition(run, name).value
        except AttributeError:
            return None
    def pretty_event_count(self, run):
        n = self.get_condition(run, 'event_count')
        if n is not None:
            return '%7.1e'%n
        return '    ?  '
    def get_start_time(self, run, expand):
        r = int(run)
        for i in range(expand+1):
            c = self.get_condition(r, ['run_start_time','run_end_time'][i%2])
            if c is not None:
                return c
            if i%2 == 0 and i<expand:
                print('WARNING:  Using time from %d\'s previous run'%int(r))
                r = self.db.get_prev_run(r).number
        return None
    def get_end_time(self, run, expand):
        r = int(run)
        for i in range(expand+1):
            c = self.get_condition(r, ['run_end_time','run_start_time'][i%2])
            if c is not None:
                return c
            if i%2 == 0 and i<expand:
                print('WARNING:  Using time from %d\'s next run'%int(r))
                r = self.db.get_next_run(r).number
        return None
    def get_time_span(self, first_run, last_run, expand=0):
        start = self.get_start_time(first_run, expand)
        end = self.get_end_time(last_run, expand)
        if start is None or end is None:
            return None
        return start,end
    def cleanup(self):
        try:
            self.db.disconnect()
        except AttributeError:
            pass

#
# Convenience class for storing calibration results:
#
class FcupCalib:
    def __init__(self, runmin, runmax):
        self.runmin = runmin
        self.runmax = runmax
        self.runsrc = runmin
        self.slope = 906.2
        self.offset = None
        self.noffsets = 0
        self.offset_rms = None
        self.atten = None
        self.span = None
        self.nevents = None
        self.stops = []
        self.energies = []
    def minutes(self):
        if self.span is not None:
            return (self.span[1]-self.span[0]).seconds/60
        return None
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
                print('ERROR:    Unknown beam energy:  %.2f for run %s'%(self.energies[0],str(self.runmin)))
    def check(self):
        if len(self.energies) > 1:
            print('ERROR:    Found multiple beam energies for %d:  %s'%(self.runmin,' '.join([str(x) for x in self.energies])))
        if len(self.stops) > 1:
            print('ERROR:    Found multiple beam stopper positions for %d:  %s'%(self.runmin,' '.join([str(x) for x in self.stops])))
        if self.noffsets < minimum_offsets:
            print('ERROR:  Only %d points found for fcup offset for %d-%d.'%(self.noffsets,self.runmin,self.runmax))
    def ignore(self, min_events=-1, min_minutes=-1):
        if self.span is None and self.nevents is None:
            return True
        if min_minutes>0 and self.minutes() is not None and self.minutes()<min_minutes:
            return True
        if min_events>0 and self.nevents is not None and self.nevents<min_events:
            return True
        return False
    def fatal(self):
        return len(self.stops)>1 or len(self.energies)>1 or self.atten is None
    def good(self):
        return not self.fatal() and self.offset is not None and self.atten is not None

#
# Convenience class for CCDB table:
#
class FcupTable(FcupCalib):
    table_name = '/runcontrol/fcup'
    def __init__(self, runmin, runmax):
        super().__init__(runmin, runmax)
        self.mother = None
    def __str__(self):
        s = '# %s(%s)\n'%(os.path.basename(__file__),version)
        return s + '0 0 0 %.2f %.2f %.5f'%(self.slope, self.offset, self.atten)
    def pretty_minutes(self):
        if self.minutes() is not None:
            return '%5.1f' % self.minutes()
        else:
            return '  ?  '
    def pretty(self):
        return 'slope=%6.1f atten=%8.5f offset=%6.1f+/-%.1f'%(self.slope, self.atten, self.offset, self.offset_rms)
    def save(self, out_dir):
        self.filename = '%s/fcup-%d-%d.txt'%(out_dir,self.runmin,self.runmax)
        with open(self.filename,'w') as f:
            f.write(str(self))
    def cmd(self):
        return 'ccdb -c $CCDB_CONNECTION add %s -r %d-%d %s'%(FcupTable.table_name,self.runmin,self.runmax,os.path.basename(self.filename))
    def inherit(self, other):
        if other.good() and not self.fatal():
            if self.noffsets < minimum_offsets:
                if self.atten == other.atten:
                    other.runmin = min(other.runmin,self.runmin)
                    other.runmax = max(other.runmax,self.runmax)
                    self.mother = other
                    return True
        return False

#
# Retrieve Mya data for one PV and return a pandas dataframe:
#
def get_mya(pv, alias, args):
    url = 'https://epicsweb.jlab.org/myquery/interval?p=1&a=1&d=1'
    url += '&c=%s&m=%s&b=%s&e=%s'%(pv,args.m,args.start,args.end)
    if args.v>2:
        print('INFO:     ',url)
    import requests
    from requests.adapters import HTTPAdapter,Retry
    import pandas
    requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
    retries = Retry(total=10, backoff_factor=0.1, status_forcelist=[500,502,503,504])
    session = requests.Session()
    start = time.perf_counter()
    session.mount(url, HTTPAdapter(max_retries=retries))
    result = session.get(url, timeout=1.0, verify=False)
    df = pandas.DataFrame(result.json().get('data'))
    df.rename(columns={'d':'t', 'v':alias}, inplace=True)
    if args.v>0:
        print('INFO:     Got %d points from Mya for %s in %.1f seconds.'
            %(len(df.index), pv, time.perf_counter()-start))
        if args.v>3:
            with pandas.option_context('display.max_rows', None):
                print(df)
        elif args.v>1:
            print(df)
    return df

#
# Apply BPM veto, return Faraday cup offset readings:
#
def get_offsets(df):
    start_time,offsets,fcups = None,[],[]
    for x in df.iterrows():
        if start_time is not None:
            if not math.isnan(x[1].fcup) and x[1].fcup<fcup_maximum_offset:
                # Early time veto:
                if x[1].t > start_time + 1000*bpm_veto_seconds[0]:
                    fcups.append((x[1].t, x[1].fcup))
        if not math.isnan(x[1].bpm):
            if x[1].bpm < bpm_veto_nA:
                # Start the time window:
                if start_time is None:
                    start_time = x[1].t
                    fcups = []
            elif start_time is not None:
                # End the time window:
                start_time = None
                for k,v in fcups:
                    # Late time veto:
                    if k < x[1].t - 1000*bpm_veto_seconds[1]:
                        offsets.append(v)
    # Allow single-sided veto at end of run:
    if start_time is not None:
        offsets.extend([x[1] for x in fcups])
    return offsets

#
# Calculate calibration parameters, return an FcupTable:
#
def analyze(df, runmin, runmax, args):
    ret = FcupTable(runmin, runmax)
    # Store lists of non-null uniques:
    ret.energies = list(set(list(df[df.energy.notnull()].energy)))
    ret.stops = list(set(list(df[df.stop.notnull()].stop)))
    # Remove stopper positions within the deadband:
    for i in range(len(ret.stops)-1,0,-1):
        if math.fabs(ret.stops[i]-ret.stops[i-1]) < stopper_deadband:
            ret.stops.pop(i)
    # Fatal issues, multiple energy/stopper values, abort:
    #if len(ret.energies) > 1 or len(ret.stops) > 1:
    #    return ret
    # Calculate the average offset and its RMS:
    offsets = get_offsets(df)
    ret.noffsets = len(offsets)
    import numpy as np
    import matplotlib.pyplot as plt
    if args.v>1 and len(offsets)>0:
        print('INFO:     Offsets:  '+' '.join([str(x) for x in offsets]))
    if len(offsets) >= minimum_offsets:
        import functools
        ret.histogram = np.histogram(offsets, bins=int((max(offsets)-min(offsets))))
        ret.offset = functools.reduce(lambda x,y: x+y, offsets) / len(offsets)
        ret.offset_rms = math.sqrt(sum([ math.pow(x-ret.offset,2) for x in offsets]) / len(offsets))
    # Determine stopper attenuation and others:
    ret.set_atten()
    ret.nevents = args.db.get_condition(runmin,'event_count')
    ret.check()
    return ret

#
# Spawn a Mya query for each PV, analyze it, and return an FcupTable:
#
def process(args, runmin, runmax):
    # Determine time span for Mya queries:
    span = args.db.get_time_span(runmin, runmax, args.R)
    if span is None:
        return FcupTable(runmin,runmax)
    args.start = span[0].strftime('%Y-%m-%dT%H:%M:%S')
    args.end = span[1].strftime('%Y-%m-%dT%H:%M:%S')
    if args.v>0:
        print('INFO:     Using Mya date range:  %s (%d) -> %s (%d)'%(args.start,runmin,args.end,runmax))
    # Spawn one thread per Mya query:
    dfs = []
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for pv,alias in pv_names.items():
            if args.v>1:
                print('INFO:     Reading %s from Mya ...'%pv)
            futures.append(executor.submit(get_mya,pv,alias,args))
        for f in futures:
            concurrent.futures.wait([f])
            if f.exception() is not None:
                print(f.exception())
                sys.exit(222)
            dfs.append(f.result())
    if max([ len(x.index) for x in dfs]) <= 2:
        print('ERROR:    no data found for %d-%d.'%(runmin,runmax))
        return FcupTable(runmin,runmax)
    # Merge results into one dataframe and analyze it:
    start = time.perf_counter()
    import pandas
    df = pandas.concat(dfs).sort_values('t')
    if args.v>0:
        if args.v>2:
            print(df.to_string())
        elif args.v>1:
            print(df)
    ret = analyze(df, runmin, runmax, args)
    ret.span = span
    if args.v > 0:
        print('INFO:     Analyzing data for %s-%s took %.1f seconds.'%(str(runmin),str(runmax),time.perf_counter()-start))
        if ret.offset is not None:
            print('INFO:     Found %d fcup offset points with an average of %s.'%(ret.noffsets,str(ret.offset)))
        if args.v > 1 and ret.good():
            print(ret)
    return ret

def plot_details(runs):
    import matplotlib.pyplot as plt
    ncol,nrow = 4,6
    for i,run in enumerate(good):
        if i%(ncol*nrow) == 0:
            fig, ax = plt.subplots(n,n)
        if i==len(good)-1 or i%(ncol*nrow)==ncol*nrow-1:
            plt.savefig(output
        y = [ sum(run[1].histogram[0]) * gauss(x,run[1].offset,run[1].offset_rms) for x in run[1].histogram[1] ]
        ax[int(i%n)][int(i/n)].hist(run[1].histogram[1][:-1], run[1].histogram[1], weights=run[1].histogram[0])
        ax[int(i%n)][int(i/n)].plot(run[1].histogram[1], y, '-', linewidth=2)
    plt.show()

#
# Plot stuff from the generated "view" file:
#
def plot(path, output=None, batch=False):
    try:
        import pandas as pd
        import numpy
        data = pd.read_csv(path,sep='\s+',header=None)
        data = pd.DataFrame(data)
        import matplotlib.pyplot as plt
        fig, (ax1,ax2) = plt.subplots(1,2,figsize=(12,4))
        fig.suptitle('Faraday Cup Calibrations')
        ax1.set_xlabel('Run Number')
        ax2.set_xlabel('Run Number')
        ax1.set_ylabel('Faraday Cup Offset  (Hz)')
        ax2.set_ylabel('Faraday Cup Attenuation')
        x = [ (row[1][1]+row[1][0])/2 for row in data.iterrows() ]
        ex = [ (row[1][1]-row[1][0])/2+0.5 for row in data.iterrows() ]
        ax1.errorbar(numpy.array(x), numpy.array(data[3]), yerr=numpy.array(data[4]), xerr=ex, fmt='r',marker='.',linestyle='')
        ax2.plot(numpy.array(x), numpy.array(data[5]),'r',marker='.',linestyle='')
        if output:
            for x in ['pdf','png','svg']:
                plt.savefig(output+'.'+x, format=x)
                print('INFO:     Saved image to '+output+'.'+x)
        if not batch:
            print('Close plot window to quit.')
            plt.show()
    except (FileNotFoundError,TypeError,IsADirectoryError,pd.errors.ParserError) as e:
        print(e,'\nInvalid view file:  '+path)
    except KeyboardInterrupt:
        pass

#
# For runs with insufficient measurements, try to inherit from a neighboring run:
# If a fatal run is transversed, do not inherit in that direction.
#
def merge_runs(runs, expand):
    for i,(run,data) in enumerate(runs):
        run = int(run)
        fatal = {-1:False,1:False}
        for j in range(1,expand+1):
            if not fatal[-1] and i-j >= 0 and run-int(runs[i-1][0]) <= expand:
                if data.inherit(runs[i-j][1]):
                    break
                elif runs[i-j][1].fatal():
                    fatal[-1] = True
            if not fatal[1] and i+j < len(runs) and int(runs[i+1][0])-run <= expand:
                if data.inherit(runs[i+j][1]):
                    break
                elif runs[i+j][1].fatal():
                    fatal[1] = True

def gauss(x,mean,sigma):
    return 1/sigma/math.sqrt(2*math.pi)*math.exp( -math.pow((x-mean)/sigma,2)/2 )
#
# Print a bunch of info, save tables for uploading to CCDB, generate "view" file:
#
def closeout(runs, args):
    sep = '\n'+':'*40
    good =   list(filter(lambda x : x[1].good(), runs))
    bad =    list(filter(lambda x : not x[1].ignore(args.N,args.M) and not x[1].good() and not x[1].mother, runs))
    ignore = list(filter(lambda x : x[1].ignore(args.N,args.M) and not x[1].good() and not x[1].mother, runs))
    inherit = list(filter(lambda x : x[1].mother, runs))
    if len(inherit) > 0:
        print(sep+'\n: Runs Inheriting (%d)'%len(inherit)+sep)
        [ print(r[0],' <--- ',r[1].mother.runsrc) for r in inherit ]
    if len(good) > 0:
        print(sep+'\n: Runs Calibrated (%d)'%len(good)+sep)
        [ print(r[0],':',r[1].pretty()) for r in good ]
        if not args.d:
            print(sep+'\n: To Upload'+sep)
            print('1. set CCDB_CONNECTION for clas12writer')
            print('2. cd %s\n3. chmod +x upload\n4. ./upload'%args.o)
    if len(ignore) > 0:
        print(sep+'\n: Runs Ignored (%d)'%len(ignore)+sep)
        for r in ignore:
            print(r[0],'[%s minutes, %s events]'%(r[1].pretty_minutes(),str(args.db.pretty_event_count(r[0]))),
                'https://clasweb.jlab.org/rcdb/runs/info/'+r[0].split('-').pop(0))
    if len(bad) > 0:
        print(sep+'\n: Runs with Errors (%d)'%len(bad)+sep)
        for r in bad:
            if args.s:
                print(r[0],'[%d stops, %d energies]'%(len(r[1].stops),len(r[1].energies)),
                    'https://clasweb.jlab.org/rcdb/runs/info/'+r[0].split('-').pop(0))
            else:
                print(r[0],'[%s minutes, %s events, %d stops, %d energies]'%(r[1].pretty_minutes(),str(args.db.pretty_event_count(r[0])),len(r[1].stops),len(r[1].energies)),
                    'https://clasweb.jlab.org/rcdb/runs/info/'+r[0].split('-').pop(0))
    if args.u:
        import matplotlib.pyplot as plt
        n = math.sqrt(len(good))
        fig, axes = plt.subplots(n,n)
        for i,run in enumerate(good):
            if i > n*n-1:
                break
            y = [ sum(run[1].histogram[0]) * gauss(x,run[1].offset,run[1].offset_rms) for x in run[1].histogram[1] ]
            axes[int(i%n)][int(i/n)].hist(run[1].histogram[1][:-1], run[1].histogram[1], weights=run[1].histogram[0])
            axes[int(i%n)][int(i/n)].plot(run[1].histogram[1], y, '-', linewidth=2)
        plt.show()

    if not args.d:
        print('\nINFO:     Logs saved to '+tee.name)
        if len(good) > 0:
            # Write the CCDB tables and script:
            with open('%s/upload'%args.o,'w') as f:
                for run in good:
                    run[1].save(args.o)
                    f.write(run[1].cmd()+'\n')
            # Write the view data file:
            with open('%s/view'%args.o,'w') as f:
                for run in good:
                    f.write('%d %d %.2f %.2f %.2f %.5f\n'%(run[1].runmin,run[1].runmax,run[1].slope,run[1].offset,run[1].offset_rms,run[1].atten))
            print('INFO:     CCDB tables written to %s'%args.o)
            print('INFO:     CCDB upload script written to %s/upload'%args.o)
            print('INFO:     Data for visualization written to %s/view'%args.o)
            if not args.s:
                plot('%s/view'%args.o, output='%s/fcup'%args.o, batch=args.b)

if __name__ == '__main__':

    import argparse
    cli = argparse.ArgumentParser(description='Calibrate Faraday cup offset and attenuation for CCDB.',epilog='For details, see https://clasweb.jlab.org/wiki/index.php/CLAS12_Faraday_Cup_Calibration_Procedure.  Note, after a year or two, EPICS data are moved to the Mya "history" deployment and may require using the -m option.  Example usage:  "fcup-calib.py -m history 17100,17101"') 
    cli.add_argument('runs', help='run range or list, e.g., 100-200 or 1,4,7 or 1 4 7', nargs='*')
    cli.add_argument('-N', help='ignore runs with fewer events than this (default: 10000)', metavar='events', default=10000, type=int)
    cli.add_argument('-M', help='ignore runs lasting fewer minutes than this (default: 5)', metavar='minutes', default=3, type=float)
    cli.add_argument('-I', help='inherit from neighbor up to this many runs away, if insufficient data (default: 5)', metavar='runs', default=5, type=int)
    cli.add_argument('-R', help='require valid times in RCDB (default: use start/end of next/previous run if necessary)', default=1, const=0, action='store_const')
    cli.add_argument('-d', help='dry run, no output files', default=False, action='store_true')
    cli.add_argument('-v', help='increase verbosity', default=0, action='count')
    cli.add_argument('-o', help='output directory', metavar='path', default='./fcup-calib_%s'%timestamp.replace(' ','_').replace('/','-'))
    cli.add_argument('-g', help='generate images from previously generated view file', metavar='path')
    cli.add_argument('-b', help='batch mode, no graphics', default=False, action='store_true')
    cli.add_argument('-m', help='Mya deployment (default: ops)', default='ops', choices=['ops','history'])
    cli.add_argument('-s', help='single calculation over all runs', default=False, action='store_true')
    cli.add_argument('-u', help='show histogram of offsets', default=False, action='store_true')
    args = cli.parse_args(sys.argv[1:])

    # User-supplied view file, just plot it and quit:
    if isinstance(args.g, str):
        plot(args.g, output='fcup-'+timestamp.replace(' ','_').replace('/','-'), batch=args.b)
        sys.exit(1)
    elif len(args.runs) == 0:
        cli.error('Runs argument is required')

    # Unless it's a dry-run, tee stdout/stderr to a log file:
    if not args.d:
        if os.path.exists(args.o):
            cli.error('Output directory already exists')
        os.makedirs(args.o)
        tee = Tee('%s/log'%args.o,'w')

    # Interpret the runs argument:
    try:
        # It's a space-separated list of runs:
        if len(args.runs)>1 or args.runs[0].isdigit():
            args.runs = sorted([ int(x) for x in args.runs ])
            args.min = args.runs[0]
            args.max = args.runs[len(args.runs)-1]
        # It's a comma-separated list of runs:
        elif ',' in args.runs[0]:
            args.runs = sorted([ int(x) for x in args.runs[0].split(',') ])
            args.min = args.runs[0]
            args.max = args.runs[len(args.runs)-1]
        # It's a dash-separated run range:
        elif '-' in args.runs[0]:
            args.min,args.max = [int(x) for x in args.runs[0].split('-')]
            args.runs = None
            if args.max < args.min:
                cli.error('Max is less than min')
        else:
            raise ValueError()
    except (ValueError,TypeError):
        cli.error('Invalid "runs" argument:  '+str(args.runs))

    # Initialize RCDB:
    import atexit
    args.db = RCDB()
    atexit.register(args.db.cleanup)

    runs = []

    # Single calibration over inclusive, full time range:
    if args.s:
        runs.append(('%s-%s'%(args.min,args.max), process(args, args.min, args.max)))

    # One calibration per run from user-specified list:
    elif args.runs:
        for run in args.runs:
            runs.append((str(run), process(args, run, run)))

    # One calibration per run in RCDB: 
    else:
        run = args.min
        while run <= args.max:
            runs.append((str(run), process(args, run, run)))
            run = args.db.db.get_next_run(run)
            if run is None:
                print('WARNING:  reached latest run in RCDB')
                break
            else:
                run = run.number

    if not args.s:
        merge_runs(runs, args.I)

    closeout(runs, args)

    if not args.s:
        plot_summary('%s/view'%args.o, output='%s/fcup'%args.o, batch=args.b)

