#!/bin/bash

echo 'MON12 WATCHDOG'
run_number=-1

# mon12's functionality is spread across multiple repositories,
# with build systems that only support remote dependencies.  So
# updating logic and testing and using it, e.g. automatically
# reconnecting to the ET ring when it's restarted, is cumbersome
# and we do this kludge instead for now.

# If run number is good and new, and daq status is running,
# and beam current non-zero, then return the new run number:
function check() {
   run=$(caget -t -w 1 B_DAQ:run_number)
   sta=$(caget -t -w 1 B_DAQ:coda_status | awk '{print$1}')
   cur=$(caget -t -w 1 IPM2C21A)
   cur=${cur%%.*}
   [ $run -lt 100000 ] || return
   [ $run -gt 0 ] || return
   [ $cur -gt 1 ] || return
   [ $sta == "running" ] || return
   [ $run != $run_number ] || return
   echo $run
}

while [ 1 ]
do
    run=$(check)
    if [ "$run" != "" ]
    then
        run_number=$run
        echo "RESTARTING MON12 ..."
        date
        echo 18 | xxd -r -p | nc localhost 20002
    fi
    sleep 5
done

