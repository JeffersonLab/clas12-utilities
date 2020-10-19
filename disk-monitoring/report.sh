#!/bin/bash

# this doesn't work in a cron job, due to x-display
#!/bin/bash -l

# this doesn't work without a login shell, due to module command:
#source /site/env/sysprofile

# so just do this:
export PATH=/apps/bin:${PATH}

limit=30

outdir=`dirname $0`/`date +%Y%m%d`
mkdir $outdir
cd $outdir

touch log
echo "STARTING ..." >> log
date >> log

for xx in rg-a rg-b rg-k users
do
    indir=/work/clas12
    if [ $xx == "users" ]
    then
        cmd=../disk-database-users.pl
    else
        indir=$indir/$xx
        cmd=../disk-database.pl
    fi
    rm -f $xx.log $xx.html
    $cmd $indir/ ${xx/-/} >& $xx.log
    ../disk-report.pl ${xx/-/} $limit > $xx.html
done

rm -f du.txt du2.txt perms.txt perms2.txt
du -s /work/clas12/* /work/clas12/users/* 2> perms.txt 1> du.txt
awk -F'[‘’]' '{print$2}' ./perms.txt > perms2.txt
sort -r -n du.txt | awk '{printf"%12s %s\n",$1,$2}' > du2.txt
mv -f du2.txt du.txt
echo 'These private directories occupy an unknown amount of disk space:' > perms.txt
echo '   ("chgrp clas12" and "chmod -R g+r" to fix it)' >> perms.txt
echo >> perms.txt
cat perms2.txt >> perms.txt
rm -f perms2.txt

scp -p *.txt *.html clas12@ifarm1901:~/clasweb/clas12offline/disk/work

echo "FINISHED." >> log
date >> log

