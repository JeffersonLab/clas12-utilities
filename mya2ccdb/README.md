# new

fcup-calib.py

Python module ependencies:
* requests
* pandas
* rcdb

# old

Extract Faraday cup offset and half-wave plate position from Mya archive and create .txt files for CCDB.

Requires Mya archive access from command line tools, so must be behind hallgw firewall.  Written before HTTP queries existed, would be good to switch to that.

To open myaPlot with the appropriate PVs, see configuration file BLINE/fcup-calib-2

To run, make a new directory, source the env.(c)sh file, and run mya2ccdb.py with the appropriate start/end date arguments for a given run period.

Currently upperlimit of last run range is infinite.  This is only appropriate for the most recent run period and needs to be manually adjusted.

