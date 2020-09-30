#!/bin/bash

cd `dirname $0`

export PYTHONPATH=/group/clas12/packages/mysql-connector/8.0.17/lib

rm -f index.html cache.html hps-volatile.html hps-cache.html

./volatile_html.py >& index.html
scp index.html clas12@jlabl5:~/clasweb/clas12offline/disk/volatile

./cache_html.py >& cache.html
scp cache.html clas12@jlabl5:~/clasweb/clas12offline/disk/cache/index.html

./volatile_html.py /volatile/hallb/hps >& hps-volatile.html
scp hps-volatile.html hps@ifarm1901:/group/hps/www/hpsweb/html/disk/volatile/index.html

# doing it from /cache/hallb/hps doesn't work, probably need to modify query
./cache_html.py /cache/hallb >& hps-cache.html
scp hps-cache.html hps@ifarm1901:/group/hps/www/hpsweb/html/disk/cache/index.html

