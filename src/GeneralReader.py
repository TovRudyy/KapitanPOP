import json
import math
import os
import subprocess
from typing import Dict, List
from datetime import datetime

import h5py
import dask.dataframe as dd
import numpy as np

import src.Trace as trace

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


def load(trace_file: str, args: Dict ={}) -> trace.Trace:
    """Reads the trace file provided. It it is a .prv it will parse it before
    loading it to memory."""
    if trace_file.endswith('.prv'):
        trace_hdf5_file = file_parser(trace_file, args)
        if not trace_hdf5_file:
            print(f'Could not completely parse the file.')
            return ''
    elif trace_file.endswith('.h5'):
        trace_hdf5_file = trace_file
    else:
        print(f'==ERROR== File {trace_file} has not a valid extension.')
        return ''

    trace_metadata = trace.TraceMetaData(hdf5_file=trace_hdf5_file)

    df_states = try_read_hdf5(trace_hdf5_file, key=trace.HDF5_RECORDS + "/" + trace.HDF5_STATES_DF)
    df_events = try_read_hdf5(trace_hdf5_file, key=trace.HDF5_RECORDS + "/" + trace.HDF5_EVENTS_DF)
    df_comms = try_read_hdf5(trace_hdf5_file, key=trace.HDF5_RECORDS + "/" + trace.HDF5_COMMS_DF)

    return trace.Trace(trace_metadata, df_states, df_events, df_comms)

def get_num_processes(hdf5_file: str) -> int:
    """Returns the number of processes of the trace either by reading its .row file
     or accessing the metadata."""
    cpus = trace.TraceMetaData.get_num_processes(hdf5_file = hdf5_file)
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


def prv_header_time(header: str) -> int:
    """Returns total execution time (ns) contained in the header."""
    try:
        time_ns, _, other = header[header.find("):") + 2:].partition("_ns")  # Originally it's in ns
        time = int(time_ns)
    except ValueError:
        print(f'==WARNING== Could not parse the time of the header.')
        time = 0
    return time

def prv_header_date(header: str) -> datetime:
    """Returns the contained date in the header."""
    date, _, other = header.replace("#Paraver (", "").replace("at ", "").partition("):")
    try:
        date = datetime.strptime(date, "%d/%m/%Y %H:%M")
    except ValueError:
        date = datetime.strptime(datetime.today().strftime("%d/%m/%Y %H:%M"), "%d/%m/%Y %H:%M")
        print(f"==WARNING== Could not parse header's date.")
    return date


def prv_header_nodes(header: str) -> List[int]:
    """Returns a list telling how many CPUs has each Node."""
    nodes = []
    try:
        nodes = header[header.find("_ns:") + 4:]
        if nodes[0] == "0":
            nodes = []
        else:
            nodes = nodes[nodes.find("(") + 1: nodes.find(")")]
            nodes = nodes.split(",")
            nodes = list(map(int, nodes))
    except ValueError:
        print("==WARNING== Could not parse header's node information.")
    return nodes

def prv_header_apps(header: str) -> List[List[Dict]]:
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
        print("==WARNING== Could not trace header's application layout.")

    return apps_list

def prv_header_parser(prv_file: str) -> (int, datetime, List[int], List[List[Dict]]):
    """Parses information from the header of the .prv file.
    Returns a tuple with the collected information: execution time, date when
    the trace was generated, node information, application's layout information,
    number of processes and tasks per node."""
    # Gets header's line
    opened_prv_file = open(prv_file, 'r')
    prv_header = opened_prv_file.readline()
    opened_prv_file.close()

    time = prv_header_time(prv_header)
    date = prv_header_date(prv_header)
    nodes = prv_header_nodes(prv_header)
    apps = prv_header_apps(prv_header)

    num_processes = 0
    tasks_per_node = 0
    if not nodes:
        num_processes = [num_processes + cpus for cpus in nodes]
        tasks_per_node = math.ceil(num_processes / len(nodes))

    return time, date, nodes, apps, num_processes, tasks_per_node


def row_parser(prv_file: str) -> (List[str], List[str], List[str]):
    """Guesses the name of the .row file acording prv_file.
    Parses the .row file returning a list with the CPUs, nodes and threads names."""
    cpu_list = []
    node_list = []
    thread_list = []

    row_file = prv_file[:-4] + '.row'
    try:
        opened_row_file = open(row_file, 'r')
    except FileNotFoundError:
        print(f'==WARNING== Could not open .row file {row_file}')
        return cpu_list, node_list, thread_list

    lines = opened_row_file.read().split("\n")
    opened_row_file.close()

    lines_generator = (i for i, s in enumerate(lines) if ("LEVEL CPU SIZE" or "LEVEL TASK SIZE") in s)
    index = next(lines_generator)
    cpu_size = int(lines[index].split()[3])
    cpu_list = lines[index + 1: index + cpu_size + 1]
    # HDF5 for python only supports string in ASCII code, thus we need to reencode the string
    cpu_list = [name.encode("ascii", "ignore") for name in cpu_list]
    lines_generator = (i for i, s in enumerate(lines) if "LEVEL NODE SIZE" in s)
    index = next(lines_generator)
    node_size = int(lines[index].split()[3])
    node_list = lines[index + 1: index + node_size + 1]
    node_list = [name.encode("ascii", "ignore") for name in node_list]
    lines_generator = (i for i, s in enumerate(lines) if "LEVEL THREAD SIZE" in s)
    index = next(lines_generator)
    thread_size = int(lines[index].split()[3])
    thread_list = lines[index + 1: index + thread_size + 1]
    thread_list = [name.encode("ascii", "ignore") for name in thread_list]

    return cpu_list, node_list, thread_list


