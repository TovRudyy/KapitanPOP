from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass
import json

import numpy as np
import dask.dataframe as dd
import h5py

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
HDF5_METADATA_NUM_PROCESSES = "metNumProcesses"
HDF5_METADATA_TASKS_PER_NODE = "metTasksPerNode"
HDF5_METADATA_HWCPU = "metHwcpu"
HDF5_METADATA_HWNODES = "metHwnodes"
HDF5_METADATA_THREADS = "metThreads"

@dataclass
class TraceMetaData:
    """Stores Trace Metadata."""
    def __init__(
            self,
            name: str = "",
            path: str = "",
            trace_type: str = "",
            exec_time: int = None,
            date_time: datetime = None,
            # len(Nodes) = #nodes | Nodes[0] = #CPUs of Node 1, Nodes[n] = #CPUs of Node n
            nodes: List[int] = None,
            # len(Apps) = #Apps | len(Apps[0]) = #Tasks of APP 1 | App[0][0] = {"nTreads": int, "node": int}
            apps: List[List[Dict]] = None,
            num_processes: int = None,
            tasks_per_node: int = None,
            cpu_list: np.ndarray = None,
            node_list: np.ndarray = None,
            thread_list: np.ndarray = None,
            hdf5_file: str = None,
    ):
        if hdf5_file:
            try:
                opened_hdf5_file = h5py.File(hdf5_file, 'r')
            except:
                print(f'==ERROR== Could not access to the hdf5_file {hdf5_file}')
                exit(-1)

            metadata = opened_hdf5_file[HDF5_ROOT]
            self.name = metadata.attrs[HDF5_METADATA_NAME]
            self.path = metadata.attrs[HDF5_METADATA_PATH]
            self.type = metadata.attrs[HDF5_METADATA_TYPE]
            self.exec_time = metadata.attrs[HDF5_METADATA_EXEC_TIME]
            self.date_time = datetime.strptime(metadata.attrs[HDF5_METADATA_DATE], "%Y-%m-%dT%H:%M:%S")
            self.node_list = metadata.attrs[HDF5_METADATA_NODES]
            self.apps = json.loads(metadata.attrs[HDF5_METADATA_APPS])
            self.num_processes = metadata.attrs[HDF5_METADATA_NUM_PROCESSES]
            self.tasks_per_node = metadata.attrs[HDF5_METADATA_TASKS_PER_NODE]
            self.cpu_list = metadata[HDF5_METADATA_HWCPU][:].tolist(),
            self.node_list = metadata[HDF5_METADATA_HWNODES][:].tolist(),
            self.thread_list = metadata[HDF5_METADATA_THREADS][:].tolist()

            opened_hdf5_file.close()
        else:
            self.name = name
            self.path = path
            self.type = trace_type
            self.exec_time = exec_time
            self.date_time = date_time
            self.nodes = nodes[:]
            self.apps = apps[:]
            self.num_processes = num_processes
            self.tasks_per_node = tasks_per_node
            self.cpu_list = cpu_list
            self.node_list = node_list
            self.thread_list = thread_list


    def __repr__(self):
        """Returns self's representation as string."""
        ## DEPRECATED ##
        myself = f"INFORMATION OF OBJECT {type(self)}\n"
        myself += "--------------------\n"
        myself += f"Name: {self.name}\n"
        myself += f"Path: {self.path}\n"
        myself += f"Type: {self.type} \n"
        myself += f"ExecTime: {self.exec_time}\n"
        if self.date_time is None:
            myself += "No date available\n"
        else:
            myself += f'Date: {self.date_time.isoformat(" ")}\n'
        if self.nodes is None:
            myself += "No node configuration available\n"
        else:
            myself += "Node\tCPU list\n"
            for i in range(len(self.nodes)):
                myself += f"{i}\t\t"
                j = 0
                while j < self.nodes[0] - 1:
                    myself += f"{j + 1} "
                    j += 1
                myself += f"{j + 1}\n"

        if self.apps is None:
            myself += "No application configuration avaiable\n"
        else:
            myself += "APP\tTask\tThreads\tNode\n"
            app_id = 1
            for app in self.apps:
                myself += "".join(
                    [f"{app_id}\t{task_id}\t\t{task['nThreads']}\t\t{task['node']}\n" for task_id, task in enumerate(app)]
                )
                app_id += 1

        myself += "--------------------"
        return myself

    @classmethod
    def get_num_processes(cls, hdf5_file: str = None):
        cpus = 0

        if hdf5_file:
            opened_hdf5_file = h5py.File(hdf5_file, 'r')
            cpus = opened_hdf5_file[HDF5_ROOT].attrs[HDF5_METADATA_NUM_PROCESSES]
            opened_hdf5_file.close()

        return cpus



@dataclass
class Trace:
     """Stores Trace data."""
     def __init__(self,
                  metadata: TraceMetaData = None,
                  df_state: dd.DataFrame = None,
                  df_event: dd.DataFrame = None,
                  df_comm: dd.DataFrame = None
         ):
         self.metadata = metadata
         self.df_state = df_state
         self.df_event = df_event
         self.df_comm = df_comm