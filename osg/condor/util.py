###
### Miscellaneous functions
###

import os
import gzip
import collections

def sort_dict(dictionary, subkey):
  '''Sort a dictionary of sub-dictionaries by one of the keys
  in the sub-dictionaries'''
  ret = collections.OrderedDict()
  ordered_keys = []
  for k,v in dictionary.items():
    if len(ordered_keys) == 0:
      ordered_keys.append(k)
    else:
      inserted = False
      for i in range(len(ordered_keys)):
        if v[subkey] > dictionary[ordered_keys[i]][subkey]:
          ordered_keys.insert(i,k)
          inserted = True
          break
      if not inserted:
        ordered_keys.append(k)
  for x in ordered_keys:
    ret[x] = dictionary[x]
  return ret

def readlines(filename):
  if filename is not None:
    if os.path.isfile(filename):
      if filename.endswith('.gz'):
        f = gzip.open(filename, errors='replace')
      else:
        f = open(filename, errors='replace')
      for line in f.readlines():
        yield line.strip()
      f.close()

def readlines_reverse(filename, max_lines):
  '''Get the trailing lines from a file, stopping
  after max_lines unless max_lines is negative'''
  if filename is not None:
    if os.path.isfile(filename):
      if filename.endswith('.gz'):
        f = gzip.open(filename, errors='replace')
      else:
        f = open(filename, errors='replace')
      n_lines = 0
      f.seek(0, os.SEEK_END)
      position = f.tell()
      line = ''
      while position >= 0:
        if n_lines > max_lines and max_lines>0:
          break
        f.seek(position)
        next_char = f.read(1)
        if next_char == "\n":
           n_lines += 1
           yield line[::-1]
           line = ''
        else:
           line += next_char
        position -= 1
      yield line[::-1]

