#!/usr/bin/env python3

import argparse
cli = argparse.ArgumentParser(description='Check for missing data on tape for recent runs in RCDB.',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
cli.add_argument('path', help='path on tape to search, e.g. /mss/clas12/rg-m/data')
cli.add_argument('-e', metavar='#', help='minimum hours since run start time for existence', type=float, default=4)
cli.add_argument('-c', metavar='#', help='minimum hours since run end time for completion', type=float, default=8)
cli.add_argument('-n', metavar='#', help='mininum number of events per run', type=int, default=1e5)
cli.add_argument('-f', metavar='#', help='minimum number of files per run', type=int, default=5)
cli.add_argument('-m', metavar='#', help='minimum run number to consider', type=int, default=0)
cli.add_argument('-d', metavar='#', help='number of days to look back in RCDB', type=float, default=5)
cli.add_argument('-i', metavar='RUN', help='run number to ignore, repeatable', type=int, default=[], action='append')
cli.add_argument('-C', metavar='URL', help='RCDB database connection string', type=str, default='mysql://rcdb@clasdb.jlab.org/rcdb')
cli.add_argument('-R', metavar='REGEX', help='regular expression for finding run number in directory names', type=str, default='.*(\d\d\d\d\d\d)$')
cli.add_argument('-v', help='verbose mode, else only print failures', default=False, action='store_true')

args = cli.parse_args()

import re
try:
    args.R = re.compile(args.R)
except re.error:
    cli.error('Invalid -R regular expression:  '+args.R)

import logging
if args.v:
    logging.basicConfig(level=logging.INFO,format='%(levelname)-9s: %(message)s')
else:
    logging.basicConfig(level=logging.CRITICAL,format='%(levelname)-9s: %(message)s')

logger = logging.getLogger()

import os,sys
if not os.path.isdir(args.path):
    logger.critical('Invalid path:  '+args.path)
    sys.exit(999)

import glob
cached_dirs = glob.glob(args.path+'/*')
cached_dirs = filter(lambda d: os.path.isdir(d) , cached_dirs)
cached_dirs = filter(lambda d: re.match(args.R,d) , cached_dirs)
cached_dirs = list(cached_dirs)

import rcdb,datetime
db = rcdb.RCDBProvider(args.C)
run = 1e9
error_runs = []

while True:

  run = db.get_prev_run(run)

  try:
      try:
          run_start_time = db.get_condition(run, 'run_start_time').value
          event_count = db.get_condition(run, 'event_count').value
          evio_files_count = db.get_condition(run, 'evio_files_count').value
          age_hours_start = (datetime.datetime.now() - run_start_time).total_seconds() / 60 / 60
      except (AttributeError,TypeError):
          logger.warning('Run %d ignored due to invalid RCDB parameters.'%run.number)
          continue
      if run.number < args.m:
          break
  except (AttributeError,TypeError):
      logger.warning('Run %s ignored due to invalid RCDB parameters.'%run)
      continue

  try:
      run_end_time = db.get_condition(run, 'run_end_time').value
      age_hours_end = (datetime.datetime.now() - run_end_time).total_seconds() / 60 / 60
  except AttributeError:
      run_end_time = None
      age_hours_end = None

  if run.number in args.i:
      logger.warning('Run %d ignored due to whitelisting.'%run.number)
      continue

  if event_count < args.n:
      logger.warning('Run %d ignored due to small number of events.'%run.number)
      continue

  if evio_files_count < args.f:
      logger.warning('Run %d ignored due to small number of files.'%run.number)
      continue

  if age_hours_start < args.e:
      logger.warning('Run %d ignored due to start time less than %.1f hours ago.'%(run.number,args.e))
      continue

  run_dir = list(filter(lambda d: re.match(args.R,d).group(1).lstrip('0')==str(run.number) , cached_dirs))

  if len(run_dir) == 0:
      logger.critical('Run %d started more than %.1f hours ago in RCDB but missing /mss directory.'%(run.number,args.e))
      error_runs.append(run.number)
      continue
  elif len(run_dir) > 1:
      logger.critical('Run %d has multiple /mss directories.'%(run.number))
      error_runs.append(run.number)
      continue

  run_dir = run_dir.pop(0)

  if age_hours_end is None:
      logger.info('Run %d ignored due to missing end time in RCDB'%run.number)
      continue

  if age_hours_end > args.c:
      if len(glob.glob(run_dir+'/*')) < evio_files_count:
          logger.critical('Run %d ended more than %.1f hours ago in RCDB but missing /mss files.'%(run.number,args.c))
          error_runs.append(run.number)
          continue
      else:
          logger.info('Run %d ran from %s to %s and complete at /mss.'%(run.number,run_start_time,run_end_time))

  else:
      logger.info('Run %d ignored due to end time less than %.1f hours ago.'%(run.number,args.c))

  if age_hours_start > args.d*24:
      break

sys.exit(len(error_runs))