def write_metadata_to_hdf5(hdf5_file: str, trace_metadata: trace.TraceMetaData) -> str:
    """Writes into an hdf5 file the metadata contained in the header of the .prv
    file and the data of the .pcf and .row files."""
    try:
        opened_hdf5_file = h5py.File(hdf5_file, 'a')
    except FileNotFoundError:
        print(f'==ERROR== Could not open the HDF5 file {hdf5_file}')
        return ''

    metadata = opened_hdf5_file[trace.HDF5_ROOT]
    metadata.attrs[trace.HDF5_METADATA_NAME] = trace_metadata.name
    metadata.attrs[trace.HDF5_METADATA_PATH] = trace_metadata.path
    metadata.attrs[trace.HDF5_METADATA_TYPE] = trace_metadata.type
    metadata.attrs[trace.HDF5_METADATA_EXEC_TIME] = trace_metadata.exec_time
    metadata.attrs[trace.HDF5_METADATA_DATE] = trace_metadata.date_time.isoformat()
    metadata.attrs[trace.HDF5_METADATA_NODES] = trace_metadata.nodes
    metadata.attrs[trace.HDF5_METADATA_APPS] = json.dumps(trace_metadata.apps)
    metadata.attrs[trace.HDF5_METADATA_NUM_PROCESSES] = trace_metadata.num_processes
    metadata.attrs[trace.HDF5_METADATA_TASKS_PER_NODE] = trace_metadata.tasks_per_node
    metadata.create_dataset(trace.HDF5_METADATA_HWCPU, (len(trace_metadata.cpu_list), 1), 'S25', trace_metadata.cpu_list)
    metadata.create_dataset(trace.HDF5_METADATA_HWNODES, (len(trace_metadata.node_list), 1), 'S25', trace_metadata.node_list)
    metadata.create_dataset(trace.HDF5_METADATA_THREADS, (len(trace_metadata.thread_list), 1), 'S25', trace_metadata.thread_list)
    opened_hdf5_file.close()
    return hdf5_file


def is_valid_file(prv_file: str) -> bool:
    """Checks if the prv_file is accessible and its header
    looks good."""

    # Checks if the file is accessible
    try:
        opened_prv_file = open(prv_file, 'r')
    except FileNotFoundError:
        print(f'==ERROR== Could not open the file {prv_file}')
        return False

    # Checks if file's header contains Paraver's signature
    prv_header = opened_prv_file.readline()
    opened_prv_file.close()

    if PARAVER_MAGIC_HEADER not in prv_header:
        print(f'==ERROR== The file {prv_file} doesn not contain a valid header.')
        return False

    return True


def get_basic_file_info(prv_file: str) -> (str, str, str):
    """Dumb function that returns very basic information
    about the trace."""
    opened_prv_file = open(prv_file, 'r')
    trace_name = os.path.basename(opened_prv_file.name)
    trace_path = os.path.abspath(opened_prv_file.name)
    trace_type = PARAVER_FILE

    return trace_name, trace_path, trace_type


def file_parser(prv_file: str, args: Dict = {}) -> str:
    """Responsible to parse Paraver files (.prv, .row and .pcf) and convert
    them into HDF5 file format. 'args' are the argument to pass to the prv_parser."""
    # Checks if file is valid
    if not is_valid_file(prv_file):
        return ''

    # First we try to parse file's contents and see if it succeeded
    hdf5_file = wrapper_prv_parser(prv_file, args)
    # Checks if return is an empty string
    if not hdf5_file:
        print(f'==ERROR== Could not parse contents of {prv_file}')
        return ''
    # Gets extra data
    trace_name, trace_path, trace_type = get_basic_file_info(prv_file)
    # Parses header information of the .prv file
    trace_exec_time, trace_date, trace_nodes, trace_apps, num_processes, tasks_per_node = prv_header_parser(prv_file)
    # Checks if it could compute number of processes and tasks per node
    num_processes_is_ok = (num_processes > 0 and tasks_per_node > 0)
    # Parses .row's file data
    cpu_list, node_list, thread_list = row_parser(prv_file)
    # Recomputes number of processes and tasks per node if it couldn't earlier
    if not num_processes_is_ok:
        if cpu_list and node_list:
            num_processes = len(cpu_list)
            tasks_per_node = math.ceil(num_processes / len(node_list))
        else:
            print(f'==ERROR== Could not compute number of processes and tasks per node.')
            return ''

    trace_metadata = trace.TraceMetaData(
        trace_name, trace_path, trace_type, trace_exec_time, trace_date, trace_nodes, trace_apps, num_processes,
        tasks_per_node, cpu_list, node_list, thread_list
    )

    result = write_metadata_to_hdf5(hdf5_file, trace_metadata)

    return result;
