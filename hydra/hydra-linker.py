#!/usr/bin/env python3
import re,os,time,glob,subprocess,datetime

dryrun = False
minimum_runno = 17762
minimum_age_seconds = 120
input_dir = '/local/baltzell/hydra/images'
output_dir = '/local/hydra/input'
blacklist_file = '/local/baltzell/hydra/blacklist.txt'
indir_regex = '^clas12mon_(\d+)_(\d+-\d+-\d+_\d+\.\d+\.\d+_[APM]+)$'
time_format = '%m-%d-%Y_%H.%M.%S_%p'

def read_blacklist(filename):
  blacklist = {}
  with open(filename,'r') as f:
    for line in f.readlines():
      try:
        runno,timestamp = line.strip().split()
        runno = int(runno)
        timestamp = datetime.datetime.strptime(timestamp, time_format)
      except:
        continue
      if runno not in blacklist:
        blacklist[runno] = []
      blacklist[runno].append(timestamp)
      blacklist[runno] = sorted(blacklist[runno])
  return blacklist

def update_blacklist(filename, additions):
  with open(filename,'a') as f:
    for x in additions:
      f.write(x+'\n')

def assign_chunks(data, blacklist):
  for runno in data.keys():
    chunks = []
    if runno in blacklist:
      chunks.extend(blacklist.get(runno))
    chunks.extend(data.get(runno).keys())
    for chunk,timestamp in enumerate(sorted(chunks)):
      data[runno][timestamp]['chunk'] = chunk

def find(blacklist):
  data = {}
  for dirpath,dirnames,filenames in os.walk(input_dir):
    for dirname in dirnames:
      fulldirname = dirpath + '/' + dirname
      m = re.match(indir_regex, dirname)
      if m is None:
        continue
      if time.time() - os.path.getmtime(fulldirname) < minimum_age_seconds:
        continue
      runno = int(m.group(1))
      timestamp = m.group(2)
      if runno < minimum_runno:
        continue
      try:
        timestamp = datetime.datetime.strptime(timestamp, time_format)
      except ValueError:
        continue
      if runno not in data:
        data[runno] = {}
      data[runno][timestamp] = {'dirpath':fulldirname}
    break
  assign_chunks(data, blacklist)
  return data

def link(data):
  additions = []
  for runno in sorted(data.keys()):
    for timestamp in data.get(runno).keys():
      if runno in blacklist:
        if timestamp in blacklist.get(runno):
          continue
      stub = '%d %s'%(runno,datetime.datetime.strftime(timestamp, time_format))
      additions.append(stub)
      idir = data[runno][timestamp]['dirpath']
      chunk = data[runno][timestamp]['chunk']
      odir = output_dir + '/' + str(runno)
      if dryrun:
        print(stub)
      else:
        os.makedirs(odir, exist_ok=True)
        os.chmod(odir, 0o777)
      for png in glob.glob(idir+'/*.png'):
        png = os.path.basename(png)
        if re.match('.*\d+-\d+-\d+_\d+\.\d+\.\d+.*', png) is not None:
          continue
        new_png = png[:-4] + '_%.4d.png'%chunk
        src = idir + '/' + png
        dst = odir + '/' + new_png
        if dryrun:
          print(src+'  ->  '+dst)
        elif not os.path.exists(dst):
          os.symlink(src, dst)
  return additions

print('Starting hydra-linker ...')
while True:
  blacklist = read_blacklist(blacklist_file)
  additions = link(find(blacklist))
  update_blacklist(blacklist_file, additions)
  if len(additions) > 0:
    t = datetime.datetime.strftime(datetime.datetime.now(), '%m/%d/%y %H:%M:%S')
    print('%s: Added %d runchunks.'%(t,len(additions)))
  time.sleep(60)

