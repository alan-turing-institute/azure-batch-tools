#!/bin/bash
sudo apt-get --yes --force-yes  update
#sudo apt-get upgrade #no need for the safety of this
sudo apt-get --yes --force-yes dist-upgrade
# Install python stuff we use
sudo apt --yes --force-yes install python-pip
sudo -H pip install --upgrade azure-servicebus azure-storage
# Add juliareleases Personal Package Archive (PPA)
sudo add-apt-repository --yes ppa:staticfloat/juliareleases
sudo apt-get --yes --force-yes update
sudo apt-get --yes --force-yes install julia=0.5*

# Install PDMP Julia Package
julia -e 'Pkg.clone("git://github.com/alan-turing-institute/PDMP.jl.git")'
julia -e 'Pkg.update("PDMP")'

sudo apt-get --yes --force-yes install hdf5-tools
julia -e 'Pkg.add("JLD")'