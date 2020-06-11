import subprocess
import os
import sys
import tempfile
import argparse
import fnmatch
from typing import Dict, List

import h5py
import pandas as pd
import numpy as np
import dask
import dask.dataframe as dd
import dask.array as da

from src.GeneralReader import file_parser, load, get_num_processes
from src.Trace import Trace
from src.CONST import MOD_FACTORS_DOC, MOD_FACTORS_VAL, STATE_COLS, STATE_VALUES, EVENT_COLS, EVENT_VALUES
from src.CONST import __DECIMAL_PRECISION

__author__ = 'Oleksandr Rudyy, Adrián Espejo Saldaña'
__version_major__ = 0
__version_minor__ = 0
__version_micro__ = 1
__version__ = f'{__version_major__}.{__version_minor__}.{__version_micro__}'


prv_parser_args = {}


def parse_arguments():
    """Parses the command line arguments.
    Currently the script only accepts one parameter list, which is the list of
    traces that are processed. This can be a regex and only valid trace files
    are kept at the end."""
    parser = argparse.ArgumentParser(description='Generates performance metrics from a set of Paraver traces.')
    parser.add_argument('trace_list', nargs='*',
                        help='list of traces to process in .prv or .h5 format. Accepts wild cards and automaticaly filters for valid traces')
    parser.add_argument('-d', '--debug', help='increases output verbosity to debug level', action='store_true')
    parser.add_argument('-s', '--scaling',
                        help='defines whether the measurements are weak or strong scaling (default: auto)',
                        choices=['weak', 'strong', 'auto'], default='auto')
    parser.add_argument('-dim', '--dimemas', help='runs Dimemas to get ideal execution times', action='store_true',
                        default=False)
    parser.add_argument('-p', '--only_parse', action='store_true', help='only parse the trace_list. This option is provided to control parsing parameters')
    parser.add_argument('--chunk_size', metavar='MB', type=int, default=1024, help='parser option: limits maximum size of the file to hold in memory (default 1GB)')
    parser.add_argument('-c', '--comp_lvl', metavar='LVL', default=0, help='parser option: sets the compression level (between 0 and 9). Default is 0 (no compression)')

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    cmdl_args = parser.parse_args()

    prv_parser_args['--chunk_size'] = cmdl_args.chunk_size
    prv_parser_args['--comp_lvl'] = cmdl_args.comp_lvl
    if cmdl_args.debug:
        print('==DEBUG== Running in debug mode.')
        prv_parser_args['--verbose'] = True

    return cmdl_args


def get_prv_traces_from_args(cmdl_args) -> List[str]:
    """Filters the given list to extract traces, i.e. matching *.prv.
    Excludes all files other than *.prv.Returns list of trace paths.
    """
    trace_list = [x for x in cmdl_args.trace_list if (fnmatch.fnmatch(x, '*.prv')) if os.path.exists(x)]
    if not trace_list:
        print(f'==ERROR== Could not find any traces matching {cmdl_args.trace_list}')
        sys.exit(-1)

    return trace_list


def get_traces_from_args(cmdl_args, prv_parser_args: Dict = {}) -> Dict:
    """Filters the given list to extract traces, i.e. matching *.prv & *.h5 and sorts
     the traces in ascending order based on the number of processes in the trace.
     Excludes all files other than *.prv & *.h5 and ignores also simulated traces from
     this script, i.e. *.sim.prv & *.sim.h5
     Returns list of trace paths and dictionary with the number of processes.
     """
    trace_list = [x for x in cmdl_args.trace_list if (fnmatch.fnmatch(x, '*.prv') or fnmatch.fnmatch(x, '*.h5')) if
                  not (fnmatch.fnmatch(x, '*.sim.prv') or fnmatch.fnmatch(x, '*.sim.h5')) if os.path.exists(x)]

    for trace in trace_list:
        if trace.endswith('.prv'):
            trace_list.remove(trace)
            trace_list.append(file_parser(trace, prv_parser_args))

    if not trace_list:
        print(f'==ERROR== Could not find any traces matching {cmdl_args.trace_list}')
        sys.exit(1)

    # Removes .prv files if it already has its parsed .h5 file
    [trace_list.remove(trace) for trace in trace_list if f'{trace[:-4]}.h5' in trace_list]
    trace_list = sorted(trace_list, key=get_num_processes)


    trace_processes = dict()

    for trace in trace_list:
        trace_processes[trace] = get_num_processes(trace)

    print_overview(trace_list, trace_processes)
    return trace_list, trace_processes


