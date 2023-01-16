#!/bin/bash

d=`/usr/bin/readlink -f $0`
d=`/usr/bin/dirname $d`

$d/condor-probe.py -timeline
$d/check-cvmfs.sh
$d/check-xrootd.sh
$d/vacate-stalls.sh

