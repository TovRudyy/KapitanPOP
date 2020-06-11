import json
import os
import subprocess
from typing import Dict, List
from datetime import datetime

import h5py
import dask.dataframe as dd
import numpy as np

from src.Trace import TraceMetaData, Trace

HDF5_ROOT = "/"
HDF5_RECORDS = "/RECORDS"
HDF5_STATES_DF = "STATES"
HDF5_EVENTS_DF = "EVENTS"
HDF5_COMMS_DF = "COMMUNICATIONS"

HDF5_METADATA_NAME = "metName"
HDF5_METADATA_PATH = "metPath"
HDF5_METADATA_TYPE = "metType"
HDF5_METADATA_EXEC_TIME = "metTime"
HDF5_METADATA_DATE = "metDate"
HDF5_METADATA_NODES = "metNodes"
HDF5_METADATA_APPS = "metApps"
HDF5_METADATA_HWCPU = "metHwcpu"
HDF5_METADATA_HWNODES = "metHwnodes"
HDF5_METADATA_THREADS = "metThreads"

BIN_UTILS_PATH = "utils/bin"
PRV_PARSER_BIN = BIN_UTILS_PATH + "prv_parser"
PARAVER_FILE = "Paraver (.prv)"
PARAVER_MAGIC_HEADER = "#Paraver"

# Default prv_parser arguments
default_args = {'--chunk_size': 1024,
                '--comp_lvl': 0}


def try_read_hdf5(hdf5_file, key) -> dd.DataFrame:
    """Try to load the .h5 file as a Dask DataFrame."""
    try:
        return dd.read_hdf(hdf5_file, key=key)
    except ValueError:
        print(f'==WARNING== Could not recover Table {key} as DaskDataframe.')
        return dd.from_array(np.array([[]]))


def load(trace_file: str, args: Dict ={}) -> Trace:
    """Reads the trace file provided. It it is a .prv it will parse it before
    loading it to memory."""
    if trace_file[-4:] == ".prv":
        print(f'==INFO== Parsing prv file {trace_file}')
        trace_hdf5_file = file_parser(trace_file, args)
    elif trace_file[-3:] == ".h5":
        trace_hdf5_file = trace_file
    else:
        print(f'==ERROR== File {trace_file} is not valid.')
        return None

    with h5py.File(trace_hdf5_file, "r") as f:
        metadata = f[HDF5_ROOT]
        trace_metadata = TraceMetaData(
            metadata.attrs[HDF5_METADATA_NAME],
            metadata.attrs[HDF5_METADATA_PATH],
            metadata.attrs[HDF5_METADATA_TYPE],
            metadata.attrs[HDF5_METADATA_EXEC_TIME],
            datetime.strptime(metadata.attrs[HDF5_METADATA_DATE], "%Y-%m-%dT%H:%M:%S"),
            metadata.attrs[HDF5_METADATA_NODES],
            json.loads(metadata.attrs[HDF5_METADATA_APPS]),
            metadata[HDF5_METADATA_HWCPU][0][:].tolist(),
            metadata[HDF5_METADATA_HWNODES][0][:].tolist(),
            metadata[HDF5_METADATA_THREADS][0][:].tolist()
        )
    df_states = try_read_hdf5(trace_hdf5_file, key=HDF5_RECORDS + "/" + HDF5_STATES_DF)
    df_events = try_read_hdf5(trace_hdf5_file, key=HDF5_RECORDS + "/" + HDF5_EVENTS_DF)
    df_comms = try_read_hdf5(trace_hdf5_file, key=HDF5_RECORDS + "/" + HDF5_COMMS_DF)

    return Trace(trace_metadata, df_states, df_events, df_comms)

def get_num_processes(trace_file: str) -> int:
    """Returns the number of processes of the trace either by reading its .row file
     or accessing the metadata."""
    cpus = 0
    if trace_file.endswith('.prv'):
        cpus = int(open(f'{trace_file[:-4]}.row').readline().rstrip().rstrip().split(' ')[3])
    elif trace_file.endswith('.h5'):
        with h5py.File(trace_file, 'r') as trace:
            cpus = len(trace[HDF5_ROOT][HDF5_METADATA_HWCPU])
    else:
        print(f'==ERROR== File {trace_file} has not valid extension.')

    return cpus


