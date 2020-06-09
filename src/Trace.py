from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass

import numpy as np
import dask.dataframe as dd

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
            cpu_list: np.ndarray = None,
            node_list: np.ndarray = None,
            thread_list: np.ndarray = None,
    ):
        self.name = name
        self.path = path
        self.type = trace_type
        self.exec_time = exec_time
        self.date_time = date_time
        self.nodes = nodes[:]
        self.apps = apps[:]
        self.cpu_list = cpu_list
        self.node_list = node_list
        self.thread_list = thread_list

    def __repr__(self):
        """Returns self's representation as string."""
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