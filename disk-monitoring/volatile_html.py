#!/usr/bin/env python
import mysql.connector
import time
import sys
import subprocess

path_prefix='/volatile/clas12'
startSeconds = time.time()
updateTime = time.strftime('%c')
max_rows = 1e4

if len(sys.argv)>1:
  path_prefix=sys.argv[1]

# setup the database connection:
db = mysql.connector.connect(
  host="scidbw.jlab.org",
  user="dummy",
  passwd="",
  database="wdm"
)
cursor = db.cursor()

# get global info:
query = 'select reserved, cached/1024./1024./1024. from projectDisk where root = "%s"'%path_prefix
cursor.execute(query)
result = cursor.fetchall()
reserved = float(result[0][0])
used = float(result[0][1])
target_size = used - reserved
if target_size < 1000.0:
  target_size = 1000.0

# get detailed info:
query = 'select vfile.mod_time as mtime, file_name, vfile.owner, size, full_path'
query += ' from vfile, vdirectory, projectDisk'
query += ' where vfile.dir_index = vdirectory.dir_index'
query += ' and projectDisk.disk_index = vdirectory.disk_index'
query += ' and root = "%s"'%path_prefix
query += ' order by mtime'
cursor.execute(query)
result = cursor.fetchall()

# check for blacklisted directories:
checked_dirs = []
def is_dir_checked(d):
  if d in checked_dirs:
    return True
  checked_dirs.append(d)
  return False

queue_lines = []
count = 0
count_dir = 0
sum_gb = 0

for i in range(len(result)):

  count += 1
  line_array = result[i]
  sum_gb = float(line_array[3])/1024.0/1024.0/1024.0
  this_dir = str(line_array[4])

#  was thinking to parasitically get top level usage, but this 
#  databse query is inappropriate for that:
#  len_path_prefix = len(path_prefix.strip('/').split('/'))
#  top_dir = this_dir.strip('/').split('/')[len_path_prefix]
#  if top_dir not in top_sums:
#    top_sums[top_dir] = 0
#  top_sums[top_dir] += int(sum_gb)

  # avoid checking the same dir twice, not sure why this is necssary:
  if is_dir_checked(this_dir):
    continue

  # stop accumulating if we've already got sufficient data:
  if sum_gb > target_size or count_dir > max_rows:
    break

  # accumulate the deletion queue, i.e. the oldest stuff:
  count_dir += 1
  line_str_array = []
  for j in range(len(line_array)):
    line_str_array.append(str(line_array[j]))
  line = '<tr>'
  line += '<td>%d</td>'%count_dir
  line += '<td>%d</td>'%count
  line += '<td>%.3f</td>'%sum_gb
  line += '<td>%s</td>'%line_str_array[0]
  line += '<td>%s</td>'%line_str_array[2]
  line += '<td>%s</td>'%line_str_array[4].replace(path_prefix+'/','')
  line += '<td>%s</td>'%line_str_array[1]
  line += '</tr>'
  queue_lines.append(line)

# get top-level usage (this is the slowest part, so we limit to specific subdirs):
# (if we could use the database to do this efficiently, that would be nice):
top_sums = {}
for x in 'a','b','c','f','k','m':
  try:
    y = subprocess.check_output(['du','-s',path_prefix+'/rg-'+x])
    y = float(y.split().pop(0))/1024/1024/1024
    top_sums['rg-'+x] = y
  except:
    pass
fmt = '<tr><td>%s</td><td>%.1f</td></tr>'
top_sums_lines = [ fmt%(x,top_sums[x]) for x in reversed(sorted(top_sums,key=top_sums.get)) ]

# print header:
print('<html>')
print('<head><title>'+path_prefix+' Usage and Auto-Deletion Queue</title></head>')
print('<body>')
print('<h1>'+path_prefix+' Usage and Auto-Deletion Queue</h1>')
print('<p> Last Updated: %s</p>'%updateTime)
print('<p> Update Duration: %.1f minutes</p>'%((time.time()-startSeconds)/60))

# print top-level usage:
print('<h2>Usage Summary:</h2>')
print('<table border>')
print('<tr>')
print('<th>subdirectory</th>')
print('<th>size (TB)</th>')
print('</tr>')
print('\n'.join(top_sums_lines))
print('</table>')

# print auto-deletion queue:
print('<h2>Auto-Deletion Queue:</h2>')
print('<table border>')
print('<tr>')
print('<th>running directory count</th>')
print('<th>running file count</th>')
print('<th>running sum of <br/> size of old files (GB)</th>')
print('<th>file mod time</th>')
print('<th>file owner</th>')
print('<th>directories with oldest files</th>')
print('<th>oldest file in directory</th>')
print('</tr>')
print('\n'.join(queue_lines))
print('</table>')

# print footer
print('</body>')
print('</html>')