def wrapper_prv_parser(file: str, args: Dict) -> str:
    """Invokes the C prv_parser with the right arguments."""
    cmd = [os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bin/prv_parser')]

    # Checks verbosity argument
    if '--verbose' in args:
        cmd.append('--verbose')
    # Checks chunk_size argument
    if '--chunk_size' in args:
        cmd.append(f'--chunk_size={args["--chunk_size"]}')
    else:
        cmd.append(f'--chunk_size={default_args["--chunk_size"]}')
    # Checks comp_lvl argument
    if '--comp_lvl' in args:
        cmd.append(f'--comp_lvl={args["--comp_lvl"]}')
    else:
        cmd.append(f'--comp_lvl={default_args["--comp_lvl"]}')
    # Inserts the right output file
    output_file = file[:-4] + '.h5'
    cmd.append(f'--output={output_file}')
    # Inserts original prv trace
    cmd.append(file)

    returncode = subprocess.run(cmd)

    if returncode.returncode == 0:
        return output_file
    else:
        return ''


def header_time(header: str) -> int:
    """Returns total execution time (us) contained in the header."""
    try:
        time_ns, _, other = header[header.find("):") + 2:].partition("_ns")  # Originally it's in ns
        time = int(time_ns) // 1000
    except ValueError:
        print(f'==WARNING== Could not parse the time of the header.')
        time = 0
    return time

def header_date(header: str) -> datetime:
    """Returns the contained date in the header."""
    date, _, other = header.replace("#Paraver (", "").replace("at ", "").partition("):")
    try:
        date = datetime.strptime(date, "%d/%m/%Y %H:%M")
    except ValueError:
        date = datetime.strptime(datetime.today().strftime("%d/%m/%Y %H:%M"), "%d/%m/%Y %H:%M")
        print(f'==WARNING== Could not parse the date of the header.')
    return date


def header_nodes(header: str) -> List[int]:
    """Returns a list telling how many CPUs has each Node.
    Origin machine's architectural information."""
    try:
        nodes = header[header.find("_ns:") + 4:]
        if nodes[0] == "0":
            nodes = None
        else:
            nodes = nodes[nodes.find("(") + 1: nodes.find(")")]
            nodes = nodes.split(",")
            nodes = list(map(int, nodes))
    except ValueError:
        nodes = []
        print('==WARNING== Could not parse the node information of the header')
    return nodes

def header_apps(header: str) -> List[List[Dict]]:
    """Returns a structure telling the threads/Node mappings of each task."""
    apps_list = []
    try:
        apps = header[header.find("_ns:") + 4:]
        apps, _, other = apps.partition(":")
        apps, _, other = other.partition(":")
        number_apps = int(apps)
        i = 0
        while i < number_apps:
            apps, _, other = other.partition("(")
            number_tasks = int(apps)
            apps, _, other = other.partition(")")
            apps = apps.split(",")
            j = 0
            tasks_list = []
            while j < number_tasks:
                tmp = list(map(int, apps[j].split(":")))
                tasks_list.append(dict(nThreads=tmp[0], node=tmp[1]))
                j += 1
            apps_list.append(tasks_list)
            i += 1
            apps, _, other = other.partition(":")
    except ValueError:
        print("==WARNING== Could not trace app's information of the header")

    return apps_list

def header_parser(header: str) -> (int, datetime, List[int], List[List[Dict]]):
    """Parses important fields of the header one by one."""
    time = header_time(header)
    date = header_date(header)
    nodes = header_nodes(header)
    apps = header_apps(header)
    return time, date, nodes, apps


def row_parser(row_file: str) -> (np.array, np.array, np.array):
    """Parses the .row file returning a list with the CPUs, nodes and threads names."""
    try:
        with open(row_file, "r") as f:
            lines = f.read().split("\n")
            gen = (i for i, s in enumerate(lines) if ("LEVEL CPU SIZE" or "LEVEL TASK SIZE") in s)
            index = next(gen)
            cpu_size = int(lines[index].split()[3])
            cpu_list = lines[index + 1: index + cpu_size + 1]
            # HDF5 for python only supports string in ASCII code
            cpu_list = [name.encode("ascii", "ignore") for name in cpu_list]
            gen = (i for i, s in enumerate(lines) if "LEVEL NODE SIZE" in s)
            index = next(gen)
            node_size = int(lines[index].split()[3])
            node_list = lines[index + 1: index + node_size + 1]
            node_list = [name.encode("ascii", "ignore") for name in node_list]
            gen = (i for i, s in enumerate(lines) if "LEVEL THREAD SIZE" in s)
            index = next(gen)
            thread_size = int(lines[index].split()[3])
            thread_list = lines[index + 1: index + thread_size + 1]
            thread_list = [name.encode("ascii", "ignore") for name in thread_list]
            return cpu_list, node_list, thread_list
    except FileNotFoundError:
        print(f'==WARNING== Could not access the .row file {row_file}')
        return np.empty(0), np.empty(0), np.empty(0)


def write_metadata_to_hdf5(hdf5_file: str, trace_metadata: TraceMetaData) -> str:
    """Writes into an hdf5 file the metadata contained in the header of the .prv
    file and the data of the .pcf and .row files."""
    try:
        with h5py.File(hdf5_file, "a") as f:
            metadata = f[HDF5_ROOT]
            metadata.attrs[HDF5_METADATA_NAME] = trace_metadata.name
            metadata.attrs[HDF5_METADATA_PATH] = trace_metadata.path
            metadata.attrs[HDF5_METADATA_TYPE] = trace_metadata.type
            metadata.attrs[HDF5_METADATA_EXEC_TIME] = trace_metadata.exec_time
            metadata.attrs[HDF5_METADATA_DATE] = trace_metadata.date_time.isoformat()
            metadata.attrs[HDF5_METADATA_NODES] = trace_metadata.nodes
            metadata.attrs[HDF5_METADATA_APPS] = json.dumps(trace_metadata.apps)
            metadata.create_dataset(HDF5_METADATA_HWCPU, (len(trace_metadata.cpu_list), 1), 'S25', trace_metadata.cpu_list)
            metadata.create_dataset(HDF5_METADATA_HWNODES, (len(trace_metadata.node_list), 1), 'S25', trace_metadata.node_list)
            metadata.create_dataset(HDF5_METADATA_THREADS, (len(trace_metadata.thread_list), 1), 'S25', trace_metadata.thread_list)
            return hdf5_file
    except FileNotFoundError:
        return ''


def file_parser(file: str, args: Dict = {}) -> str:
    try:
        with open(file, "r") as f:
            header= f.readline()
            if PARAVER_MAGIC_HEADER not in header:
                print(f'==WARNING== The file {file} is not a valid Paraver trace.')
                return ''

            # Parses contents
            hdf5_file = wrapper_prv_parser(file, args)

            # Parses straightforward metadata
            trace_name = os.path.basename(f.name)
            trace_path = os.path.abspath(f.name)
            trace_type = PARAVER_FILE
            # Parses header's metadata
            trace_exec_time, trace_date, trace_nodes, trace_apps = header_parser(header)
            # Parses .row's file metadata
            row_file = file[:-4] + '.row'
            cpu_list, node_list, thread_list = row_parser(row_file)
            trace_metadata = TraceMetaData(
                trace_name, trace_path, trace_type, trace_exec_time, trace_date, trace_nodes, trace_apps, cpu_list,
                node_list, thread_list
            )

            result = write_metadata_to_hdf5(hdf5_file, trace_metadata)

            return result;

    except FileNotFoundError:
        print(f'==ERROR== Could not open the file {file}')
        return ''