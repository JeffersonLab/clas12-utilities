
from MyaData import MyaDatum
from CcdbUtil import RunRange

_BEAM_ENERGY_TOLERANCE=10  # MeV
_BEAM_STOP_THRESHOLD=10
_RUN_NUMBER_MAX=2E5
_RUN_NUMBER_MIN=1

#
# Beam blocker attenuation factor is dependent on beam energy.
# Here we hardcode the results of the attenuation measurements,
# since sometimes data is taken without a previous measurement
# available and so the archived PV for attenuation is sometimes
# inaccurate.


# NOTES: 

_ATTEN={}

# TO run the mya2ccdb.py code, I will need to run each target separately, since the code only supports attenuation of a given beam energy and target
# so will have to uncomment ONLY one: _ATTEN[beam_energy]=att_factor below, for a particular target, and run the mya2ccdb.py code

# C. Yero May 19, 2022 | Work Summary:
# 0) For each of the run ranges below (separated by target changes), I determined the start_time of 1st run and end_time of last run in the range
# 1) ran the mya2ccdb.py code for each range, and made comments regarding any errors mya2ccdb.py might have displayed. I also made a directory for each run range
#    with informations such as the mya2ccdb output and a MyaPlot of the run range
#
# 2) for each range, provided mya2ccdb.py ran without errors: I checked the beam_stop in MyaPlot and made sure it was consistent with beam blocker atten. output from mya2ccdb.py 
#    NOTE: For most run ranges, the Mya beam_stop paramter had a small, dip, which I checked to make sure it DID NOT occur in the middle of a run, by examining
#    the run start_time / end_time in: https://clas12mon.jlab.org/runs/summaries/,  and making sure the dip was actually in-between runs, and that the adjacent runs had
#    a attenuation factor consistent with the ouput from mya2ccd.py.  For each range I made a note under the 'Mya_beam_stop', as to whether the beam blocker was OUT 
#    and whether or NOT it was taken out during a run
#
# Observations / Questions for Nathan: 
# 0) I noticed some of the run times in the clas12mon.jlab.org/runs/summaries were inconsistent with the run time of PV B_DAQ:run_number
#    (for example, see run 15042, where in clas12mon is says: 11:02:53 - 11:19:40. whereas in B_DAQ_run_number it run time keeps going until ~17:32:18 .   
#    Will use the run range times in clas12mon for now. 
#
# 1) I noticed from the output of mya2ccdb, the SLM slope (usually 1.0 ) was inconsistent with the SLM slope in MyaPlot (~ thousands) (see, for example, Run range: 15178-15317)
#    the faraday cup slope / offsets in the output were consistent with those in the MyaPlot 
#
# 2) Runs 15726, 15727 in clas12mon.jlab.org/runs/summaries, shows it still has beam energy of 2 GeV, so I excluded those. Also, from attenuation 
#    factors table, the range 15726-15732 has no attenuation factor, so I put in 16.40835, presumably since the other Empty runs at this beam energy 
#    have that attenuation
#
# 3) FOr some of the run ranges (see below) --->  # ERROR: File "mya2ccdb.py", line 233, in <module> data=dict(offset,**atten)  TypeError: type object argument after ** must be a mapping, not NoneType
#                                                 # ERROR:  File "mya2ccdb.py", line 198, in <module> offsets[len(offsets)-1].runMax=None IndexError: list index out of range
#
# 4) Is it possible to cut out parts of a run, say if the beam blocker was OUT for a brief period of time during a RUN, can we cut out the scaler read corresponding to that part?
#    How often are the Hall B scalers read out, and is that readout stored in such a way it can be retrieved later via a loop over each scaler read ??? 


