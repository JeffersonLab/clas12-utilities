#!/bin/bash
#
# N. Baltzell, March 2021
#
# For rsyncing sufficiently old OSG data files from local scosg##
# filesystem to final Lustre destination for users, and deleting
# their local copies upon successful transfer.  A separate python
# script is called at the end to do local filesystem cleanup to 
# avoid excessive finds.
#
# Does *not* delete anything at the destination, but there should be
# something in place to at least clean up old empty directories there.
#
# Intended to be run as a cronjob with MAILTO set, with no arguments,
# and without redirecting stdout/stderr.  Does *not* print anything
# to stdout/stderr unless there's a critical error or filesystem
# almost full, with all logging to $logfile.
#
# Notes:
#
# 1) The rsync version on scosg16 appears to be too old to support
#    full wildcards in ignore/exclude arguments.
#
# 2) There exist things in these CLAS12 OSG job that can be cleaned
#    up before registering in the payload, e.g. LUND and EVIO files,
#    whose information is already in HIPO, and background files.
#
# 3) Identically named nodeScript.sh exists at both the submit and
#    every job directory level, and we need to keep at least one of
#    them for provenance until, until that info is in HIPO. 
#
# 4) Job numbers appear in directory names, but not those jobs'
#    output files.  More fully-qualifed output file names (at least
#    job number, but could consider other specs too) could
#    facilitate automatic downsizing unnecessary directories later. 
#

########################################################################
# Static setup:
########################################################################

# user@host that should be running this script:
user=gemc
localhost=scosg2202

# path on $localhost to be rsync'd to $dest:
srcdir=/osgpool/hallb/clas12/gemc

# remote destination for contents of $srcdir:
remotehost=dtn1902
remotepath=/lustre19/expphy/volatile/clas12/osg2
dest=$user@$remotehost:$remotepath

# timeout transfer if it takes longer than this many seconds: 
rsync_timeout=5400

# data files older than this will be rsync'd to $dest:
rsync_minutes=60

# files older than this will be deleted from $srcdir:
delete_days=7

# script name and absolute path containing this script:
scriptname=$(basename $0)
dirname="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"

# output files for this instance of this script:
mkdir -p $srcdir/transfers /tmp/gemc
timestamp=$(date +%Y%m%d_%H%M%S)
tmpfile=$(mktemp /tmp/gemc/$timestamp.XXXXXX)
logfile=$(mktemp $srcdir/transfers/$timestamp.XXXXXX.log)

# conveneniences for logging:
errmsg="ERROR:  $scriptname: "
warnmsg="WARNING:  $scriptname: "
infomsg="INFO:  $scriptname: "
tee="tee -a $logfile"

########################################################################
# Interpret command line:
########################################################################

dryrun=0
verbose=0
usage="Usage:  $scriptname [-d (dry run)] [-v (verbose)]"
while getopts "dvh" opt; do
  case "${opt}" in
    d)
      dryrun=1
      ;;
    v)
      verbose=1
      ;;
    h)
      echo $usage
      exit 0
      ;;
    *)
      echo $usage
      echo "Incorrect arguments:  $@"
      exit 1
      ;;
  esac
done

# setup verbose/dryrun rsync options:
rsync_opts="--stats --timeout $rsync_timeout"
if [ $verbose -ne 0 ]; then
  rsync_opts="-vv $rsync_opts"
fi
if [ $dryrun -ne 0 ]; then
  rsync_opts="$rsync_opts --dry-run"
fi

########################################################################
# Convenience functions:
########################################################################

function cleanup {
  rm -f $tmpfile
}
trap cleanup EXIT

function dateit {
  d=`date +%Y-%m-%d\ %H:%M:%S`
  echo "$infomsg $@ - $d" >> $logfile
}

function check_duplicates {
  if [ "$(pgrep -c -u $user -f "rsync.*$user@$remotehost.*$remotepath")" -eq 0 ]; then
      return 0
  fi
  return 1
}

function check_ssh {
  host=$1
  path=$2
  maxtries=10
  tries=0
  while [ 1 ]; do
    let tries=$tries+1
    echo "$infomsg Attempting ssh $host $path, #$tries ... "
    ssh -q $1 ls -d $path > /dev/null
    if [ $? -eq 0 ]; then
      echo "$infomsg ssh success."
      break
    else
      if [ $tries -gt $maxtries ]; then
        echo "$errmsg  ssh failed $maxtries times.  Aborting."
        return 1
      fi
      echo "$warnmsg ssh failed.  Retrying ..."
    fi
    sleep 10
  done
  return 0
}

