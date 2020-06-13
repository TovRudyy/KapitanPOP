Bootstrap: docker
From: ubuntu:20.04

%labels
MAINTAINER TovRudyy

%setup
    mkdir -p ${SINGULARITY_ROOTFS}/opt

%environment
    KAPITANPOP_HOME=/opt/KapitanPOP
    HDF5_HOME=/opt/hdf5-hdf5-1_12_0/install
    DASK_HOME=/opt/dask-2.18.1
    PATH=/opt/KapitanPOP:/opt/KapitanPOP/bin:/opt/dimemas-5.4.2-Linux_x86_64/bin:$PATH

%post
    # Basic OS packages
    apt-get update
    apt-get install -y build-essential python3 python3-pip python3-dev git wget vim
    ln -s /usr/bin/python3 /usr/bin/python && ln -s /usr/bin/pip3 /usr/bin/pip

    # Download & install HDF5-1.12.0
    cd /opt && wget -nv https://github.com/HDFGroup/hdf5/archive/hdf5-1_12_0.tar.gz
    tar -xf hdf5-1_12_0.tar.gz
    cd hdf5-hdf5-1_12_0 && mkdir -p build install
    HDF5_ROOT=/opt/hdf5-hdf5-1_12_0/install
    cd build
    ../configure --prefix=$HDF5_ROOT --enable-shared --enable-optimization=high
    make -j 4 install
    export HDF5_HOME=/opt/hdf5-hdf5-1_12_0/install

    # Donwload & install Dask master
    cd /opt && git clone https://github.com/dask/dask.git
    cd dask
    DASK_HOME=/opt/dask
    python -m pip install ".[complete]"

    # Download & install Dimemas
    cd /opt && wget -nv https://ftp.tools.bsc.es/dimemas/dimemas-5.4.2-Linux_x86_64.tar.bz2
    tar -xvf dimemas-5.4.2-Linux_x86_64.tar.bz2

    # Download & install KapitanPOP
    cd /opt && git clone https://github.com/TovRudyy/KapitanPOP.git
    cd KapitanPOP
    pip install -r requirements.txt
    mkdir -p obj bin
    make
    chmod +x kapitanPOP.py