# ------CY May 19 : Added rgm attenuation factors             ~   start_time(1st run)   end _time(last run)    Mya_beam_stop               # mya2ccdb.py Output Errors ??
# 6 GeV (more precisely, 5986.36 MeV)  
#_ATTEN[5986]=15.3412   # Run range: 15016-15042, Eb=6 GeV, LH2    2021-11-10_18:15:38   2021-11-12_11:19:40     65.732                    # mya2ccdb.py runs fine 
#                                                                                                      beam blocker OUT (small dip to -0.1)          
#                                                                                                         "no runs in-between dip" | PASSED
#
#_ATTEN[5986]=15.022    # Run range: 15043-15106, Eb=6 GeV, LD2    2021-11-12_17:45:21   2021-11-18_10:37:53      65.732                    # ERROR: File "mya2ccdb.py", line 233, in <module> data=dict(offset,**atten)  TypeError: type object argument after ** must be a mapping, not NoneType
#                                                                                                       beam blocker OUT (small dip to -0.1)                                                                                                     
#                                                                                                         "no runs in-between dip" | PASSED
#                                                                                                              
#
#_ATTEN[5986]=14.8788   # Run range: 15108-15164, Eb=6 GeV, LHe4    2021-11-18_17:57:19   2021-11-23_05:24:50      65.732                                 # mya2ccdb.py runs fine 
#                                                                                                      beam blocker OUT (small dip to -0.1)                   
#                                                                                                    "run 15108 was still going: 11-18 17:57-19:06"
#                                                                                                     "beam_blocker OUT (dip)  : 11-18 18:52-19:05 " 
#                                                                                  mya2ccdb.py did NOT picked up this change since the run was already on-going(see rgm_15108_15164/output.txt )
#                                                                                  but adjacent runs DO HAVE beam_blocker IN | lumi scan specialized run, SO WILL never be part of production data | PASSED
#
#_ATTEN[5986]=15.95795  # Run range: 15165-15177, Eb=6 GeV, Empty  2021-11-23_05:49:35   2021-11-23_19:04:56      65.732                          # mya2ccdb.py runs fine 
#                                                                                                "beam blocker IN for entire duration" | PASSED
#
#_ATTEN[5986]=12.017    # Run range: 15178-15317, Eb=6 GeV, C(x4)  2021-11-25_01:24:37   2021-12-05_08:04:44       65.732                        # mya2ccdb.py runs fine 
#                                                                                                     beam blocker OUT twice (2 small dips to -0.1)    
#                                                                                                         "no runs in-between dips" | PASSED 
#                                                                                                 

#_ATTEN[5986]=8.183     # Run range: 15318-15328, Eb=6 GeV, Sn     2021-12-05_08:33:38   2021-12-06_07:50:47    65.732                           # ERROR: File "mya2ccdb.py", line 233, in <module> data=dict(offset,**atten)  TypeError: type object argument after ** must be a mapping, not NoneType
#                                                                                                       beam blocker OUT (small dip to -0.1)    
#                                                                                                         "no runs in-between dips" | PASSED 
#                                                                                                      
#_ATTEN[5986]=9.5178    # Run range: 15355-15389, Eb=6 GeV, 48Ca   2021-12-06_20:02:11   2021-12-10_07:30:18       65.732                        # mya2ccdb.py runs fine 
#                                                                                                  beam blocker OUT twice (2 small dips to -0.1)    
#                                                                                                        "no runs in between 1st dip"
#                                                                                  "during dip 2: run 15356 (lumi scan run) was still going: 12-07 00:59 - 2:31"
#                                                                                                                                    "dip 2: 12-07 02:19 - 2:31"
#                                                                                mya2ccdb.py did NOT picked up this change since the run was already on-going(see rgm_15355_15389/output.txt )
#                                                                                but adjacent runs DO HAVE beam_blocker IN | lumi scan specialized run, SO WILL never be part of production data | PASSED
#
#_ATTEN[5986]=12.6204   # Run range: 15390-15432, Eb=6 GeV, 40Ca   2021-12-10_17:23:13   2021-12-14_07:35:07     65.732                             # mya2ccdb.py runs fine 
#                                                                                                   beam blocker OUT twice (2 small dips to -0.1)
#                                                                                                   "both dips ocurred during run 15390"  PASSED   
#                                                                                      "but according to shift summary, 15390 is JUNK" See: https://clas12mon.jlab.org/runs/summaries/
#
#_ATTEN[5986]=14.1515   # Run range: 15433-15456, Eb=6 GeV, LD2    2021-12-14_14:22:22   2021-12-17_07:30:42        65.732                        # mya2ccdb.py runs fine 
#                                                                                                      beam blocker OUT (small dip to -0.1)      
#                                                                                               "run 15434 was still going: 12-15 1:20-2:00"
#                                                                                               "beam blocker OUT (dip)   : 12-15 1:45-1:56 " 
#                                                                          mya2ccdb.py did NOT picked up this change since the run was already on-going(see rgm_15433_15456/output.txt )
#                                                                                  but adjacent runs DO HAVE beam_stopper IN | run 15434 is a beam blocker calibration run SO WILL never be part of production | PASSED
#
#_ATTEN[5986]=13.9358   # Run range: 15458-15490, Eb=6 GeV, LHe4   2021-12-17_11:33:01   2021-12-21_07:19:07         65.732                       # mya2ccdb.py runs fine 
#                                                                                                    beam blocker OUT (small dip to -0.1)     
#                                                                                                 run 15458 was still on-going: 12-17 11:33 - 12:00       
#                                                                                                            beam blocker OUT : 12-17 11:47 - 11:58
#                                                                   mya2ccdb.py did NOT picked up this change since the run was already on-going(see rgm_15458_15490/output.txt )
#                                                                                  but adjacent runs DO HAVE beam_stopper IN | run 15458 is a beam blocker calibration run SO WILL never be part of production | PASSED
#

