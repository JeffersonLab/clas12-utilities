#!/bin/sh

# setup environment:
source /scigroup/cvmfs/hallb/clas12/sw/setup.sh
module load clas12

# define snapshot paths:
snapshotDir=/group/clas12/packages/local/share/ccdb/sqlite
snapshot=$snapshotDir/ccdb_`date +%F`.sqlite
webDir=/group/clas/www/clasweb/html/clas12offline/sqlite/ccdb

# generate the snapshot:
rm -f $snapshot
clas12-ccdb-mysql2sqlite.py $snapshot

snapshotSize=$(stat -c%s $snapshot)

if [ $snapshotSize == "" ] || [ $snapshotSize -lt 10 ]
then
  echo 'Error making ccdb snapshot.' >&2
  rm -f $snapshot
  exit
fi

# update link to the latest:
cd $snapshotDir
ln -s -f ${snapshot##*/} latest.sqlite
rm -f LATEST ; tmp=${snapshot##*/}; tmp=${tmp%%.*}; tmp=${tmp##*_}; echo $tmp > LATEST
cd -

# delete snapshots older than 30 days:
find $snapshotDir -maxdepth 1 -name "*.sqlite" -type f -mtime +30 -exec rm -f {} \;

# rsync to web directory:
rsync -av --delete $snapshotDir/ $webDir/

# copy latest to CVMFS:
cp -p -f -L $snapshotDir/latest.sqlite /scigroup/cvmfs/hallb/clas12/sw/noarch/data/ccdb/ccdb_latest.sqlite

