#!/bin/bash -l

# setup environment:
module use /scigroup/cvmfs/hallb/clas12/sw/modulefiles
module load -s clas12

# define snapshot paths:
snapshotDir=/group/clas12/packages/local/share/rcdb/sqlite
snapshot=$snapshotDir/rcdb_`date +%F`.sqlite
webDir=/group/clas/www/clasweb/html/clas12offline/sqlite/rcdb

# generate the snapshot:
rm -f $snapshot
clas12-rcdb-mysql2sqlite.py $snapshot

snapshotSize=$(stat -c%s $snapshot)

if [ $snapshotSize == "" ] || [ $snapshotSize -lt 10 ]
then
  echo 'Error making rcdb snapshot.' >&2
  rm -f $snapshot
  exit
fi

# update link to the latest:
cd $snapshotDir
ln -s -f ${snapshot##*/} latest.sqlite
rm -f LATEST ; tmp=${snapshot##*/}; tmp=${tmp%%.*}; tmp=${tmp##*_}; echo $tmp > LATEST
cd -

# delete snapshots older than 7 days:
find $snapshotDir -name "*.sqlite" -type f -mtime +7 -exec rm -f {} \;

# rsync to web directory:
rsync -av --delete $snapshotDir/ $webDir/

# copy latest to CVMFS:
cp -p -f -L $snapshotDir/latest.sqlite /scigroup/cvmfs/hallb/clas12/sw/noarch/data/rcdb/rcdb_latest.sqlite

