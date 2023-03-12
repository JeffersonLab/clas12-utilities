#!/bin/bash

usage='transfer-logs.sh USER GEMCID'

local_dir=/osgpool/hallb/clas12/gemc/$1/job_$2/log
remote_dir=/work/clas12/osg2/$1/job_$2/log

if [ -z $2 ]
then
    echo $usage
    exit 1
fi

if ! [ -d $local_dir ]
then
    echo $usage
    echo Nonexistent directory: $local_dir
    exit 1
fi

mkdir -p $remote_dir

[ $? -ne 0 ] && echo "Error making directory $remote_dir" && exit

rsync -avz $local_dir/ ifarm1901:$remote_dir/

