#!/bin/bash

DISK=/work/hallb/hps
OUTDIR=$HOME/disk/hps-`date +%Y%m%d`
SCRIPTDIR=`dirname $0`
LIMIT=30

mkdir -p $OUTDIR
cd $OUTDIR

touch log
echo "STARTING ..." >> log
date >> log

rm -f hps.log hps.html data.log data.html

$SCRIPTDIR/disk-database.pl $DISK/ hps >& hps.log
$SCRIPTDIR/disk-report.pl hps $LIMIT > hps.html

$SCRIPTDIR/disk-database.pl $DISK/data/ hpsdata >& hpsdata.log
$SCRIPTDIR/disk-report.pl hpsdata $LIMIT > hpsdata.html

rm -f du.txt du2.txt perms.txt perms2.txt

du -s $DISK/* $DISK/data/* 2> perms.txt 1> du.txt

awk -F'[‘’]' '{print$2}' ./perms.txt > perms2.txt

sort -r -n du.txt | awk '{printf"%12s %s\n",$1,$2}' > du2.txt

mv -f du2.txt du.txt

echo 'These private directories occupy an unknown amount of disk space:' > perms.txt
echo '   ("chgrp hps" and "chmod -R g+r" to fix it)' >> perms.txt
echo >> perms.txt
cat perms2.txt >> perms.txt
rm -f perms2.txt

scp -q perms.txt du.txt hps.html hps@ifarm1901:/group/hps/www/hpsweb/html/disk/work/

echo "FINISHED." >> log
date >> log