########################################################################
# Perform some sanity checks and aborts before doing anything:
########################################################################

# abort if incorrect user:
[ $(whoami) != "$user" ] && echo "$errmsg User must be $user." | $tee && exit 2

# abort if incorrect host:
[ $(hostname -s) != "$localhost" ] && echo "$errmsg Must be on $localhost." | $tee && exit 3

# print warning if local disk is getting full:
used_frac=`df $srcdir | tail -1 | awk '{print$5}' | sed 's/%//'`
[ "$used_frac" -gt 80 ] && echo "$warnmsg $srcdir more than 80% full:  $used_frac%" | $tee 

# check we can ssh to remote host and access the destination path:
check_ssh $user@$remotehost $remotepath 2&>1 >> $logfile
[ $? -ne 0 ] && echo "$errmsg ssh $user@$remotehost failed." && exit 55

# abort if already an rsync running:
check_duplicates "rsync.*$user@$remotehost"
[ $? -ne 0 ] && echo "$errmsg rsync $user@$remotehost already running." && exit 66 

########################################################################
# Do the transfers from local $srcdir to remote $dest:
########################################################################

pushd $srcdir > /dev/null

[ $(pwd) != "$srcdir" ] && echo "$errmsg Failed to get to $srcdir." | $tee && exit 10

# transfer *.hipo data files older than some minutes:

dateit FIND HIPO
find . -mindepth 5 -maxdepth 5 -type f -cmin +$rsync_minutes -name '*.hipo' > $tmpfile 2>&1 | $tee
[ $? -ne 0 ] && echo "$errmsg find *.hipo failed, aborting." | $tee && exit 5

if [ -s $tmpfile ]; then

  echo "$infomsg Files to Transfer:" >> $logfile ; cat $tmpfile >> $logfile
  dateit RSYNC HIPO1
  rsync -a -R --files-from=$tmpfile $rsync_opts $srcdir $dest >> $logfile
  [ $? -ne 0 ] && echo "$errmsg rsync *.hipo failed, aborting." | $tee && exit 6

  # first rsync claimed sucess, run it again with local deletion:
  if [ $dryrun -eq 0 ]; then
    dateit RSYNC HIPO2
    rsync -a -R --remove-source-files --files-from=$tmpfile $rsync_opts $srcdir $dest >> $logfile
    [ $? -ne 0 ] && echo "$errmsg rsync *.hipo failed, aborting." | $tee && exit 6
  fi

  # transfer the top-level nodeScript.sh from each submission:
  # (one day we can remove this, after job specifications are in HIPO)

  dateit FIND SCRIPT
  find . -mindepth 3 -maxdepth 3 -type f -cmin +$rsync_minutes -name 'nodeScript.sh' > $tmpfile 2>&1 | $tee
  [ $? -ne 0 ] && echo "$errmsg find nodeScript failed, aborting." | $tee && exit 7

  if [ -s $tmpfile ]; then
    dateit RSYNC SCRIPT
    rsync -a -R --files-from=$tmpfile $rsync_opts $srcdir $dest >> $logfile
    [ $? -ne 0 ] && echo "$errmsg rsync nodeScript failed, aborting." | $tee && exit 8
  fi

else
  echo "$infomsg No Files to Transfer." >> $logfile
fi

popd > /dev/null

########################################################################
# Cleanup old stuff on local $srcdir filesystem:
########################################################################

# minimize finds, reduce to a single crawl for deletions:
opts="-path $srcdir -delete $delete_days -empty $delete_days -trash 2"
if [ $dryrun -ne 0 ]; then
    opts="$opts -dryrun"
fi
dateit CLEANUP
echo "$infomsg Files to Delete:" >> $logfile
$dirname/disk-cleanup.py $opts 2>&1 >> $logfile
[ $? -ne 0 ] && echo "$errmsg disk-cleanup.py failed." | $tee

########################################################################
# Done
########################################################################

[ $dryrun -ne 0 ] && cat $logfile

dateit DONE
exit 0

