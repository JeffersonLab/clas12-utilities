set sourced=($_)
set d=`/usr/bin/readlink -f $sourced[2]`
set d=`/usr/bin/dirname $d`
setenv PYTHONPATH ${d}:/usr/local/src/rcdb/python:${PYTHONPATH}
setenv PATH ${d}:${PATH}
