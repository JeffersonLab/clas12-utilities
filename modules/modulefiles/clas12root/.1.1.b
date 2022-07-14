#%Module1.0
proc ModulesHelp { } {
    puts stderr "This module sets up environment for clas12root"
}
module-whatis   "clas12root 1.1.b"

conflict clas12root

module load root/6.14.04
module load hipo/1.1

set version 1.1.b

setenv CLAS12ROOT /group/clas12/packages/clas12root/$version

prepend-path PATH $env(CLAS12ROOT)/bin
prepend-path LD_LIBRARY_PATH $env(CLAS12ROOT)/lib

