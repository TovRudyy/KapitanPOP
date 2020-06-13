# KapitanPOP

Engine to generate POP perfomance metrics and translate Paraver (.prv, .row, .pcf) files into HDF5 file format.

## Quick Usage

To take a look to the available options and funcionalities:
```
$python kapitanPOP.py --help
```

To generate a _.csv_ file with POP metrics:

```
$python kapitanPOP.py trace.prv
```

To translate a Paraver trace to HDF5:

```
$python kapitanPOP.py -p trace1.prv
```

### Installation
Before using KapitanPOP you will need to install some dependencies and compile a small binary
#### Dependencies:
* [HDF5 library](https://www.hdfgroup.org/) 1.12.0 release - C/Fortran library to store data on disk in HDF5 file format
* [Pandas](https://pandas.pydata.org/) - Python module for data analysis
* [Numpy](https://numpy.org/) - Package for scientific computing in Python
* [Dask](https://dask.org/) the version from [GitHub's](https://github.com/dask/dask) master branch - Parallel computing library for Python
* [H5py](https://www.h5py.org/) - HDF5 for Python
* [PyTables](https://www.pytables.org/) Package used by Dask to manage datasets from HDF5 files
* [Dimemas](https://tools.bsc.es/downloads) - Network simulator tool for message-passing programs

You should be able to install **Pandas**, **Numpy**, **h5py** and **PyTables** on your computer very easyly using **pip install**, for example.
```
pip install pandas numpy h5py tables
```
or, more easily
```
pip install -r requirements.txt
```
To install **HDF5-1.12.0** the best approach is to download the [sources](https://portal.hdfgroup.org/display/support/HDF5+1.12.0) 
and install them on your computer:

For **Dask** you must install it from source from its master branch on [GitHub](https://github.com/dask/dask) 
because the latest releases have some issues related to HDF5.

**Dimemas** is not a key dependency. You can run KapitanPOP without it, but you will miss some performance metrics 
(transfer and serialization efficiency).

#### Compilation

After installing C/Fortran HDF5 library, you can run the Makefile to compile KapitanPOP's Paraver traces parser.
```
make install
```
It will generate an error if your HDF5 installation is not in a standard system directory. You can export the 
variable *HDF5_HOME* with the path where the library was installed, or modify the include and library paths in the Makefile
to avoid the error.

Once the Paraver parser is generated and Python's dependencies satisfied, you are set up to execute *kapitanPOP.py*.

## Functionalities

- Parsing of Paraver trace files (currently only .prv and .row) into the HDF5 file format.
- Generation of a CSV file with the available POP metrics from a list of Paraver or parsed HDF5 files.


