import os

class RunRange:
  def __init__(self,runMin,runMax,data):
    self.runMin=runMin
    self.runMax=runMax
    self.data=data
  def contains(self,run):
    if self.runMin is not None and run<self.runMin:
      return False
    if self.runMax is not None and run>self.runMax:
      return False
    return True
  def __str__(self):
    return '%s-%s %s'%(str(self.runMin),str(self.runMax),self.data)

class CcdbEntry(RunRange):
  def __init__(self,runMin,runMax,data={},sector=0,layer=0,component=0):
    RunRange.__init__(self,runMin,runMax,data)
    self.prefix=None
    self.table=None
    self.sector=sector
    self.layer=layer
    self.component=component
  def getSLC(self):
    return '%d %d %d'%(self.sector,self.layer,self.component)
  def getFilename(self):
    return '%s_%s-%s.txt'%(self.prefix,str(self.runMin),str(self.runMax))
  def writeFile(self,directory=None):
    if directory is None: directory='.'
    if not os.access(directory,os.W_OK):
      os.makedirs(directory)
    with open(directory+'/'+self.getFilename(),'w') as f:
      f.write(self.getRow())
      f.close()
  def getCommand(self):
    cmd='ccdb -c mysql://clas12writer:geom3try@clasdb/clas12 add '+self.table+' -r '
    if self.runMin is not None:
      cmd+=str(self.runMin)
    cmd+='-'
    if self.runMax is not None:
      cmd+=str(self.runMax)
    cmd+=' '+self.getFilename()
    return cmd

class FcupCcdbEntry(CcdbEntry):
  def __init__(self,runMin,runMax,data={'offset':None,'atten':None}):
    if 'slope' not in data:
      data['slope']=906.2
    CcdbEntry.__init__(self,runMin,runMax,data)
    self.prefix='fcup'
    self.table='runcontrol/fcup'
    # kludge for BONuS, where Faraday cup died:
    if runMin >= 12858 and runMin <= 12951:
      self.data['slope'] = 1.0
      self.data['atten'] = 0.0
  def getRow(self):
    return '%s %.2f %.2f %.5f'%(self.getSLC(),\
        self.data['slope'],self.data['offset'],self.data['atten'])

class SlmCcdbEntry(CcdbEntry):
  def __init__(self,runMin,runMax,data={'offset':None,'atten':None,'slope':None}):
    CcdbEntry.__init__(self,runMin,runMax,data)
    self.prefix='slm'
    self.table='runcontrol/slm'
    self.data['slope']=1.0
    self.data['atten']=0.0
    # FIXME:  SLM slope is generally unknown, except during special BONuS period:
    if runMin >= 12878 and runMin <= 12951:
      self.data['slope']=4298.0
      self.data['atten']=1.0
  def getRow(self):
    return '%s %.2f %.2f %.5f'%(self.getSLC(),\
        self.data['slope'],self.data['offset'],self.data['atten'])

class HwpCcdbEntry(CcdbEntry):
  def __init__(self,runMin,runMax,data={'hwp':None}):
    CcdbEntry.__init__(self,runMin,runMax,data)
    self.prefix='hwp'
    self.table='runcontrol/hwp'
  def getRow(self):
    return '%s %d'%(self.getSLC(),self.data['hwp'])

