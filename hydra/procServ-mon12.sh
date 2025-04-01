#!/bin/bash
export JAVA_HOME=/usr/clas12/offline/jdk/21.0.2
export CCDB_CONNECTION=mysql://clas12reader@clondb1.jlab.org/clas12
export PATH=$JAVA_HOME/bin:$PATH
procServ -n hydra-mon12 -i^D^C --logfile /local/baltzell/hydra/logs/mon12.log --logstamp -c /home/baltzell/hydra/mon12 20002 ./bin/mon12_hydra