# ------CY May 19 : Added rgm attenuation factors             ~   start_time(1st run)   end _time(last run)     Mya_beam_stop  
# 2.1 GeV (more precisely, 2070.52 MeV)
# beam blocker OUT ---> -999
#_ATTEN[2070]=-999   # Run range: 15533-15565, Eb=2.1 GeV, LH2    2022-01-09_18:00:04   2022-01-13_08:01:42        65.732->-0.1                                   # mya2ccdb.py runs fine
#                                                                                  beam blocker OUT (change to -0.1) @ 01-11 8:56 (during run 15538 ) | PASSED 
#                                                                                  "15533 - 15538 no beam",  "15540 - 15565 had beam, and beam blocker OUT"
#                                                                              "Mya plot beam_stop is consistent with mya2ccdb.py output", see rgm_15533_15565/output.txt             
#                                                                                             
#_ATTEN[2070]=-999   # Run range: 15566-15627, Eb=2.1 GeV, LD2    2022-01-13_12:28:32   2022-01-16_17:57:42    beam blocker OUT (-0.1) | PASSED  | # ERROR: File "mya2ccdb.py", line 233, in <module> data=dict(offset,**atten)  TypeError: type object argument after ** must be a mapping, not NoneType
#                                                                                                       ("need to fix bug in code, but everything else is fine")

#_ATTEN[2070]=-999   # Run range: 15628-15636, Eb=2.1 GeV, LH2    2022-01-16_23:16:03   2022-01-17_11:27:56     beam blocker OUT (-0.1) | PASSED                            # mya2ccdb.py runs fine

#_ATTEN[2070]=23.3452   # Run range: 15637-15642, Eb=2.1 GeV, Empty  2022-01-17_14:04:29   2022-01-18_13:26:35   53                        # mya2ccdb.py runs fine
#                                                                                                             beam blocker IN | PASSED
#                                                                                                          "small fluctuation in beam_stop"
#                                                                                               "after 15637, but before 15638, so no run was compromised"

#_ATTEN[2070]=-999   # Run range: 15643-15670, Eb=2.1 GeV, C      2022-01-18_23:43:07   2022-01-20_20:28:08  -0.1                            # mya2ccdb.py runs fine
#                                                                                                         beam blocker OUT   | PASSED

#_ATTEN[2070]=-999   # Run range: 15671-15725, Eb=2.1 GeV, LAr    2022-01-20_20:32:28   2022-01-24_07:19:16  -0.1                            # mya2ccdb.py runs fine
#                                                                                                         beam blocker OUT   | PASSED

# ------CY May 19 : Added rgm attenuation factors             ~   start_time(1st run)   end _time(last run)
# 4 GeV (more precisely, 4029.62 MeV), 
#_ATTEN[4029]=16.40835  # Run range: 15728-15732, Eb=4 GeV, Empty  2022-01-24_11:31:11  2022-01-24_12:15:05      53                            # mya2ccdb.py runs fine
#                                                                                                          beam blocker IN   | PASSED

#_ATTEN[4029]=11.6961   # Run range: 15733,       Eb=4 GeV, C      2022-01-24_17:09:54  2022-01-24_18:15:47      53->-0.1 (@ 18:00)             # ERROR:  File "mya2ccdb.py", line 198, in <module> offsets[len(offsets)-1].runMax=None IndexError: list index out of range
#                                                                                                 run 15733 was still on-going: 17:09 - 18:15
#                                                                                                           "beam blocker OUT : 18:00 - 18:14"| run 15733 is a beam blocker calibration run SO WILL never be part of production | PASSED
#                                                                                                  

#_ATTEN[4029]=4.2662    # Run range: 15734,       Eb=4 GeV, LAr    2022-01-24_18:23:22  2022-01-24_22:20:02      53                            # ERROR:  File "mya2ccdb.py", line 198, in <module> offsets[len(offsets)-1].runMax=None IndexError: list index out of range
#                                                                                                    beam blocker IN  
#                                                                                     "need to fix bug before this run can be checked" | 15734 IS A JUNK RUN | PASSED

