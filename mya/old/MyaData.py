import subprocess

class MyaPv:
  def __init__(self,name,deadband=None):
    self.name=name
    self.deadband=None
    if deadband is not None:
      self.deadband=float(deadband)
  def getMyaDataArg(self):
    if self.deadband is None:
      return self.name
    else:
      return self.name+','+str(self.deadband)

class MyaDatum:
  def __init__(self,date,time):
    self.date=date
    self.time=time
    self.pvs={}
  def addPv(self,name,value):
    self.pvs[name]=value
  def getValue(self,name):
    if name in self.pvs:
      return self.pvs[name]
    else:
      return None
  def __str__(self):
    print(str(self.date),str(self.time),str(self.pvs))

class MyaData:
  def __init__(self,start=None,end=None):
    self.pvs=[]
    self.start='-1w'
    self.end='0'
    if start is not None:
      self.start=str(start)
    if end is not None:
      self.end=str(end)
  def addPv(self,name,deadband=None):
    self.pvs.append(MyaPv(name,deadband))
  def setStart(self,start):
    self.start=str(start)
  def setEnd(self,end):
    self.end=str(end)
  def get(self):
    cmd=['myData','-b',self.start,'-e',self.end,'-i']
    cmd.extend([pv.getMyaDataArg() for pv in self.pvs])
    for line in subprocess.check_output(cmd).splitlines():
      columns=line.strip().split()
      if len(columns) == 2+len(self.pvs):
        date,time=columns[0],columns[1]
        md=MyaDatum(date,time)
        for ii in range(2,len(columns)):
          md.addPv(self.pvs[ii-2].name,columns[ii])
        yield(md)

