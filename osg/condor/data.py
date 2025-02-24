###
### Utilities to store/manipulate/analyze a set of HTCondor jobs and their attributes
###

import os
import re
import sys
import stat
import json
import datetime
import subprocess
import collections

import condor.matching
import condor.util
import condor.table

json_format =  {'indent':2, 'separators':(',',': '), 'sort_keys':True}
log_regex = '/([a-z]+)/job_([0-9]+)/log/job\.([0-9]+)\.([0-9]+)\.'
job_states = {0:'U', 1:'I', 2:'R', 3:'X', 4:'C', 5:'H', 6:'E'}
job_counts = {'done':0, 'run':0, 'idle':0, 'held':0, 'other':0, 'total':0}
exit_codes = { 202:'cvmfs', 203:'generator', 211:'ls', 204:'gemc', 0:'success/unknown',
               205:'evio2hipo', 207:'recon-util', 208:'hipo-utils', 212:'xrootd'}
cvmfs_error_strings = [ 'Loaded environment state is inconsistent',
  'Command not found','Unable to access the Singularity image','CVMFS ERROR']
#  'No such file or directory', 'Transport endpoint is not connected',

job_tallies = {'goodwall':0, 'badwall':0, 'goodcpu':0, 'badcpu':0, 'goodattempts':0, 'badattempts':0, 'attempts':[]}
job_cache = collections.OrderedDict()

def get_jobs(args):
  cm = condor.matching.CondorMatchers(args)
  for condor_id,job in job_cache.items():
    if cm.matches(job):
      yield (condor_id, job)

def show():
  print(json.dumps(job_cache, **json_format))

def add_json(cmd):
  '''Add JSON condor data to local dictionary'''
  global job_cache
  response = None
  try:
    response = subprocess.check_output(cmd).decode('UTF-8')
    if len(response) > 0:
      for x in json.loads(response):
        if 'ClusterId' in x and 'ProcId' in x:
          job_cache['%d.%d'%(x['ClusterId'],x['ProcId'])] = x
        else:
          pass
  except:
    print('Error running command:  '+' '.join(cmd)+':')
    print(response)
    sys.exit(1)

def read(args):
  global job_cache
  data = json.load(open(args.input,'r'))
  if type(data) is list:
    for x in data:
      if 'ClusterId' in x and 'ProcId' in x:
        job_cache['%d.%d'%(x['ClusterId'],x['ProcId'])] = x
  elif type(data) is dict:
    job_cache = data
  else:
    raise TypeError()
  munge(args)

def munge(args):
  '''Assign custom parameters based on parsing some condor parameters'''
  for condor_id,job in job_cache.items():
    job.update({'user':None,'gemc':None,'host':None,'condor':None,'stderr':None,'stdout':None,'eff':None,'ceff':None})
    job['generator'] = get_generator(job)
    job['wallhr'] = calc_wallhr(job)
    job['condorid'] = '%d.%d'%(job['ClusterId'],job['ProcId'])
    job['gemcjob'] = '.'.join(job.get('Args').split()[0:2])
    # setup clas12 job ids and usernames:
    if 'UserLog' in job:
      m = re.search(log_regex, job['UserLog'])
      if m is not None:
        job['user'] = m.group(1)
        job['gemc'] = m.group(2)
        job['condor'] = m.group(3)+'.'+m.group(4)
        job['stderr'] = job['UserLog'][0:-4]+'.err'
        job['stdout'] = job['UserLog'][0:-4]+'.out'
        if condor_id != job['condor']:
          raise ValueError('condor ids do not match.')
    # trim hostnames to the important bit:
    if job.get('RemoteHost') is not None:
      job['host'] = job.get('RemoteHost').split('@').pop()
    if job.get('LastRemoteHost') is not None:
      job['LastRemoteHost'] = job.get('LastRemoteHost').split('@').pop().split('.').pop(0)
    # calculate cpu utilization for good, completed jobs:
    if job_states[job['JobStatus']] == 'C' and  float(job.get('wallhr')) > 0:
        job['eff'] = '%.2f'%(float(job.get('RemoteUserCpu')) / float(job.get('wallhr'))/60/60)
    # calculate cumulative cpu efficiency for all jobs:
    if job.get('CumulativeSlotTime') > 0:
      if job_states[job['JobStatus']] == 'C' or job_states[job['JobStatus']] == 'R':
        job['ceff'] = '%.2f'%(float(job.get('RemoteUserCpu'))/job.get('CumulativeSlotTime'))
      else:
        job['ceff'] = 0
    # get exit code from log files (since it's not always available from condor):
    if args.parseexit and job_states[job['JobStatus']] == 'H':
      job['ExitCode'] = get_exit_code(job)
    tally(job)

