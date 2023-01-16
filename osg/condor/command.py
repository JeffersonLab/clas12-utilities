###
### Command wrappers for HTCondor that also update a temporary condor.data job cache
###

import subprocess
import json

import condor.data

def queue(constraints=[], opts=[]):
  '''Get the JSON from condor_q'''
  cmd = ['condor_q','gemc']
  cmd.extend(constraints)
  cmd.extend(opts)
  cmd.extend(['-nobatch','-json'])
  condor.data.add_json(cmd)

def history(args, constraints=[]):
  '''Get the JSON from condor_history'''
  start = args.end + datetime.timedelta(hours = -args.hours)
  start = str(int(start.timestamp()))
  cmd = ['condor_history','gemc']
  cmd.extend(constraints)
  cmd.extend(['-json','-since',"CompletionDate!=0&&CompletionDate<%s"%start])
  condor.data.add_json(cmd)

def query(args):
  '''Load data from condor_q and condor_history'''
  constraints = []
  for x in args.condor:
    if not str(x).startswith('-'):
      constraints.append(str(x))
  opts = []
  if args.held:
    opts.append('-hold')
  if args.running:
    opts.append('-run')
  if not args.completed or args.plot is not False:
    queue(constraints=constraints, opts=opts)
  if args.hours > 0:
    history(args, constraints=constraints)
  condor.data.munge(args)

def vacate(job):
  cmd = ['condor_vacate_job', '-fast', job.get('condorid')]
  response = None
  try:
    response = subprocess.check_output(cmd).decode('UTF-8').rstrip()
    if re.fullmatch('Job %s fast-vacated'%job.get('condorid'), response) is None:
      raise ValueError()
  except:
    print('ERROR running command "%s":\n%s'%(' '.join(cmd),response))
  print(str(job.get('MATCH_GLIDEIN_Site'))+' '+str(job.get('RemoteHost'))+' '+str(job.get('condorid')))

def hold(job):
  cmd = ['condor_hold', job.get('condorid')]
  response = None
  try:
    response = subprocess.check_output(cmd).decode('UTF-8').rstrip()
    print(response)
  except:
    print('ERROR running command "%s":\n%s'%(' '.join(cmd),response))

