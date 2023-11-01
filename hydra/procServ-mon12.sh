#!/bin/bash
export CCDB_CONNECTION=mysql://clas12reader@clondb1.jlab.org/clas12
procServ -n hydra-mon12 -i^D^C --logfile /local/baltzell/hydra/logs/mon12.log --logstamp -c /home/baltzell/mon12 20002 ./bin/mon12_hydra