#_ATTEN[4029]=16.40835  # Run range: 15735-15738, Eb=4 GeV, Empty  2022-01-25_18:00:16  2022-01-25_18:28:45      53                            # mya2ccdb.py runs fine
#                                                                                                         beam blocker IN | PASSED 

#_ATTEN[4029]=4.2662    # Run range: 15739-15765, Eb=4 GeV, LAr    2022-01-27_14:19:02  2022-01-29_22:30:17      53->-0.1 (@ 1-27  20:46)            # mya2ccdb.py runs fine
#                                                                                                              -0.1->53  (@ 1-29  22:00)
#                                                                                         mya2ccdb reported:   "beam blocker IN: 15739-15742"
#                                                                                         mya2ccdb reported:   "beam blocker OUT: 15743-15765"
#                                                                               from MyaPlot, the beam blocker was taken OUT during run 15742 and put IN
#                                                                                during run 15765, but since the runs were on-going, mya2ccdb.py did not
#                                                                                 pickup the parameter change until the next run. | run 15742 is beam blocker calibration | run 15765 is JUNK RUN | PASSED

#_ATTEN[4029]=11.6961   # Run range: 15766-15775, Eb=4 GeV, C      2022-01-29_22:42:08  2022-01-30_13:30:35      53                            # mya2ccdb.py runs fine
#                                                                                                          beam blocker IN   | PASSED

#_ATTEN[4029]=16.40835  # Run range: 15777,       Eb=4 GeV, Empty  2022-01-30_16:06:04  2022-01-30_18:04:04      53                            # ERROR:  File "mya2ccdb.py", line 198, in <module> offsets[len(offsets)-1].runMax=None IndexError: list index out of range
#                                                                                                          beam blocker IN   | need to fix bug first, but PASSED

#_ATTEN[4029]=11.6961   # Run range: 15778-15784, Eb=4 GeV, C      2022-01-30_18:10:51  2022-01-31_08:22:00      53                            # mya2ccdb.py runs fine
#                                                                                                          beam blocker IN   | PASSED

# ------CY May 19 : Added rgm attenuation factors             ~   start_time(1st run)   end _time(last run)
# 6 GeV, (more precisely. 5986.36 MeV)

#_ATTEN[5986]=15.95795  # Run range: 15787-15788, Eb=6 GeV, Empty  2022-01-31_15:16:26   2022-01-31_15:46:50    -0.1->53 (@ 15:32)             # mya2ccdb.py runs fine
#                                                                                                                53->-0.1 (@15:40)   
#                                                                                      "beam blocker was put IN and taken OUT while run 15788 was on-going" 
#                                                                                       mya2ccdb.py did NOT pick up this change, as it ocurred during a run
#                                                                                       so, mya2ccdb.py output was beam block OUT during 15787-15788 | RUN 15788 was a daq test run | PASSED
#                                                                                          

#_ATTEN[5986]=-999  # Run range: 15789-15802, Eb=6 GeV, LAr    2022-01-31_15:49:30   2022-02-01_19:58:52     -0.1                                # mya2ccdb.py runs fine
#                                                                                                          beam blocker OUT   | PASSED

#_ATTEN[5986]=15.95795  # Run range: 15803,       Eb=6 GeV, Empty  2022-02-01_20:28:52   2022-02-01_21:28:59      53                           # ERROR:  File "mya2ccdb.py", line 198, in <module> offsets[len(offsets)-1].runMax=None IndexError: list index out of range            
#                                                                                                          beam blocker IN   | need to fix bug first, but PASSED

#_ATTEN[5986]=10.1932   # Run range: 15804-15827, Eb=6 GeV, Sn     2022-02-01_22:02:25   2022-02-03_07:30:43      53                           # mya2ccdb.py runs fine
#                                                                                                       beam blocker OUT twice (2 dips) 
#                                                                                                   run 15804: 02-01 22:02 - 22:26   ( was beam blocker calibration run )
#                                                                                                       dip 1: 02-01 22:12 - 22:30
#                                                                                                   next run 15805 started @ 22:38, so beam blocker was already IN
#                                                                                                   run 15817: 02-02 11:30 - 11:49 (junK run)
#                                                                                                       dip 2: 02-02 11:39 - 11:47         
#                                                                                                 beam blocker taken OUT/ put back IN  
#                                                                                            during run 15804 and 15817, so mya2ccdb did not
#                                                                               pickup any changes in the beam blocker status, but these runs were calibration and junk, so | PASSED
#                                                                                        

