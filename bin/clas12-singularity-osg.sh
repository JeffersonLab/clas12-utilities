singularity shell --home ${PWD}:/srv --pwd /srv --bind /cvmfs --contain --cleanenv \
      --ipc --pid /cvmfs/singularity.opensciencegrid.org/jeffersonlab/clas12software:production
