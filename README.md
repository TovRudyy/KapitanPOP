# KapitanPOP

Refractor of BSC's performance analysis tools to generate fundamental POP metrics.

## Description

KapitanPOP is an effort to refractor and enchance BSC's performance analysis tools (Paraver, Dimemas, BasicAnalysis) in order to leverage present technologies. With the usage of nowaday's libraries for fast I/O, data analysis and distributed programming KapitanPOP offers the same funcionalities as BSC's Basic Analysis framework, but in a scalable wayt with better performances and less memory consumption. 

KaptainPOP has 2 ultimate goals: to ease the work of HPC application performance analysts within the POP project, enabling faster efficiency metrics obtention , and the proof-of-concept of promising libraries and technologies for the sake of trace analysis, which in the end is nothing else than pure data analysis. 

## Installation

You can install KapitanPOP in two ways: using Singularity containers and downloading KapitanPOP's image from the cloud; or manual installation. I strongly recommend using KapitanPOP through Singularity containers because installing manually the dependencies can be frustrating. 

### Through Singularity

After installing Singularity containers on your computer you only have to pull KapitanPOP's image from its Singularity Hub repository and run it.
```
$singularity pull shub://TovRudyy/KapitanPOP
$singularity shell KapitanPOP_latest.sif
```
You can also build the image directly on your computer using the available [Singularity](Singularity) recipe.

```
$sudo singularity build KapitanPOP.sif Singularity
```

### Through manual installation

First of all, you will have to install the next dependencies:

* [HDF5 library](https://www.hdfgroup.org/) 1.12.0 release - C/Fortran library to store data on disk in HDF5 file format. Release 1.10.0 also should work
* [Pandas](https://pandas.pydata.org/) - Python module for data analysis
* [Numpy](https://numpy.org/) - Package for scientific computing in Python
* [Dask](https://dask.org/) the version from [GitHub's](https://github.com/dask/dask) master branch - Parallel computing library for Python. Very important to install it from the master branch
* [H5py](https://www.h5py.org/) - HDF5 for Python
* [PyTables](https://www.pytables.org/) - Package used by Dask to manage datasets from HDF5 files
* [Dimemas](https://tools.bsc.es/downloads) (optional) - Network simulator tool for message-passing programs

You should be able to install **Pandas**, **Numpy**, **h5py** and **PyTables** on your computer very easyly using **pip install**, for example:
```
pip install pandas numpy h5py tables
```
or easier:
```
pip install -r requirements.txt
```
To install **HDF5-1.12.0** the best approach is to download the [sources](https://portal.hdfgroup.org/display/support/HDF5+1.12.0) and install them on your computer.

For **Dask** you must install it from source from its master branch on [GitHub](https://github.com/dask/dask) 
because the latest releases have some issues related to HDF5.

**Dimemas** is not a key dependency. You can run KapitanPOP without it, but you will miss some performance metrics 
(transfer and serialization efficiency).

After the dependencies are satisfied, you can install KapitanPOP. You might need to modify the Makefile if your HDF5 libraries are not installed in a standard system path. 

```
$git clone https://github.com/TovRudyy/KapitanPOP.git
cd KapitanPOP
mkdir -p obj bin
make
```
**IMPORTANT**: KapitanPOP does not work with gcc10.

## Current Functionalities

### Parsing of Paraver trace files into HDF5 file format

KapitanPOP can read data from .row and .prv files and write it into an equivalent HDF5 file. For this, a little C program to parse .prv files is used. The resulting HDF5 file contains all the data of the original Paraver file, but in a tabular format divided in dataframes of States, Events and communications. The resulting HDF5 contains an equivalent version of the .row and .prv data in a more convenient way for fast I/O.


### Metrics computation of te multiplicative POP model

KapitanPOP can generate an identic CSV file as the original modelfactors with POP metrics of te multiplicative model:

* Parallel efficiency
* Load balance
* Communication efficiency
* Serialization efficiency
* Transfer efficiency
* Computation scalability
* Global efficiency
* IPC scalability
* Frequency scalability
* Speedup

And the data where those metrics come from:

* Average useful IPC
* Average useful frequency
* Runtime
* Runtime (ideal)
* Useful duration
* Useful duration (ideal)
* Useful instructions
* Useful cycles

## Usage

A quick help is available running: ```./kapitanPOP.py --help```

To generate a modelfactors.csv file with POP metrics: ```./kapitanPOP.py trace1.prv trace2.prv trace3.prv ...``` 

It also accepts regex expressions. By default it will not simulate the application execution on an ideal network. To enable the compute of ideal performance metrics (transfer & serialization efficiency) you will have to add the ```--dim``` option flag: ```/kapitanPOP.py --dim trace...```

To only parse a Paraver trace (.row and .prv files) into an equivalent HDF5 file: ```./kapintanPOP.py -p trace.prv```

You can tune how the parser performs in order to limit the maximum memory and disk usage. By default, the parser process the .prv file in chunks of 1GB and does not apply compression to the resuling HDF5. You can can change those setting with ```--chunk_size``` and ```--comp_lvl``` option flags. 

**IMPORTANT**: curently the parsed file is between two and three times bigger than the original Paraver file. This is a necessary trade-off for a better memory usage and speeds when analysing the trace. If your computer has limited disk space, you should run KapitanPOP with ```--comp_lvl 1``` (compression level 1). This will notably reduce the size of the file (between 5 and 10 times less), though the parse time will increase in exchange.

 ## TODO

* Implement a .pcf parser
* Implement the additive model
* Improve execution times and memory usage when analysing traces (kapitanPOP.py)
* Benchmark KapitanPOP
* Proof-of-concept running KapitanPOP using multiples nodes through Dask