#_ATTEN[5986]=11.5568   # Run range: 15829-15884, Eb=6 GeV, 48Ca   2022-02-03_17:47:17   2022-02-08_06:00:55    53                             # mya2ccdb.py runs fine
#                                                                                                             (small dip to -0.1)
#                                                                                                 run 15838 (not even recorded in run summary)  | PASSED
#                                                                                                        dip : 02-04 21:15 - 21:28         
#                                                                                                 adjacent runs, 15837, 15840 did NOT have beam,
#                                                                          even though beam blocker was briefly OUT during 15838, it does NOT compromise then other runs.
#                                                                                mya2ccdb recorded beam blocker IN during entire run range, which is consistent with what is observed



#_ATTEN[10604]= 9.8088
#_ATTEN[10409]= 9.6930
#_ATTEN[10405]= 9.6930  # unmeasured during BONuS, copied from 10409
#_ATTEN[10375]= 9.6930  # bogus beam energy from ACC during BONuS
#_ATTEN[10339]= 9.6930  # unmeasured during BONuS, copied from 10409
#_ATTEN[10389]= 9.6930  # unmeasured during BONuS, copied from 10409
#_ATTEN[10197]= 9.6930  # bogus beam energy from ACC, actually 10339
#_ATTEN[10200]= 9.96025
#_ATTEN[ 7546]=14.89565
#_ATTEN[ 6535]=16.283
#_ATTEN[ 6423]=16.9726

_OVERRIDE_ENERGY={
    RunRange(12444,12853,None):10405
}

class MyaFcup:
  def __init__(self,myaDatum):
    if not isinstance(myaDatum,MyaDatum):
      sys.exit('MyaFcup requires a MyaDatum')
    self.date = myaDatum.date
    self.time = myaDatum.time
    self.slm_atten = 1.0
    try:
      self.run = int(myaDatum.getValue('B_DAQ:run_number'))
      if self.run > _RUN_NUMBER_MAX:
        self.run=None
      if self.run < _RUN_NUMBER_MIN:
        self.run=None
    except ValueError:
      self.run = None
    try:
      self.energy = float(myaDatum.getValue('MBSY2C_energy'))
    except ValueError:
      self.energy = None
    try:
      # convert to -1/0/+1=IN/UDF/OUT scheme:
      self.hwp = int(myaDatum.getValue('IGL1I00OD16_16'))
      if   self.hwp == 1: self.hwp = -1
      elif self.hwp == 0: self.hwp = 1
      else:               self.hwp = 0
    except ValueError:
      self.hwp = None
    try:
      self.offset = float(myaDatum.getValue('fcup_offset'))
    except ValueError:
      self.offset = None
    try:
      self.slm_offset = float(myaDatum.getValue('slm_offset'))
    except ValueError:
      self.slm_offset = None
    try:
      self.stopper = float(myaDatum.getValue('beam_stop'))
    except ValueError:
      self.stopper = None
    self.energy = self.correctEnergy()
    self.atten = self.getAttenuation()
  def correctEnergy(self):
    if self.energy is not None:
      for runRange,energy in _OVERRIDE_ENERGY.items():
        if runRange.contains(self.run):
          return energy
    return self.energy
  def getAttenuation(self):
    if self.energy is None:
      return None
    if self.stopper is None:
      return None
    if self.stopper < _BEAM_STOP_THRESHOLD:
      return 1.0
    for e in _ATTEN.keys():
      if abs(e-self.energy) < _BEAM_ENERGY_TOLERANCE:
        return _ATTEN[e]
    return None
  def __str__(self):
    s='%10s %10s'%(self.date,self.time)
    if self.run is None:     s+=' %5s'%self.run
    else:                    s+=' %5d'%self.run
    if self.energy is None:  s+=' %8s'%self.energy
    else:                    s+=' %8.2f'%self.energy
    if self.stopper is None: s+=' %6s'%self.stopper
    else:                    s+=' %6.3f'%self.stopper
    if self.atten is None:   s+=' %8s'%self.atten
    else:                    s+=' %8.5f'%self.atten
    if self.offset is None:  s+=' %6s'%self.offset
    else:                    s+=' %5.1f'%self.offset
    s+=' %s'%self.hwp
    return s

