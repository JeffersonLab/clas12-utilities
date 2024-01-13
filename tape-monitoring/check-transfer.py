#!/usr/bin/env python3
import os
import sys
import glob
import logging
import datetime
import argparse
import rcdb

cli = argparse.ArgumentParser(description='Check for missing data on tape for recent runs in RCDB.',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
cli.add_argument('path', help='path on tape to search, e.g. /mss/clas12/rg-m/data')
cli.add_argument('-e', metavar='#', help='minimum hours since run start time for existence', type=float, default=4)
cli.add_argument('-c', metavar='#', help='minimum hours since run end time for completion', type=float, default=8)
cli.add_argument('-n', metavar='#', help='mininum number of events per run', type=int, default=1e5)
cli.add_argument('-f', metavar='#', help='minimum number of files per run', type=int, default=5)
cli.add_argument('-m', metavar='#', help='minimum run number to consider', type=int, default=0)
cli.add_argument('-d', metavar='#', help='number of days to look back in RCDB', type=float, default=5)
cli.add_argument('-r', metavar='URL', help='RCDB database connection string', type=str, default='mysql://rcdb@clasdb.jlab.org/rcdb')
cli.add_argument('-v', help='verbose mode, else only print failures', default=False, action='store_true')

args = cli.parse_args(sys.argv[1:])

if args.v:
  logging.basicConfig(level=logging.INFO,format='%(levelname)-9s: %(message)s')
else:
  logging.basicConfig(level=logging.CRITICAL,format='%(levelname)-9s: %(message)s')

logger = logging.getLogger()

if not os.path.isdir(args.path):
  logger.critical('Invalid path:  '+args.path)
  sys.exit(999)

cached_dirs = glob.glob(args.path+'/*')

db = rcdb.RCDBProvider(args.r)

run = 1e9

error_runs = []

while True:

  run = db.get_prev_run(run)

  try:
    try:
      run_start_time = db.get_condition(run, 'run_start_time').value
      age_hours_start = (datetime.datetime.now() - run_start_time).total_seconds() / 60 / 60
      event_count = db.get_condition(run, 'event_count').value
      evio_files_count = db.get_condition(run, 'evio_files_count').value
    except (AttributeError,TypeError):
      logger.warning('Run %d ignored due to its invalid RCDB parameters.'%run.number)
      continue
    if run.number < args.m:
      break
  except (AttributeError,TypeError):
    logger.warning('Run %s ignored due to its invalid RCDB parameters.'%run)
    continue

  try:
    run_end_time = db.get_condition(run, 'run_end_time').value
    age_hours_end = (datetime.datetime.now() - run_end_time).total_seconds() / 60 / 60
  except AttributeError:
    run_end_time = None
    age_hours_end = None

  if event_count < args.n:
    logger.warning('Run %d ignored due to small number of events.'%run.number)
    continue

  if evio_files_count < args.f:
    logger.warning('Run %d ignored due to small number of files.'%run.number)
    continue

  if age_hours_start < args.e:
    logger.warning('Run %d ignored due to start time less than %.1f hours ago.'%(run.number,args.e))
    continue

  run_dir = None
  for d in cached_dirs:
    if os.path.isdir(d) and d.endswith(str('%.6d'%run.number)):
      run_dir = d
      break

  if run_dir is None:
    logger.critical('Run %d started more than %.1f hours ago in RCDB but missing /mss directory.'%(run.number,args.e))
    error_runs.append(run.number)
    continue

  if age_hours_end is None:
    logger.info('Run %d ignored due to missing end time in RCDB'%run.number)
    continue

  if age_hours_end > args.c:
    if len(glob.glob(d+'/*')) < evio_files_count:
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

