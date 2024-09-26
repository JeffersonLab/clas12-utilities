#!/bin/bash -l

# use the same mysql.connector that you get via ccdb:
module use /scigroup/cvmfs/hallb/clas12/sw/modulefiles
module load -s ccdb

dir=$(cd $(dirname $0) && pwd -P)

clas=/group/clas/www/clasweb/html/clas12offline/disk
hps=/group/hps/www/hpsweb/html/disk

mkdir -p $HOME/disk/tmp
cd $HOME/disk/tmp
rm -f index.html cache.html hps-volatile.html hps-cache.html

$dir/volatile_html.py -d $@ >& index.html

scp -q index.html clas12@ifarm:$clas/volatile

$dir/cache_html.py >& cache.html
scp -q cache.html clas12@ifarm:$clas/cache/index.html

#$dir/volatile_html.py $@ /volatile/hallb/hps >& hps-volatile.html
#scp -q hps-volatile.html hps@ifarm:$hps/volatile/index.html

# doing it from /cache/hallb/hps doesn't work, probably need to modify query
#$dir/cache_html.py /cache/hallb >& hps-cache.html
#scp -q hps-cache.html hps@ifarm:$hps/cache/index.html