def which(cmd):
    """Returns path to cmd in path or None if not available."""
    for path in os.environ['PATH'].split(os.pathsep):
        path = path.strip('"')
        cmd_path = os.path.join(path, cmd)
        if os.path.isfile(cmd_path) and os.access(cmd_path, os.X_OK):
            return cmd_path

    return None


def check_installation(cmdl_args):
    """Checks if Dimemas, Pandas, Dask and h5py are installed and available."""
    if not which('Dimemas'):
        print('==WARNING== Could not find Dimemas. Please make sure Dimemas is correctly installed and in the path.')

    if cmdl_args.debug:
        print(f'==DEBUG== Using {__file__} {__version__}')
        print(f'==DEBUG== Using {sys.executable}.{map(str, sys.version_info[:3])}')

        try:
            print(f'==DEBUG== Using Pandas {pd.__version__}')
        except NameError:
            print(f'==ERROR== Pandas not installed.')
            sys.exit(1)
        try:
            print(f'==DEBUG== Using Dask {dask.__version__}')
        except NameError:
            print('==ERROR== Dask not installed')
        try:
            print(f'==DEBUG== Using h5py {h5py.__version__}')
        except NameError:
            print('==ERROR== h5py not installed')
        print(f"==DEBUG== Using {which('Dimemas')}")
        print('')

    return


def run_command(cmd):
    """Runs a command and forwards the return value."""
    if cmdl_args.debug:
        print(f'==DEBUG== Executing {cmd}')
    # In debug mode, keep the output. Otherwise, redirect it to devnull.
        out = tempfile.NamedTemporaryFile(suffix='.out', prefix=f'{cmd[0]}_', dir='./', delete=False)
        err = tempfile.NamedTemporaryFile(suffix='.err', prefix=f'{cmd[0]}_', dir='./', delete=False)
    else:
        out = open(os.devnull, 'w')
        err = open(os.devnull, 'w')

    return_value = subprocess.call(cmd, stdout=out, stderr=err)

    out.close()
    err.close()

    if return_value == 0:
        None
    else:
        print(f'==ERROR== {cmd} failed with return value {return_value}')

    if cmdl_args.debug:
        print(f'==DEBUG== See {out.name} and {err.name} for more details about the command execution.')

    return return_value


def create_ideal_trace(trace: str, processes: int):
    """Returns a Dimemas .prv file simulating the execution of trace
    on an ideal network."""

    print(f'==INFO== Simulating ideal execution of {trace}')

    trace_dim = trace[:-4] + '.dim'
    trace_sim = trace[:-4] + '.sim.prv'
    cmd = ['prv2dim', trace, trace_dim]
    run_command(cmd)
    if os.path.isfile(trace_dim):
        None
    else:
        print(f'==ERROR== {trace_dim} could not be created.')
        return None
    # Creates Dimemas configuration
    cfg_dir = os.path.join(os.path.dirname(__file__), 'cfgs')
    content = []
    with open(os.path.join(cfg_dir, 'dimemas_ideal.cfg')) as f:
        content = f.readlines()
        content = [line.replace('REPLACE_BY_NTASKS', str(processes)) for line in content]
        content = [line.replace('REPLACE_BY_COLLECTIVES_PATH', os.path.join(cfg_dir, 'dimemas.collectives')) for line in
                   content]

    with open(trace[:-4] + '.dimemas_ideal.cfg', 'w') as f:
        f.writelines(content)
    cmd = ['Dimemas', '-S', '32k', '--dim', trace_dim, '-p', trace_sim, trace[:-4] + '.dimemas_ideal.cfg']
    run_command(cmd)

    os.remove(trace_dim)
    os.remove(trace[:-4] + '.dimemas_ideal.cfg')

    if os.path.isfile(trace_sim):
        return trace_sim
    else:
        print(f'==ERROR== {trace_sim} could not be created.')
        return None


