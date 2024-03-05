#!/bin/bash
DISK=/w/hallb-scshelf2102/clas
OUTDIR=$HOME/disk/clas-`date +%Y%m%d`
SCRIPTDIR=`dirname $0`
LIMIT=30

# what's this for, probably perl or python?
export PATH=/apps/bin:${PATH}

mkdir -p $OUTDIR
cd $OUTDIR

touch log
echo "STARTING ..." >> log
date >> log

$SCRIPTDIR/disk-database.pl $DISK clas >& clas.log
$SCRIPTDIR/disk-report.pl clas 30 > index.html

du -s $DISK/* 2> perms.txt 1> du.txt
awk -F'[‘’]' '{print$2}' ./perms.txt > perms2.txt
sort -r -n du.txt | awk '{printf"%12s %s\n",$1,$2}' > du2.txt
mv -f du2.txt du.txt
mv -f perms2.txt perms.txt

scp -q *.txt *.html jlabl5:~/public_html/clas/disk/work

echo "FINISHED." >> log
date >> log

