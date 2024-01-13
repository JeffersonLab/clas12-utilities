#!/usr/bin/env python
import os,sys

free_limit = float(sys.argv[1])

for d in ['/work/clas12','/work/hallb/hps']:

  x = os.statvfs(d)

  free_frac = float(x.f_bfree) / x.f_blocks

  used_tb = float(x.f_blocks) * x.f_bsize/1e12
  free_tb = float(x.f_bfree) * x.f_bsize/1e12

  if len(sys.argv) > 2 or free_frac < free_limit:
    fmt = '%s = %.2f%% free'
    if free_frac < free_limit:
      fmt = 'WARNING!!!!! ' + fmt
    print(fmt%(d,100*free_frac))