def get_ideal_data(trace: str, processes: int):
    """Returns ideal runtime and useful computation time."""
    # Creates ideal trace with Dimemas
    trace_sim = create_ideal_trace(trace, processes)
    if trace_sim:
        # Parses the just generated .prv file and loads it
        trace_sim = load(trace_sim, prv_parser_args)

        # Drops duplicate rows (somehow the generated trace by Dimemas has duplicated rows)
        df_state = trace_sim.df_state.drop_duplicates()

        # Computes the elapse times of each state
        df_state['el_time'] = df_state[STATE_COLS.END.value] - df_state[STATE_COLS.START.value]

        # Removes start and end columns from rows cause we don't need them. Load the data into memory.
        df_state = df_state.drop(columns=[STATE_COLS.START.value, STATE_COLS.END.value]).compute()

        # Computes runtime (in us)
        runtime_id = df_state.groupby([STATE_COLS.APP.value, STATE_COLS.TASK.value, STATE_COLS.THREAD.value])[
                      'el_time'].sum().max() / 1000

        # Computes useful ideal max time (in us)
        useful_id = \
        df_state.loc[df_state[STATE_COLS.VAL.value] == STATE_VALUES.RUNNING.value].groupby([STATE_COLS.APP.value, STATE_COLS.TASK.value, STATE_COLS.THREAD.value])[
            'el_time'].sum().max() / 1000

        return runtime_id, useful_id

    else:
        return float('NaN'), float('NaN')


def is_useful(row, useful_states):
    appid, taskid, threadid = row.name
    useful_times = useful_states.loc[(useful_states[STATE_COLS.APP.value] == appid) & (useful_states[STATE_COLS.TASK.value] == taskid) & (useful_states[STATE_COLS.THREAD.value] == threadid)][STATE_COLS.END.value].values
    useful_rows = row.loc[row[EVENT_COLS.TIME.value].isin(useful_times)]
    return useful_rows
    #print(row.loc[row[EVENT_COLS.TIME.value].isin(useful_states)])

def get_raw_data(trace: Trace, cmdl_args):
    """Analyses the trace and computes raw values."""
    # Retrieves states dataframe with the intresting columns
    df_state = trace.df_state[[STATE_COLS.APP.value, STATE_COLS.TASK.value, STATE_COLS.THREAD.value, STATE_COLS.START.value,
                               STATE_COLS.END.value, STATE_COLS.VAL.value]]

    # Computes the elapse times of each state
    df_state['el_time'] = df_state[STATE_COLS.END.value] - df_state[STATE_COLS.START.value]

    # Removes start and end columns from rows cause we don't need them. Load the data into memory.
    df_state = df_state.drop(columns=[STATE_COLS.START.value, STATE_COLS.END.value]).compute()

    # Computes runtime (in us)
    runtime = df_state.groupby([STATE_COLS.APP.value, STATE_COLS.TASK.value, STATE_COLS.THREAD.value])['el_time'].sum().max() / 1000
    # Filters rows by useful and groups dataframe by process
    df_state_useful_grouped = df_state.loc[df_state[STATE_COLS.VAL.value] == STATE_VALUES.RUNNING.value].groupby([STATE_COLS.APP.value, STATE_COLS.TASK.value, STATE_COLS.THREAD.value])
    # Computes useful average time (in us)
    useful_av = df_state_useful_grouped['el_time'].sum().mean() / 1000
    # Computes useful max time (in us)
    useful_max = df_state_useful_grouped['el_time'].sum().max() / 1000
    # Computes useful tot time (in us)
    useful_tot = df_state_useful_grouped['el_time'].sum().sum() / 1000

    # Dimemas simulation for ideal times
    if cmdl_args.dimemas:
        runtime_id, useful_id = get_ideal_data(trace.metadata.path, len(trace.metadata.cpu_list))
    else:
        runtime_id = float('NaN')
        useful_id = float('NaN')


    # Loads only meaningful columns from df_states and filters useful rows
    df_state_useful = trace.df_state[[STATE_COLS.APP.value, STATE_COLS.TASK.value, STATE_COLS.THREAD.value, STATE_COLS.END.value, STATE_COLS.VAL.value]]
    df_state_useful = df_state_useful.loc[df_state_useful[STATE_COLS.VAL.value] == STATE_VALUES.RUNNING.value].drop(columns=STATE_COLS.VAL.value).compute()

    # Loads only meaningful columns from df_events
    df_event = trace.df_event[[EVENT_COLS.APP.value, EVENT_COLS.TASK.value, EVENT_COLS.THREAD.value, EVENT_COLS.TIME.value,
                                   EVENT_COLS.EVTYPE.value, EVENT_COLS.EVVAL.value]]

    # Filters for PAPI_TOT_INS and set as index the process identifier
    df_event_ins = df_event.loc[df_event[EVENT_COLS.EVTYPE.value] == EVENT_VALUES.PAPI_TOT_INS.value].drop(columns=EVENT_COLS.EVTYPE.value).compute().set_index([EVENT_COLS.APP.value, EVENT_COLS.TASK.value, EVENT_COLS.THREAD.value])

    # Gets total useful instructions by grouping and applying a custom filtering function
    useful_ins = df_event_ins.groupby([EVENT_COLS.APP.value,EVENT_COLS.TASK.value, EVENT_COLS.THREAD.value]).apply(is_useful, useful_states=df_state_useful)[EVENT_COLS.EVVAL.value].sum()

    # Filter for PAPI_TOT_CYC and set as indexes the process identifier
    df_event_cyc = df_event.loc[df_event[EVENT_COLS.EVTYPE.value] == EVENT_VALUES.PAPI_TOT_CYC.value].drop(columns=EVENT_COLS.EVTYPE.value).compute().set_index([EVENT_COLS.APP.value, EVENT_COLS.TASK.value, EVENT_COLS.THREAD.value])

    # Gets total useful cycles by grouping and applying a custom filtering function
    useful_cyc= df_event_cyc.groupby([EVENT_COLS.APP.value,EVENT_COLS.TASK.value, EVENT_COLS.THREAD.value]).apply(is_useful, useful_states=df_state_useful)[EVENT_COLS.EVVAL.value].sum()

    # Computes  average IPC
    try:
        ipc = useful_ins / useful_cyc
    except ValueError:
        ipc = float('NaN')
    # Computes average frequency
    try:
        freq = useful_cyc / useful_tot / 1000
    except ValueError:
        freq = float('NaN')

    return ipc, freq, runtime, runtime_id, useful_av, useful_max, useful_tot, useful_id, useful_ins, useful_cyc


