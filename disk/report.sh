#!/bin/bash

DISK=/work/clas12
OUTDIR=$HOME/disk/`date +%Y%m%d`
SCRIPTDIR=`dirname $0`
LIMIT=30

mkdir -p $OUTDIR
cd $OUTDIR

touch log
echo "STARTING ..." >> log
date >> log

for xx in rg-a rg-b rg-c rg-d rg-e rg-f rg-k rg-m users
do
    indir=$DISK
    if [ $xx == "users" ]
    then
        cmd=$SCRIPTDIR/disk-database-users.pl
    else
        indir=$indir/$xx
        cmd=$SCRIPTDIR/disk-database.pl
    fi
    rm -f $xx.log $xx.html
    $cmd $indir/ ${xx/-/} >& $xx.log
    $SCRIPTDIR/disk-report.pl ${xx/-/} $LIMIT > $xx.html
done

rm -f du.txt du2.txt perms.txt perms2.txt
du -s $DISK/* 2> perms.txt 1> du.txt
du -s $DISK/users/* 2> permsA.txt 1> duA.txt
cat duA.txt >> du.txt
awk -F'[‘’]' '{print$2}' ./perms.txt > perms2.txt
df $DISK > du2.txt
sort -r -n du.txt | awk '{printf"%12s %s\n",$1,$2}' >> du2.txt
mv -f du2.txt du.txt
rm -f duA.txt permsA.txt
echo 'These private directories occupy an unknown amount of disk space:' > perms.txt
echo '   ("chgrp clas12" and "chmod -R g+r" to fix it)' >> perms.txt
echo >> perms.txt
cat perms2.txt >> perms.txt
rm -f perms2.txt

scp -q -p perms.txt du.txt rg-?.html users.html clas12@ifarm:/u/group/clas/www/clasweb-2015/html/clas12offline/disk/work

echo "FINISHED." >> log
date >> log

