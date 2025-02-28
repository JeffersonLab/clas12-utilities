#!/usr/bin/env python3

import os
import sys
import socket
import datetime

sys.path.append(os.path.dirname(os.path.realpath(__file__))+'/..')

import condor.data
import condor.plot
import condor.table
import condor.command
from condor.cli import cli

args = cli.parse_args(sys.argv[1:])

if args.held + args.idle + args.running + args.completed > 1:
  cli.error('Only one of -held/idle/running/completed is allowed.')

if (bool(args.vacate>=0) + bool(args.tail is not None) + bool(args.cvmfs) + bool(args.json)) > 1:
  cli.error('Only one of -cvmfs/vacate/tail/json is allowed.')

if args.completed and args.hours <= 0 and not args.input:
  cli.error('-completed requires -hours is greater than zero or -input.')

if not args.input:
  if socket.gethostname() not in ['scosg2202.jlab.org']:
    cli.error('You must be on an OSG submit node unless using the -input option.')

if len(args.exit) > 0 and not args.parseexit:
  print('Enabling -parseexit to accommodate -exit.  This may be slow ....')
  args.parseexit = True

if args.plot and os.environ.get('DISPLAY') is None:
  cli.error('-plot requires graphics, but $DISPLAY is not set.')

if args.end is None:
  args.end = datetime.datetime.now()
else:
  try:
    args.end = datetime.datetime.strptime(args.end,'%Y/%m/%d_%H:%M:%S')
  except:
    try:
      args.end = datetime.datetime.strptime(args.end,'%Y/%m/%d')
    except:
      cli.error('Invalid date format for -end:  '+args.end)

if args.plot is not False:
  import ROOT

if args.input:
  condor.data.read(args)
else:
  condor.command.query(args)

if args.timeline:
  condor.data.timeline(args)
  sys.exit(0)

if args.json:
  condor.data.show()
  sys.exit(0)

if args.plot is not False:
  c = condor.plot.plot(args)
  if c is not None and args.plot is not True:
    c.SaveAs(args.plot)
    c = condor.plot.plot(args, 1)
    suffix = args.plot.split('.').pop()
    logscalename = ''.join(args.plot.split('.')[0:-1])+'-logscale.'+suffix
    c.SaveAs(logscalename)
  else:
    print('Done Plotting.  Press Return to close.')
    input()
  sys.exit(0)

for cid,job in condor.data.get_jobs(args):

  if args.hold:
    condor.command.hold_job(job)

  if args.vacate>0:
    if job.get('wallhr') is not None:
      if float(job.get('wallhr')) > args.vacate:
        if condor.data.job_states.get(job['JobStatus']) == 'R':
          condor.command.vacate(job)

  elif args.cvmfs:
    if not condor.data.check_cvmfs(job):
      if 'LastRemoteHost' in job:
        print(job.get('MATCH_GLIDEIN_Site')+' '+job['LastRemoteHost']+' '+cid)

  elif args.xrootd:
    if not condor.data.check_xrootd(job):
      if 'LastRemoteHost' in job:
        print(job.get('MATCH_GLIDEIN_Site')+' '+job['LastRemoteHost']+' '+cid)

  elif args.tail is not None:
    condor.table.tail_log(job, args.tail)

  else:
    condor.table.job_table.add_job(job)

if args.tail is None and not args.cvmfs:
  if len(condor.table.job_table.rows) > 0:
    if args.summary or args.sitesummary:
      if args.summary:
        print(condor.table.summary_table.add_jobs(condor.data.cluster_summary(args)))
      else:
        print(condor.table.site_table.add_jobs(condor.data.site_summary(args)))
    else:
      print(condor.table.job_table)
    if (args.held or args.idle) and args.parseexit:
      print(condor.data.exit_code_summary(args))
    if args.hours>0:
      print(condor.data.efficiency_summary())