def get_scaling_type(df_mfactors: pd.DataFrame, cmdl_args):
    """Guess the scaling type (weak/strong) based on the useful instructions.
    Computes the normalized instruction ratio for all measurements, whereas the
    normalized instruction ratio is (instructions ratio / process ratio) with
    the smallest run as reference. For exact weak scaling the normalized ratio
    should be exactly 1 and for exact strong scaling it should be close to zero
    with an upper bound of 0.5. The eps value defines the threshold to be
    considered weak scaling and should give enough buffer to safely handle
    non-ideal scaling.
    """
    eps = 0.9
    normalized_inst_ratio = 0

    # Check if there is only one trace
    if len(df_mfactors.index) == 1:
        return 'strong'

    for index, row in df_mfactors.iterrows():
        inst_ratio = float(row[MOD_FACTORS_DOC['useful_ins']]) / float(df_mfactors[MOD_FACTORS_DOC['useful_ins']][0])
        proc_ratio = float(row[MOD_FACTORS_DOC['num_processes']]) / float(
            df_mfactors[MOD_FACTORS_DOC['num_processes']][0])
        normalized_inst_ratio += inst_ratio / proc_ratio

    # Get the average inst increase. Ignore ratio of first trace (1.0)
    normalized_inst_ratio = (normalized_inst_ratio - 1) / (len(df_mfactors.index) - 1)

    scaling_computed = ''

    if normalized_inst_ratio > eps:
        scaling_computed = 'weak'
    else:
        scaling_computed = 'strong'

    if cmdl_args.scaling == 'auto':
        if cmdl_args.debug:
            print(f'==DEBUG== Detected {scaling_computed} scaling.')
            print('')
        return scaling_computed

    if cmdl_args.scaling == 'weak':
        if scaling_computed == 'strong':
            print('==WARNING== Scaling set to weak scaling but detected strong scaling.')
            print('')
        return 'strong'

    if cmdl_args.scaling == 'strong':
        if scaling_computed == 'weak':
            print('==WARNING== Scaling set to strong scaling but detected weak scaling.')
            print('')
        return 'strong'

    print('==ERROR== Reached undefined control flow state.')
    sys.exit(1)


