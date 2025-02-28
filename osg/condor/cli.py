###
### Command-line parser, serving also as a data structure for passing
### configuration between submodules.
###

import argparse
import condor.data

cli = argparse.ArgumentParser(description='Wrap condor_q and condor_history and add features for CLAS12.',
    epilog='''(1) Repeatable "limit" options are first OR\'d independently, then AND'd together, and if their
    argument is prefixed with a dash ("-"), it is a veto (overriding the \'OR\').  (2) For non-numeric arguments
    starting with a dash, use the "-opt=arg" format.  (3) Per-site wall-hour tallies ignore running jobs, unless
    -running is specified.  (4) Efficiencies and process wall hours are only calculated for completed jobs.  (5) Known exit codes are: '''
    +', '.join(['%d=%s'%(k,v) for k,v in condor.data.exit_codes.items()]))
cli.add_argument('-condor', default=[], metavar='#', action='append', type=int, help='limit by condor cluster id (repeatable)')
cli.add_argument('-gemc', default=[], metavar='#', action='append', type=int, help='limit by gemc submission id (repeatable)')
cli.add_argument('-user', default=[], action='append', type=str, help='limit by portal submitter\'s username (repeatable)')
cli.add_argument('-site', default=[], action='append', type=str, help='limit by site name, pattern matched (repeatable)')
cli.add_argument('-host', default=[], action='append', type=str, help='limit by host name, pattern matched (repeatable)')
cli.add_argument('-exit', default=[], metavar='#', action='append', type=int, help='limit by exit code (repeatable)')
cli.add_argument('-noexit', default=False, action='store_true', help='limit to jobs with no exit code')
cli.add_argument('-generator', default=[], action='append', type=str, help='limit by generator name (repeatable)')
cli.add_argument('-held', default=False, action='store_true', help='limit to jobs currently in held state')
cli.add_argument('-idle', default=False, action='store_true', help='limit to jobs currently in idle state')
cli.add_argument('-running', default=False, action='store_true', help='limit to jobs currently in running state')
cli.add_argument('-completed', default=False, action='store_true', help='limit to completed jobs')
cli.add_argument('-summary', default=False, action='store_true', help='tabulate by cluster id instead of per-job')
cli.add_argument('-sitesummary', default=False, action='store_true', help='tabulate by site instead of per-job')
cli.add_argument('-hours', default=0, metavar='#', type=float, help='look back # hours for completed jobs, reative to -end (default=0)')
cli.add_argument('-end', default=None, metavar='YYYY/MM/DD[_HH:MM:SS]', type=str, help='end date for look back for completed jobs (default=now)')
cli.add_argument('-tail', default=None, metavar='#', type=int, help='print last # lines of logs (negative=all, 0=filenames)')
cli.add_argument('-cvmfs', default=False, action='store_true', help='print hostnames from logs with CVMFS errors')
cli.add_argument('-xrootd', default=False, action='store_true', help='print hostnames from logs with XRootD errors')
cli.add_argument('-vacate', default=-1, metavar='#', type=float, help='vacate jobs with wall hours greater than #')
cli.add_argument('-hold', default=False, action='store_true', help='send matching jobs to hold state (be careful!!!)')
cli.add_argument('-json', default=False, action='store_true', help='print full condor data in JSON format')
cli.add_argument('-input', default=False, metavar='FILEPATH', type=str, help='read condor data from a JSON file instead of querying')
cli.add_argument('-timeline', default=False, action='store_true', help='publish results for timeline generation')
cli.add_argument('-perf', default=False, action='store_true', help='get more performance info (from logs, slow), e.g. sub-wall times, exit codes')
cli.add_argument('-plot', default=False, metavar='FILEPATH', const=True, nargs='?', help='generate plots (requires ROOT)')

