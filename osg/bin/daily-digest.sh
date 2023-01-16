#!/bin/bash

recipients='baltzell@jlab.org ungaro@jlab.org devita@jlab.org mckinnon@jlab.org'

dirname="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"

mkdir -p /osgpool/hallb/clas12/gemc/daily
timestamp=$(date +%Y%m%d_%H%M%S)
plotfile=$(mktemp /osgpool/hallb/clas12/gemc/daily/$timestamp\_XXXXXX.pdf)
emailbody=$(mktemp /osgpool/hallb/clas12/gemc/daily/$timestamp\_XXXXXX.txt)
touch $emailbody
plotfilelogscale=${plotfile%%.*}-logscale.pdf

cvmfs_cache=$HOME/cvmfs-errors.txt
vacate_cache=$HOME/vacate-stalls.txt
xrootd_cache=$HOME/xrootd-errors.txt

function munge {
    # 1. remove username, keeping only site, host, and job ids
    # 2. sort and remove uniques, i.e. same host and job id
    # 3. count per host and sort by counts
    if [ -e $1 ]
    then
        sed 's/@/ /g' $1 | awk '{print$1,$(NF-1),$NF}' | sort | uniq | awk '{print$1,$2}' | sort | uniq -c | sort -n -r
    fi
}

echo Nodes with CVMFS issues in the past 24 hours: >> $emailbody
munge $cvmfs_cache >> $emailbody
echo  >> $emailbody

echo Nodes with XRootD issues in the past 24 hours: >> $emailbody
munge $xrootd_cache >> $emailbody
echo >> $emailbody

echo Vacated jobs in the past 24 hours: >> $emailbody
munge $vacate_cache >> $emailbody
echo >> $emailbody

rm -f $cvmfs_cache $xrootd_cache $vacate_cache

export DISPLAY=:0.0
source /cvmfs/sft.cern.ch/lcg/app/releases/ROOT/6.26.04/x86_64-centos8-gcc85-opt/bin/thisroot.sh

$dirname/condor-probe.py -completed -hours 24 -plot $plotfile >& /dev/null

cat $emailbody | mail -a $plotfile -a $plotfilelogscale -s OSG-CLAS12-Daily-Digest $recipients