def get_scalabilities(df_mfactors: pd.DataFrame, cmdl_args):
    """Computes scalability metrics adding them directly to the dataframe."""
    scaling_type = get_scaling_type(df_mfactors, cmdl_args)

    for index, row in df_mfactors.iterrows():
        if scaling_type == 'strong':
            try:
                df_mfactors[MOD_FACTORS_DOC['comp_scale']][index] = df_mfactors[MOD_FACTORS_DOC['useful_tot']][0] / row[
                    MOD_FACTORS_DOC['useful_tot']] * 100
            except ValueError:
                df_mfactors[MOD_FACTORS_DOC['comp_scale']][index] = float('NaN')
            try:
                df_mfactors[MOD_FACTORS_DOC['ins_scale']][index] = df_mfactors[MOD_FACTORS_DOC['useful_ins']][0] / row[
                    MOD_FACTORS_DOC['useful_ins']] * 100
            except ValueError:
                df_mfactors[MOD_FACTORS_DOC['ins_scale']] = float('NaN')
            try:
                df_mfactors[MOD_FACTORS_DOC['speedup']][index] = df_mfactors[MOD_FACTORS_DOC['runtime']][0] / row[
                    MOD_FACTORS_DOC['runtime']]
            except ValueError:
                df_mfactors[MOD_FACTORS_DOC['speedup']] = float('NaN')

        elif scaling_type == 'weak':
            lif = row[MOD_FACTORS_DOC['num_processes']] / df_mfactors[MOD_FACTORS_DOC['num_processes']][0]
            try:
                df_mfactors[MOD_FACTORS_DOC['comp_scale']][index] = df_mfactors[MOD_FACTORS_DOC['useful_tot']][0] / row[
                    MOD_FACTORS_DOC['useful_tot']] / lif * 100
            except ValueError:
                df_mfactors[MOD_FACTORS_DOC['comp_scale']][index] = float('NaN')
            try:
                df_mfactors[MOD_FACTORS_DOC['ins_scale']][index] = df_mfactors[MOD_FACTORS_DOC['useful_ins']][0] / row[
                    MOD_FACTORS_DOC['useful_ins']] / lif * 100
            except ValueError:
                df_mfactors[MOD_FACTORS_DOC['ins_scale']] = float('NaN')
            try:
                df_mfactors[MOD_FACTORS_DOC['speedup']][index] = df_mfactors[MOD_FACTORS_DOC['runtime']][0] / row[
                    MOD_FACTORS_DOC['runtime']] * lif
            except ValueError:
                df_mfactors[MOD_FACTORS_DOC['speedup']] = float('NaN')

        try:
            df_mfactors[MOD_FACTORS_DOC['ipc_scale']][index] = row[MOD_FACTORS_DOC['ipc']] / df_mfactors[MOD_FACTORS_DOC['ipc']][0] * 100
        except ValueError:
            df_mfactors[MOD_FACTORS_DOC['ipc_scale']][index] = float('NaN')
        try:
            df_mfactors[MOD_FACTORS_DOC['freq_scale']][index] = row[MOD_FACTORS_DOC['freq']] / df_mfactors[MOD_FACTORS_DOC['freq']][0] * 100
        except ValueError:
            df_mfactors[MOD_FACTORS_DOC['freq_scale']] = float('NaN')

        # Now it can compute the global efficiency
        try:
            df_mfactors[MOD_FACTORS_DOC['global_eff']][index] = row[MOD_FACTORS_DOC['parallel_eff']] * row[
                MOD_FACTORS_DOC['comp_scale']] / 100
        except TypeError:
            global_eff = row[MOD_FACTORS_DOC['parallel_eff']]

    return df_mfactors


def get_efficiencies(runtime, runtime_id, useful_av, useful_max, useful_id, comp_scale):
    """Computes efficiencies."""
    try:
        load_balance = useful_av / useful_max * 100
    except TypeError:
        load_balance = float('NaN')
    try:
        comm_eff = useful_max / runtime * 100
    except TypeError:
        comm_eff = float('NaN')
    try:
        parallel_eff = load_balance * comm_eff / 100
    except TypeError:
        parallel_eff = float('NaN')
    try:
        transfer_eff = runtime_id / runtime * 100
    except TypeError:
        transfer_eff = float('NaN')
    try:
        serial_eff = useful_id / runtime_id * 100
    except TypeError:
        serial_eff = float('NaN')

    return parallel_eff, load_balance, comm_eff, serial_eff, transfer_eff


def print_mod_factors_csv(df: pd.DataFrame):
    """Prints the computed metrics into a .csv file"""
    delimiter = ';'

    file_path = os.path.join(os.getcwd(), 'modelfactors.csv')
    with open(file_path, 'w') as output:
        for columnname, data in df.iteritems():
            line = f"{columnname}"
            for value in data:
                try:
                    line += delimiter + '{0:.{prec}f}'.format(value, prec=__DECIMAL_PRECISION)
                except ValueError:
                    line += '{}'.format(value)
            output.write(line + '\n')
            if columnname == MOD_FACTORS_DOC['freq']:
                output.write("#\n")
    print(f'==INFO== Modelfactors written into {file_path}')


