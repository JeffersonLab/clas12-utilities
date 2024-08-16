###
### Tools for generating HTCondor status tables
### 

import os
import math
import datetime
import condor.util

null_field = '-'

class Column():
  def __init__(self, name, width, tally=None):
    self.name = name
    self.width = width
    self.tally = tally
    self.fmt = '%%-%d.%ds' % (self.width, self.width)

class Table():
  def __init__(self):
    self.columns = []
    self.rows = []
    self.tallies = []
    self.width = 0
  def add_column(self, column, tally=None):
    if not isinstance(column, Column):
      raise TypeError()
    self.columns.append(column)
    self.tallies.append([])
    self.fmt = ' '.join([x.fmt for x in self.columns])
    self.width = sum([x.width for x in self.columns]) + len(self.columns) - 3
  def add_row(self, values):
    self.rows.append(self.values_to_row(values).rstrip())
    self.tally(values)
  def tally(self, values):
    for i in range(len(values)):
      if self.columns[i].tally is not None:
        try:
          x = float(values[i])
          self.tallies[i].append(x)
        except:
          pass
  def values_to_row(self, values):
    # left-truncate and prefix with a '*' if a column is too long
    x = []
    for i,v in enumerate([str(v).strip() for v in values]):
      if len(v) > self.columns[i].width:
        v = '*'+v[len(v)-self.columns[i].width+1:]
      x.append(v)
    return self.fmt % tuple(x)
  def get_tallies(self):
    # assume it's never appropriate to tally the 1st column
    values = ['tally']
    for i in range(1,len(self.columns)):
      if self.columns[i].tally is not None and len(self.tallies[i]) > 0:
        values.append(sum(self.tallies[i]))
        if self.columns[i].tally is 'avg':
          if values[-1] > 0:
            values[-1] = '%.1f' % (values[-1]/len(self.tallies[i]))
        else:
          values[-1] = int(values[-1])
      else:
        values.append(null_field)
    return (self.fmt % tuple(values)).rstrip()
  def get_header(self):
    ret = ''.ljust(self.width, null_field)
    ret += '\n' + (self.fmt % tuple([x.name for x in self.columns])).rstrip()
    ret += '\n' + ''.ljust(self.width, null_field)
    return ret
  def __str__(self):
    rows = [self.get_header()]
    rows.extend(self.rows)
    rows.append(self.get_tallies())
    rows.append(self.get_header())
    return '\n'.join(rows)

class CondorColumn(Column):
  def __init__(self, name, varname, width, tally=None):
    super().__init__(name, width, tally)
    self.varname = varname

class CondorTable(Table):
  def add_column(self, name, varname, width, tally=None):
    super().add_column(CondorColumn(name, varname, width, tally))
  def job_to_values(self, job):
    return [self.munge(x.varname, job.get(x.varname)) for x in self.columns]
  def job_to_row(self, job):
    return self.values_to_row(self.job_to_values(job))
  def add_job(self, job):
    self.add_row(self.job_to_values(job))
    return self
  def add_jobs(self,jobs):
    for k,v in jobs.items():
      self.add_job(v)
    return self
  def munge(self, name, value):
    ret = value
    if value is None or value == 'undefined':
      ret = null_field
    elif name == 'NumJobStarts':
      if value == 0:
        ret = null_field
    elif name == 'ExitBySignal':
      ret = {True:'Y',False:'N'}[value]
    elif name == 'JobStatus':
      try:
        ret = job_states[value]
      except:
        pass
    elif name.endswith('Date'):
      if value == '0' or value == 0:
        ret = null_field
      else:
        try:
          x = datetime.datetime.fromtimestamp(int(value))
          ret = x.strftime('%m/%d %H:%M')
        except:
          pass
    elif name == 'DiskUsage':
      try:
        ret = int(value)/1e6
      except:
        pass
    return ret

def average(alist):
  if len(alist) > 0:
    return '%.2f' % (sum(alist) / len(alist))
  else:
    return null_field

def stddev(alist):
  if len(alist) > 0:
    m = average(alist)
    s = sum([ (x-float(m))*(x-float(m)) for x in alist ])
    return '%.2f' % math.sqrt(s / len(alist))
  else:
    return null_field

summary_table = CondorTable()
summary_table.add_column('condor','ClusterId',9)
summary_table.add_column('gemc','gemc',6)
summary_table.add_column('submit','QDate',12)
summary_table.add_column('total','TotalSubmitProcs',8,tally='sum')
summary_table.add_column('done','done',8,tally='sum')
summary_table.add_column('run','run',8,tally='sum')
summary_table.add_column('idle','idle',8,tally='sum')
summary_table.add_column('held','held',8,tally='sum')
summary_table.add_column('user','user',10)
summary_table.add_column('gen','generator',9)
summary_table.add_column('util','eff',4)
summary_table.add_column('ceff','ceff',4)
summary_table.add_column('att','att',4)
summary_table.add_column('disk','DiskUsage',6)

site_table = CondorTable()
site_table.add_column('site','MATCH_GLIDEIN_Site',26)
site_table.add_column('total','total',8,tally='sum')
site_table.add_column('done','done',8,tally='sum')
site_table.add_column('run','run',8,tally='sum')
site_table.add_column('idle','idle',8,tally='sum')
site_table.add_column('held','held',8,tally='sum')
site_table.add_column('wallhr','wallhr',6)
site_table.add_column('stddev','ewallhr',7)
site_table.add_column('util','eff',4,tally='avg')

job_table = CondorTable()
job_table.add_column('condor','condorid',13)
job_table.add_column('gemc','gemc',6)
job_table.add_column('site','MATCH_GLIDEIN_Site',15)
job_table.add_column('host','LastRemoteHost',16)
job_table.add_column('stat','JobStatus',4)
job_table.add_column('exit','ExitCode',4)
job_table.add_column('sig','ExitBySignal',4)
job_table.add_column('att','NumJobStarts',4,tally='avg')
job_table.add_column('wallhr','wallhr',6,tally='avg')
job_table.add_column('util','eff',4,tally='avg')
job_table.add_column('ceff','ceff',4)
job_table.add_column('start','JobCurrentStartDate',12)
job_table.add_column('end','CompletionDate',12)
job_table.add_column('user','user',10)
job_table.add_column('gen','generator',9)
job_table.add_column('disk','DiskUsage',6)

def tail_log(job, nlines):
  print(''.ljust(80,'#'))
  print(''.ljust(80,'#'))
  print(job_table.get_header())
  print(job_table.job_to_row(job))
  for x in (job['UserLog'],job['stdout'],job['stderr']):
    if x is not None and os.path.isfile(x):
      print(''.ljust(80,'>'))
      print(x)
      if nlines > 0:
        print('\n'.join(reversed(list(condor.util.readlines_reverse(x, nlines)))))
      elif nlines < 0:
        for x in condor.util.readlines(x):
          print(x)

