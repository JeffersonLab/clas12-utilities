###
### Utilities for selecting HTCondor jobs
###

class Matcher():
  def __init__(self, values):
    self.values = []
    self.antivalues = []
    for v in [str(v) for v in values]:
      if v.startswith('-'):
        self.antivalues.append(v[1:])
      else:
        self.values.append(v)
  def matches(self, value):
    if str(value) in self.antivalues:
      return False
    if str(value) in self.values:
      return True
    return len(self.values)==0 or value is None
  def pattern_matches(self, value):
    for v in self.antivalues:
      if v.find(str(value)) >= 0:
        return False
    for v in self.values:
      if v.find(str(value)) >= 0:
        return True
    return len(self.values)==0 or value is None

class CondorMatcher(Matcher):
  def __init__(self, values, key):
    self.key = key
    super().__init__(values)
  def matches(self, job):
    return super().matches(job.get(self.key))
  def pattern_matches(self, job):
    return super().pattern_matches(job.get(self.key))

class CondorMatchers():
  def __init__(self, args):
    self.args = args
    self.exit = CondorMatcher(args.exit, 'ExitCode')
    self.gemc = CondorMatcher(args.gemc, 'gemc')
    self.user = CondorMatcher(args.user, 'user')
    self.site = CondorMatcher(args.site, 'MATCH_GLIDEIN_Site')
    self.host = CondorMatcher(args.host, 'LastRemoteHost')
    self.condor = CondorMatcher(args.condor, 'condor')
    self.generator = CondorMatcher(args.generator, 'generator')
  def matches(self, job):
    if args.noexit and job.get('ExitCode') is not None:
      return False
    if job.get('condor') is None:
      return False
    if not super(CondorMatcher, self.condor).matches(job.get('condor').split('.').pop(0)):
      return False
    if not self.gemc.matches(job):
      return False
    if not self.user.matches(job):
      return False
    if not self.site.pattern_matches(job):
      return False
    if not self.host.pattern_matches(job):
      return False
    if not self.generator.matches(job):
      return False
    elif not self.exit.matches(job):
      return False
    if self.args.plot is False:
      if self.args.idle and job_states.get(job['JobStatus']) != 'I':
        return False
      if self.args.completed and job_states.get(job['JobStatus']) != 'C':
        return False
      if self.args.running and job_states.get(job['JobStatus']) != 'R':
        return False
      if self.args.held and job_states.get(job['JobStatus']) != 'H':
        return False
    try:
      if int(job['CompletionDate']) > int(self.args.end.timestamp()):
        return False
    except:
      pass
    return True