def modelfactors(trace_files: List[str], trace_processes: Dict):
    """ Analyse the provided traces returning a Pandas dataframe with all POP efficiencies"""
    traces = [load(file) for file in trace_files]
    df_mfactors = pd.DataFrame(columns=MOD_FACTORS_DOC.values())
    reference = True
    for (hdf5_file, trace, cpus) in zip(trace_files, traces, trace_processes.values()):
        MOD_FACTORS_VAL['num_processes'] = cpus
        print(
            f"==INFO== Analysing {hdf5_file} ({MOD_FACTORS_VAL['num_processes']} processes, {human_readable(os.path.getsize(hdf5_file))})")

        # Computes raw data
        ipc, freq, runtime, runtime_id, useful_av, useful_max, useful_tot, useful_id, useful_inst, useful_cyc = get_raw_data(
            trace, cmdl_args)

        MOD_FACTORS_VAL['ipc'] = ipc
        MOD_FACTORS_VAL['freq'] = freq
        MOD_FACTORS_VAL['runtime'] = runtime
        MOD_FACTORS_VAL['runtime_id'] = runtime_id
        MOD_FACTORS_VAL['useful_av'] = useful_av
        MOD_FACTORS_VAL['useful_max'] = useful_max
        MOD_FACTORS_VAL['useful_tot'] = useful_tot
        MOD_FACTORS_VAL['useful_id'] = useful_id
        MOD_FACTORS_VAL['useful_ins'] = useful_inst
        MOD_FACTORS_VAL['useful_cyc'] = useful_cyc

        # Computes efficiencies after getting the raw data
        parallel_eff, load_balance, comm_eff, serial_eff, transfer_eff = get_efficiencies(
            MOD_FACTORS_VAL['runtime'],
            MOD_FACTORS_VAL['runtime_id'],
            MOD_FACTORS_VAL['useful_av'],
            MOD_FACTORS_VAL['useful_max'],
            MOD_FACTORS_VAL['useful_id'],
            MOD_FACTORS_VAL['comp_scale'])

        MOD_FACTORS_VAL['parallel_eff'] = parallel_eff
        MOD_FACTORS_VAL['load_balance'] = load_balance
        MOD_FACTORS_VAL['comm_eff'] = comm_eff
        MOD_FACTORS_VAL['serial_eff'] = serial_eff
        MOD_FACTORS_VAL['transfer_eff'] = transfer_eff

        # Adds the new row with the raw data and efficiencies to the dataframe
        df_mfactors.loc[len(df_mfactors), :] = list(MOD_FACTORS_VAL.values())

    # Computes scalabilities
    df_mfactors = get_scalabilities(df_mfactors, cmdl_args)

    return df_mfactors


def human_readable(size, precision=1):
    """Converts a given size in bytes to the value in human readable form."""
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
    suffixIndex = 0
    while size > 1024 and suffixIndex < 4:
        suffixIndex += 1
        size = size / 1024.0
    return "%.*f%s" % (precision, size, suffixes[suffixIndex])


def print_overview(trace_list: List[str], trace_processes: Dict):
    """Prints an overview of the traces that will be processed."""
    print(f'==INFO== Running {os.path.basename(__file__)} for the following traces:')

    for trace in trace_list:
        line = trace
        line += f', {str(trace_processes[trace])} processes'
        line += f', {human_readable(os.path.getsize(trace))}'
        print(line)
    print('')


if __name__ == "__main__":
    """Main control flow.
     Currently the script only accepts one parameter, which is a list of traces
     that are processed. This can be a regex with wild cards and only valid trace
     files are kept at the end.
     """
    # Parses command line arguments
    cmdl_args = parse_arguments()

    # Deals with the only_parse mode
    if cmdl_args.only_parse:
        print(f'==INFO== Only parsing mode.')
        # Gets only prv traces
        trace_list = get_prv_traces_from_args(cmdl_args)

        for trace in trace_list:
            result_hdf5 = file_parser(trace, prv_parser_args)
            if not result_hdf5 == '':
                print(f'==INFO== Has been generated the file {result_hdf5} of {human_readable(os.path.getsize(result_hdf5))}')

    else:
        # Checks if Dimemas is in the path
        check_installation(cmdl_args)

        # Gets info about the traces
        trace_list, trace_processes = get_traces_from_args(cmdl_args, prv_parser_args)

        # Analyses traces
        df_mfactors = modelfactors(trace_list, trace_processes)
        # Generates the output file
        print_mod_factors_csv(df_mfactors)