def tally(job):
  '''Increment total good/bad job counts and times'''
  global job_tallies
  x = job_tallies
  if job_states[job['JobStatus']] == 'C' or job_states[job['JobStatus']] == 'R':
    if job['NumJobStarts'] > 0:
      x['attempts'].append(job['NumJobStarts'])
    if job_states[job['JobStatus']] == 'C':
      x['goodattempts'] += 1
      x['goodwall'] += float(job['wallhr'])*60*60
      x['goodcpu'] += job['RemoteUserCpu']
    if job['NumJobStarts'] > 1:
      x['badattempts'] += job['NumJobStarts'] - 1
      x['badwall'] += job['CumulativeSlotTime'] - float(job['wallhr'])*60*60
      x['badcpu'] += job['CumulativeRemoteUserCpu'] - job['RemoteUserCpu']
  elif job['NumJobStarts'] > 0 and job_states[job['JobStatus']] != 'X':
      x['badattempts'] += job['NumJobStarts']
      x['badwall'] += job['CumulativeSlotTime']
      x['badcpu'] += job['CumulativeRemoteUserCpu']
  x['totalwall'] = x['badwall'] + x['goodwall']
  x['totalcpu'] = x['badcpu'] + x['goodcpu']

def calc_wallhr(job):
  '''Calculate the wall hours of the final, completed instance of a job,
  because it does not seem to be directly available from condor.  This may
  may be an overestimate of the job itself, depending on how start date
  and end date are triggered, but that's ok.'''
  ret = None
  if job_states[job['JobStatus']] == 'C' or job_states[job['JobStatus']] == 'R':
    start = job.get('JobCurrentStartDate')
    end = job.get('CompletionDate')
    if start is not None and start > 0:
      start = datetime.datetime.fromtimestamp(int(start))
      if end is not None and end > 0:
        end = datetime.datetime.fromtimestamp(int(end))
      else:
        end = datetime.datetime.now()
      ret = '%.2f' % ((end - start).total_seconds()/60/60)
  return ret

def get_status_key(job):
  d = {'H':'held','I':'idle','R':'run','C':'done'}
  return d.get(job_states[job['JobStatus']],'other')

def cluster_summary(args):
  '''Tally jobs by condor's ClusterId'''
  ret = collections.OrderedDict()
  for condor_id,job in get_jobs(args):
    cluster_id = condor_id.split('.').pop(0)
    if cluster_id not in ret:
      ret[cluster_id] = job.copy()
      ret[cluster_id].update(job_counts.copy())
      ret[cluster_id]['eff'] = []
      ret[cluster_id]['ceff'] = []
      ret[cluster_id]['att'] = []
      ret[cluster_id]['wallhr'] = []
    ret[cluster_id][get_status_key(job)] += 1
    ret[cluster_id]['done'] = ret[cluster_id]['TotalSubmitProcs']
    ret[cluster_id]['done'] -= ret[cluster_id]['held']
    ret[cluster_id]['done'] -= ret[cluster_id]['idle']
    ret[cluster_id]['done'] -= ret[cluster_id]['run']
    try:
      if job['NumJobStarts'] > 0:
        ret[cluster_id]['att'].append(job['NumJobStarts'])
      x = float(job['eff'])
      ret[cluster_id]['eff'].append(x)
      x = float(job['ceff'])
      ret[cluster_id]['ceff'].append(x)
    except:
      pass
    if args.running or job_states[job['JobStatus']] == 'C':
      try:
        x = float(job.get('wallhr'))
        ret[cluster_id]['wallhr'].append(x)
      except:
        pass
  for v in ret.values():
    v['eff'] = condor.table.average(v['eff'])
    v['ceff'] = condor.table.average(v['ceff'])
    v['att'] = condor.table.average(v['att'])
    v['ewallhr'] = condor.table.stddev(v['wallhr'])
    v['wallhr'] = condor.table.average(v['wallhr'])
  return ret

def site_summary(args):
  '''Tally jobs by site.  Note, including completed jobs
  here is only possible if condor_history is included.'''
  sites = collections.OrderedDict()
  for condor_id,job in get_jobs(args):
    site = job.get('MATCH_GLIDEIN_Site')
    if site not in sites:
      sites[site] = job.copy()
      sites[site].update(job_counts.copy())
      sites[site]['wallhr'] = []
    sites[site]['total'] += 1
    sites[site][get_status_key(job)] += 1
    if args.running or job_states[job['JobStatus']] == 'C':
      try:
        x = float(job.get('wallhr'))
        sites[site]['wallhr'].append(x)
      except:
        pass
  for site in sites.keys():
    sites[site]['ewallhr'] = condor.table.stddev(sites[site]['wallhr'])
    sites[site]['wallhr'] = condor.table.average(sites[site]['wallhr'])
    if args.hours <= 0:
      sites[site]['done'] = condor.table.null_field
  return condor.util.sort_dict(sites, 'total')

def exit_code_summary(args):
  x = {}
  for cid,job in get_jobs(args):
    if job.get('ExitCode') is not None:
      if job.get('ExitCode') not in x:
        x[job.get('ExitCode')] = 0
      x[job.get('ExitCode')] += 1
  tot = sum(x.values())
  ret = '\nExit Code Summary:\n'
  ret += '------------------------------------------------\n'
  ret += '\n'.join(['%4s  %8d %6.2f%%  %s'%(k,v,v/tot*100,exit_codes.get(k)) for k,v in x.items()])
  return ret + '\n'

