from collections import OrderedDict
from enum import Enum

__DECIMAL_PRECISION = 2

MOD_FACTORS_VAL = OrderedDict([('num_processes', float('NaN')),
                               ('parallel_eff', float('NaN')),
                               ('load_balance', float('NaN')),
                               ('comm_eff', float('NaN')),
                               ('serial_eff', float('NaN')),
                               ('transfer_eff', float('NaN')),
                               ('comp_scale', float('NaN')),
                               ('global_eff', float('NaN')),
                               ('ipc_scale', float('NaN')),
                               ('ins_scale', float('NaN')),
                               ('freq_scale', float('NaN')),
                               ('speedup', float('NaN')),
                               ('ipc', float('NaN')),
                               ('freq', float('NaN')),
                               ('runtime', float('NaN')),
                               ('runtime_id', float('NaN')),
                               ('useful_av', float('NaN')),
                               ('useful_max', float('NaN')),
                               ('useful_tot', float('NaN')),
                               ('useful_id', float('NaN')),
                               ('useful_ins', float('NaN')),
                               ('useful_cyc', float('NaN'))])

MOD_FACTORS_DOC = OrderedDict([('num_processes', 'Number of processes'),
                               ('parallel_eff', 'Parallel efficiency'),
                               ('load_balance', 'Load balance'),
                               ('comm_eff', 'Communication efficiency'),
                               ('serial_eff', 'Serialization efficiency'),
                               ('transfer_eff', 'Transfer efficiency'),
                               ('comp_scale', 'Computation scalability'),
                               ('global_eff', 'Global efficiency'),
                               ('ipc_scale', 'IPC scalability'),
                               ('ins_scale', 'Instruction scalability'),
                               ('freq_scale', 'Frequency scalability'),
                               ('speedup', 'Speedup'),
                               ('ipc', 'Average IPC'),
                               ('freq', 'Average frequency (GHz)'),
                               ('runtime', '#Runtime (us)'),
                               ('runtime_id', '#Runtime (ideal)'),
                               ('useful_av', '#Useful duration (average)'),
                               ('useful_max', '#Useful duration (maximum)'),
                               ('useful_tot', '#Useful duration (total)'),
                               ('useful_id', '#Useful duration (ideal, max)'),
                               ('useful_ins', '#Useful instructions (total)'),
                               ('useful_cyc', '#Useful cycles')])


class STATE_COLS(Enum):
    """Columns of STATES"""
    CPU = "CPUID"
    APP = "APPID"
    TASK = "TaskID"
    THREAD = "ThreadID"
    START = "Time_ini"
    END = "Time_fi"
    VAL = "State"


class STATE_VALUES(Enum):
    """Table of possible State values (Paraver format)"""
    IDLE = 0
    RUNNING = 1
    NOT_CREATED = 2
    WAITING_A_MESSAGE = 3
    WAITING_FOR_LINK = 4
    WAITING_FOR_CPU = 5
    WAITING_FOR_SEMAPHORE = 6
    OVERHEAD = 7
    PROBE = 8
    SEND_OVERHEAD = 9
    RECV_OVERHEAD = 10
    DISK_IO = 11
    DISK_IO_BLOCK = 15