def efficiency_summary():
  global job_tallies
  x = job_tallies
  ret = ''
  if len(x['attempts']) > 0:
    ret += '\nEfficiency Summary:\n'
    ret += '------------------------------------------------\n'
    ret += 'Number of Good Job Attempts:  %10d\n'%x['goodattempts']
    ret += 'Number of Bad Job Attempts:   %10d\n'%x['badattempts']
    ret += 'Average # of Job Attempts:    % 10.1f\n'%(sum(x['attempts'])/len(x['attempts']))
    ret += '------------------------------------------------\n'
    ret += 'Total Wall and Cpu Hours:   %.3e %.3e\n'%(x['totalwall'],x['totalcpu'])
    ret += 'Bad Wall and Cpu Hours:     %.3e %.3e\n'%(x['badwall'],x['badcpu'])
    ret += 'Good Wall and Cpu Hours:    %.3e %.3e\n'%(x['goodwall'],x['goodcpu'])
    ret += '------------------------------------------------\n'
    if x['goodwall'] > 0:
      ret += 'Cpu Utilization of Good Jobs:        %.1f%%\n'%(100*x['goodcpu']/x['goodwall'])
    if x['totalwall'] > 0:
      ret += 'Good Fraction of Wall Hours:         %.1f%%\n'%(100*x['goodwall']/x['totalwall'])
      ret += 'Total Efficiency:                    %.1f%%\n'%(100*x['goodcpu']/x['totalwall'])
    ret += '------------------------------------------------\n\n'
  return ret

def check_cvmfs(job):
  '''Return wether a CVMFS error is detected'''
  for line in condor.util.readlines_reverse(job.get('stdout'),20):
    for x in cvmfs_error_strings:
      if line.find(x) >= 0:
        return False
  return True

def check_xrootd(job):
  if job.get('ExitCode') is not None:
    if job.get('ExitCode') == 212:
      return False
  return True

def get_exit_code(job):
  '''Extract the exit code from the log file'''
  for line in condor.util.readlines_reverse(job.get('stderr'),3):
    cols = line.strip().split()
    if len(cols) == 2 and cols[0] == 'exit':
      try:
        return int(cols[1])
      except:
        pass
  return None

# cache generator names to only parse log once per cluster
generators = {}
def get_generator(job):
  if job.get('ClusterId') not in generators:
    generators['ClusterId'] = condor.table.null_field
    if job.get('UserLog') is not None:
      job_script = os.path.dirname(os.path.dirname(job.get('UserLog')))+'/nodeScript.sh'
      for line in condor.util.readlines(job_script):
        line = line.lower()
        m = re.search('events with generator (.*) with options', line)
        if m is not None:
          if m.group(1).startswith('clas12-'):
            generators['ClusterId'] = m.group(1)[7:]
          else:
            generators['ClusterId'] = m.group(1)
          break
        if line.find('echo lund event file:') == 0:
          generators['ClusterId'] = 'lund'
          break
        if line.find('gemc') == 0 and line.find('INPUT') < 0:
          generators['ClusterId'] = 'gemc'
          break
  return generators.get('ClusterId')

def _make_timeline_entry(args):
  data = {}
  summary = job_counts.copy()
  for cid,job in condor.data.cluster_summary(args).items():
    for x in summary.keys():
      summary[x] += job[x]
  summary.pop('done')
  summary.pop('total')
  attempts = []
  for condor_id,job in get_jobs(args):
    try:
      n = int(job['NumJobStarts'])
      if n > 0:
        attempts.append(n)
    except:
      pass
  summary['attempts'] = 0
  if len(attempts) > 0:
    summary['attempts'] = round(sum(attempts) / len(attempts),2)
  sites = {}
  for site,val in condor.data.site_summary(args).items():
    if site is not None:
      sites[site] = val['run']
  data['global'] = summary
  data['sites'] = sites
  data['update_ts'] = int(datetime.datetime.now().timestamp())
  return data

def timeline(args):
  basename = 'timeline.json'
  srcdir = os.getenv('HOME')
  destdir = 'dtn1902:/volatile/clas12/osg'
  srcpath = '%s/%s'%(srcdir,basename)
  destpath = '%s/%s'%(destdir,basename)
  cache = []
  perms = stat.S_IRWXU & (stat.S_IRUSR|stat.S_IWUSR)
  perms |= stat.S_IRWXG & (stat.S_IRGRP)
  perms |= stat.S_IRWXO & (stat.S_IROTH)
  os.chmod(srcpath, perms)
  if os.path.exists(srcpath) and os.access(srcpath, os.R_OK):
    with open(srcpath,'r') as f:
      cache = json.load(f)
  cache.append(_make_timeline_entry(args))
  if not os.path.exists(srcpath) or os.access(srcpath, os.W_OK):
    with open(srcpath,'w') as f:
      f.write(json.dumps(cache))
  else:
    print('Archive DNE or unwritable:  '+srcpath)
    print(json.dumps(cache,**json_format))
  try:
    ret=subprocess.check_output(['scp',srcpath,destpath])
  except:
    print('Failed to transfer timeline.')
  os.chmod(srcpath,stat.S_IRWXU&(stat.S_IRUSR))

