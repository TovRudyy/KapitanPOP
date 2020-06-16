#include <stdio.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <ctype.h>
#include <errno.h> 
#include <inttypes.h>
#include <assert.h>
#include <argp.h>

#ifdef PROFILING
#include <sys/time.h>
#define REGISTER_TIME(__t) gettimeofday(__t, NULL)
#define GET_ELAPSED_TIME(__t1, __t2) ((__t2).tv_sec + (__t2).tv_usec/1000000.0) - ((__t1).tv_sec + (__t1).tv_usec/1000000.0)
#endif

/*External libraries.*/
#include "hdf5.h"
#include "hdf5_hl.h"

#define MAXBUF  32768
#define DEF_READ_SIZE   1024*1024*1024
#define DEF_EXTEND_EVENT_CAPACITY   2
#define DEF_COMPRESSION_LEVEL   0
#define AV_LINE_LENGTH_BYTES  32
#define MIN_BYTES_STATES_LINE   16
#define MIN_BYTES_EVENTS_LINE   32
#define MIN_BYTES_COMMS_LINE    64
#define MIN_EVENT_CAP   512
#define DEF_MAX_HDF5_CHUNK_SIZE 4194304
#define DEF_MIN_HDF5_CHUNK_SIZE 4096
#define STATE_RECORD_ELEM 7
#define EVENT_RECORD_ELEM 7
#define COMM_RECORD_ELEM 14
#define HDF5_GROUP_NAME "/RECORDS"
#define STATE_DATASET_NAME "/RECORDS/STATES"
#define EVENT_DATASET_NAME "/RECORDS/EVENTS"
#define COMM_DATASET_NAME "/RECORDS/COMMUNICATIONS"
#define MASTER_THREAD 0
#define TRUE    1
#define FALSE   0

int retcode;
herr_t status;

char retbuff[MAXBUF];

uint8_t __Verbose = 0;
long long __ReadSize = DEF_READ_SIZE;
long long __MaxHDF5ChunkSize = DEF_MAX_HDF5_CHUNK_SIZE;
long long __MinHDF5ChunkSize = DEF_MIN_HDF5_CHUNK_SIZE;
unsigned int __ExtendEventCapacity = DEF_EXTEND_EVENT_CAPACITY;
int __CompressionLevel = DEF_COMPRESSION_LEVEL;

typedef enum {
    STATE_RECORD    =   1,
    EVENT_RECORD    =   2,
    COMM_RECORD     =   3,
    INVALID_RECORD  =   -1,
} recordTypes_enum;

/*Data structure holding all rows of one specific table.*/
typedef struct record_Array {
    void *array;    // array[]
    size_t elements;
    size_t capacity;
} record_Array;

/*Data structure to hold the read data from the .prv file
and some useful metadata.*/
typedef struct file_data {
    char *buffer;
    size_t counter_states;
    size_t counter_events;
    size_t counter_comms;
    size_t counter_unknowns;
    uint16_t *lengths;
    int8_t *types;
} file_data;

/*Specifies data types of STATES columns.*/
typedef struct state_row {
    uint32_t cpu_id;
    uint16_t appl_id;
    uint32_t task_id;
    uint32_t thread_id;
    uint64_t time_ini;
    uint64_t time_fi;
    uint16_t state;
} state_row;

/*Specifies data types of EVENTS columns.*/
typedef struct event_row {
    uint32_t cpu_id;
    uint16_t appl_id;
    uint32_t task_id;
    uint32_t thread_id;
    uint64_t time;
    uint64_t event_t;
    uint64_t event_v;
} event_row;

/*Specifies data types of COMMUNICATIONS columns.*/
typedef struct comm_row {
    uint32_t cpu_send_id;
    uint32_t ptask_send_id;
    uint32_t task_send_id;
    uint32_t thread_send_id;
    uint64_t lsend;
    uint64_t psend;
    uint32_t cpu_recv_id;
    uint32_t ptask_recv_id;
    uint32_t task_recv_id;
    uint32_t thread_recv_id;
    uint64_t lrecv;
    uint64_t precv;
    uint64_t size;
    uint64_t tag;
} comm_row;

/*Column names of the STATES table.*/
const char *__State_field_names[STATE_RECORD_ELEM] = {"CPUID", "APPID", "TaskID", "ThreadID", "Time_ini", "Time_fi", "State"};
hid_t __State_field_type[STATE_RECORD_ELEM];
size_t State_offset[STATE_RECORD_ELEM];

/*Column names of the EVENTS table.*/
const char *__Event_field_names[EVENT_RECORD_ELEM] = {"CPUID", "APPID", "TaskID", "ThreadID", "Time", "EventType", "EventValue"};
hid_t __Event_field_type[EVENT_RECORD_ELEM];
size_t __Event_offset[EVENT_RECORD_ELEM];

/*Column names of the COMMUNICATIONS table.*/
const char *__Comm_field_names[COMM_RECORD_ELEM] = {"CPUSendID", "PhyTaskSendID", "LogTaskSendID", "ThreadSendID", "LogSendTime", "PhySendTime", "CPUReceiveID", "PhyTaskReceiveID", "LogTaskReceiveID", "ThreadReceiveID", "LogReceiveTime", "PhyReceiveTime", "Size", "Tag"};
hid_t __Comm_field_type[COMM_RECORD_ELEM];
size_t __Comm_offset[EVENT_RECORD_ELEM];

/*Checks what kind of records identifies the character.*/
recordTypes_enum get_record_type(char *line) {
    char record = line[0];
    if ('0' <= record && record <= '3') {
        return record - '0';
    }
    else {
        return INVALID_RECORD;
    }
}

/*Ensures that the read data is aligned to a line. If the read data is not aligned
to a line, descards all characters until the end of the previous line.*/
size_t align_to_line(FILE *fp, const size_t read_bytes, const char* buf) {
    size_t back = 0;
    char xivato = buf[read_bytes-1];
    if (xivato != '\n' && xivato != '\0') {
    uint8_t stop = FALSE;
        for (; back < read_bytes && !stop; back++) {
            xivato = buf[(read_bytes-back)-1];
            if (xivato == '\n') {
                fseek(fp, -back, SEEK_CUR); // Move the file pointer to the start of the line
                stop = TRUE;
            }
        }
    }
    return back;
}

/*Processes 1 line of the .prv belonging to a State records.
Fills the structure pointed by state with the impoant data.*/
size_t parse_state(char *line, state_row *state) {
    char *next, *rest = line;
    size_t ret = 7;
    // Discards the record type
    strtok_r(rest, ":", &rest);
    next = strtok_r(rest, ":", &rest);
    state->cpu_id = (uint32_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    state->appl_id = (uint16_t) atoi(next);
    next = strtok_r(rest, ":", &rest);
    state->task_id = (uint32_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    state->thread_id = (uint32_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    state->time_ini = (uint64_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    state->time_fi = (uint64_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    state->state = (uint16_t) atoi(next);
    return ret;
}

/*Fills the event rows of events with the events of the events found.*/
size_t parse_event(char *line, event_row *events) {
    char *next, *nnext, *rest = line;
    size_t nevents = 0;
    //We discard the record type:
    strtok_r(rest, ":", &rest);
    next = strtok_r(rest, ":", &rest);
    events[nevents].cpu_id = (uint32_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    events[nevents].appl_id = (uint16_t) atoi(next);
    next = strtok_r(rest, ":", &rest);
    events[nevents].task_id = (uint32_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    events[nevents].thread_id = (uint32_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    events[nevents].time = (uint64_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    events[nevents].event_t = (uint64_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    events[nevents].event_v = (uint64_t) atoll(next);
    nevents++;
    while ((next = strtok_r(rest, ":", &rest)) && (nnext = strtok_r(rest, ":", &rest))) {
        events[nevents].cpu_id = events[nevents-1].cpu_id;
        events[nevents].appl_id = events[nevents-1].appl_id;
        events[nevents].task_id = events[nevents-1].task_id;
        events[nevents].thread_id = events[nevents-1].thread_id;
        events[nevents].time = events[nevents-1].time;
        events[nevents].event_t = (uint64_t) atoll(next);
        events[nevents].event_v = (uint64_t) atoll(nnext);
        nevents++;
    }
    return nevents;
}

/*Processes 1 line of the .prv file belonging to one communication
record. Fills the structure pointed by comm with the imporant
data.*/
size_t parse_comm(char *line, comm_row *comm) {
    char *next, *rest = line;
    size_t res = 14;
    // Removes the record type:
    strtok_r(rest, ":", &rest);
    next = strtok_r(rest, ":", &rest);
    comm->cpu_send_id = (uint32_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    comm->ptask_send_id = (uint32_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    comm->task_send_id = (uint32_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    comm->thread_send_id = (uint32_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    comm->lsend = (uint64_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    comm->psend = (uint64_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    comm->cpu_recv_id = (uint32_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    comm->ptask_recv_id = (uint32_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    comm->task_recv_id = (uint32_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    comm->thread_recv_id = (uint32_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    comm->lrecv = (uint64_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    comm->precv = (uint64_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    comm->size = (uint64_t) atoll(next);
    next = strtok_r(rest, ":", &rest);
    comm->tag = (uint64_t) atoll(next);
    return res;
}

/* Takes the read data from the .prv file and fills the states, events and comms row structures */
void data_parser(const file_data *file_d, record_Array *states, record_Array *events, record_Array *comms) {
    #ifdef PROFILING
    struct timeval start, end;
    REGISTER_TIME(&start);
    #endif

    size_t ret;
    size_t st_cap, ev_cap, cmm_cap;
    // Gets reference pointers to the main data structures
    st_cap = (states->capacity) = (file_d->counter_states);
    ev_cap = (events->capacity) = (file_d->counter_events)+MIN_EVENT_CAP;
    cmm_cap = (comms->capacity) = (file_d->counter_comms);
    size_t st_elem, ev_elem, cmm_elem;
    state_row *states_a = states->array = (state_row *)calloc((states->capacity), sizeof(state_row));
    event_row *events_a = events->array = (event_row *)calloc((events->capacity), sizeof(event_row));
    comm_row  *comms_a = comms->array = (comm_row *)calloc((comms->capacity), sizeof(comm_row));
    st_elem = ev_elem = cmm_elem = (states->elements) = (events->elements) = (comms->elements) = 0;
    char * buffer= (file_d->buffer);
    uint16_t *lengths = (file_d->lengths);
    int8_t *types = (file_d->types);
    size_t total_lines;
    size_t iterator;
    size_t offset;
    iterator = offset = 0;
    total_lines = (file_d->counter_states) + (file_d->counter_events) + (file_d->counter_comms) + (file_d->counter_unknowns);
    // Iterates over the lines
    while(iterator < total_lines) {
        // Infer the type of the .prv line (State, Event or Communication)
        switch(types[iterator]) {
            case STATE_RECORD   :
                ret = parse_state(&buffer[offset], &states_a[st_elem]);
                assert(ret == STATE_RECORD_ELEM);
                st_elem++;
                break;

            case EVENT_RECORD   :
                ret = parse_event(&buffer[offset], &events_a[ev_elem]);
                ev_elem += ret;
                if ((ev_elem+MIN_EVENT_CAP) >= ev_cap) {   // Checks if capacity of events buffer is enough to hold more rows
                    ev_cap = ev_cap*__ExtendEventCapacity;
                    (events->capacity) = ev_cap;
                    event_row *replacement = (event_row *)calloc(ev_cap, sizeof(event_row));
                    memcpy(replacement, (events->array), ev_elem*sizeof(event_row));
                    free(events->array);
                    events_a = (events->array) = replacement;
                }
                break;

            case COMM_RECORD    :
                ret = parse_comm(&buffer[offset], &comms_a[cmm_elem]);
                assert(ret == COMM_RECORD_ELEM);
                cmm_elem++;
                break;

                default:
                break;
        }
        offset += lengths[iterator];
        iterator++;
    }
    // Set the right values to the main data structures
    (states->elements) = st_elem;
    (events->elements) = ev_elem;
    (comms->elements) = cmm_elem;
    #ifdef PROFILING
    REGISTER_TIME(&end);
    printf("==PROFILING== El. time to parse 1 chunk: %.3f sec.\n", GET_ELAPSED_TIME(start, end));
    #endif
}

/* Reads <MaxBytesRead> aligned to line of the file <file> with an offset. Preprocess the read data saving file's structure in <file_d>.
/* Returns the amount of bytes it has processed from the file. */
size_t read_and_preprocess( const char *file, const size_t MaxBytesRead, const size_t offset, file_data *file_d) {
    #ifdef PROFILING
    struct timeval start, end;
    REGISTER_TIME(&start);
    #endif

    FILE *fp;
    size_t read_bytes_counter, ret;
    read_bytes_counter = ret = 0;

    if ( (fp = fopen(file, "r")) == NULL) {
        retcode = errno;
        perror("split(...):fopen");
        exit(retcode);
    }
    // Moves the file pointer acording tot the displacement
    if ( fseek(fp, offset, SEEK_SET) != 0) {
        retcode = errno;
        perror("split(...):fseek");
        exit(retcode);
    }

    file_d->lengths = (uint16_t *)malloc(MaxBytesRead/AV_LINE_LENGTH_BYTES * sizeof(uint16_t));
    file_d->types = (int8_t *)malloc(MaxBytesRead/AV_LINE_LENGTH_BYTES * sizeof(int8_t));

    size_t counter_states, counter_events, counter_comms, counter_unknowns;
    counter_states = counter_events = counter_comms = counter_unknowns = 0;
    recordTypes_enum record_t;
    int8_t start_of_line = TRUE;  // Bool indicating start of a new line
    file_d->buffer = (char *)malloc(MaxBytesRead+MAXBUF); // Memory buffer where to store disk's data
    if ((read_bytes_counter = fread(file_d->buffer, 1, MaxBytesRead, fp)) > 0) {
        read_bytes_counter = read_bytes_counter - align_to_line(fp, read_bytes_counter, file_d->buffer);   //  Ensures that read block is aligned to a line
        ret += read_bytes_counter;
        size_t counter_lines;
        size_t counter_line_length;
        size_t iterator;
        for(counter_line_length = 1, counter_lines = iterator = 0; iterator <= read_bytes_counter; iterator++, counter_line_length++) {
            if (start_of_line) {
                record_t = get_record_type(&(file_d->buffer)[iterator]);
                switch(record_t) {
                    case STATE_RECORD   :
                    counter_states++;
                    break;
                    case EVENT_RECORD   :
                    counter_events++;
                    break;
                    case COMM_RECORD    :
                    counter_comms++;
                    break;
                    default :
                    counter_unknowns++;
                    #ifdef WARNING
                    printf("WARNING: Invalid/Not supported record type in the trace\n");
                    #endif
                    break;
                }
                (file_d->types)[counter_lines] = record_t;
                start_of_line = FALSE;
            }
            // Check whether it've reached line's end
            if ((file_d->buffer)[iterator] == '\n') {
                (file_d->buffer)[iterator] = '\0';  // Replaces '\n' with NULL

                (file_d->lengths)[counter_lines] = counter_line_length;
                start_of_line = TRUE;
                counter_lines++;
                counter_line_length = 0;
            }
        }
    }
    file_d->counter_states = counter_states;
    file_d->counter_events = counter_events;
    file_d->counter_comms = counter_comms;
    file_d->counter_unknowns = counter_unknowns;
    size_t total_elements = counter_states + counter_events + counter_comms + counter_unknowns;
    size_t o;
    for (o = 0; o < total_elements; o++)
    // Reallocs file_structure size to minimize memory consumption
    file_d->lengths = realloc(file_d->lengths, total_elements*sizeof(uint16_t));
    file_d->types = realloc(file_d->types, total_elements*sizeof(int8_t));
    fclose(fp);

    #ifdef PROFILING
    REGISTER_TIME(&end);
    printf("==PROFILING== El. time read & pre-process 1 chunk: %.3f sec.\n", GET_ELAPSED_TIME(start, end));
    #endif
    return ret;
}

hid_t create_HDF5(const char * name) {
    hid_t file_id;
    /* HDF5 file creation */
    file_id = H5Fcreate(name, H5F_ACC_TRUNC, H5P_DEFAULT, H5P_DEFAULT);
    return file_id;
}

hid_t create_HDF5_group(const hid_t parent, const char * name) {
    hid_t group_id;
    group_id = H5Gcreate(parent, name, H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT);
    return group_id;
}

/*Creates the HDF5 table where to store parsed data.*/
void create_HDF5tables(const hid_t loc_id, record_Array state, record_Array event, record_Array comm) {
    #ifdef PROFILING
    struct timeval start, end;
    REGISTER_TIME(&start);
    #endif
    // Infers ideal table's chunk size
    size_t chunk_state, chunk_event, chunk_comm;
    if (state.elements > __MaxHDF5ChunkSize) chunk_state = __MaxHDF5ChunkSize;
    else if (state.elements < __MinHDF5ChunkSize) chunk_state = __MinHDF5ChunkSize;
    else chunk_state = state.elements;

    if (event.elements > __MaxHDF5ChunkSize) chunk_event = __MaxHDF5ChunkSize;
    else if (event.elements < __MinHDF5ChunkSize) chunk_event = __MinHDF5ChunkSize;
    else chunk_event = event.elements;

    if (comm.elements > __MaxHDF5ChunkSize/2) chunk_comm = __MaxHDF5ChunkSize/2;
    else if (comm.elements < __MinHDF5ChunkSize/2) chunk_comm = __MinHDF5ChunkSize/2;
    else chunk_comm = comm.elements;
    // Creates tables
    H5TBmake_table("State records", loc_id, STATE_DATASET_NAME, STATE_RECORD_ELEM, state.elements, sizeof(state_row), __State_field_names, State_offset, __State_field_type, chunk_state, NULL, __CompressionLevel, (state_row *) state.array);
    H5TBmake_table("Event records", loc_id, EVENT_DATASET_NAME, EVENT_RECORD_ELEM, event.elements, sizeof(event_row), __Event_field_names, __Event_offset, __Event_field_type, chunk_event, NULL, __CompressionLevel, (event_row *) event.array);
    H5TBmake_table("Communication records", loc_id, COMM_DATASET_NAME, COMM_RECORD_ELEM, comm.elements, sizeof(comm_row), __Comm_field_names, __Comm_offset, __Comm_field_type, chunk_comm, NULL, __CompressionLevel, (comm_row *) comm.array);
    #ifdef PROFILING
    REGISTER_TIME(&end);
    printf("==PROFILING== El. time creating HDF5T: %.3f sec.\n", GET_ELAPSED_TIME(start, end));
    #endif
}

/*Appends more rows to the HDF5 tables.*/
void extend_HDF5tables(const hid_t loc_id, record_Array state, record_Array event, record_Array comm) {
    #ifdef PROFILING
    struct timeval start, end;
    REGISTER_TIME(&start);
    #endif
    state_row state_sample; 
    event_row ev_sample;
    comm_row comm_sample;
    size_t state_field_size[STATE_RECORD_ELEM] = {sizeof(state_sample.cpu_id), 
                                                  sizeof(state_sample.appl_id), 
                                                  sizeof(state_sample.task_id), 
                                                  sizeof(state_sample.thread_id), 
                                                  sizeof(state_sample.time_ini), 
                                                  sizeof(state_sample.time_fi), 
                                                  sizeof(state_sample.state)};
    size_t event_field_size[EVENT_RECORD_ELEM] = {sizeof(ev_sample.cpu_id), 
                                                  sizeof(ev_sample.appl_id), 
                                                  sizeof(ev_sample.task_id), 
                                                  sizeof(ev_sample.thread_id), 
                                                  sizeof(ev_sample.time), 
                                                  sizeof(ev_sample.event_t), 
                                                  sizeof(ev_sample.event_v)};
    size_t comm_field_size[COMM_RECORD_ELEM] = {sizeof(comm_sample.cpu_send_id), 
                                                sizeof(comm_sample.ptask_send_id), 
                                                sizeof(comm_sample.task_send_id), 
                                                sizeof(comm_sample.thread_send_id), sizeof(comm_sample.lsend), 
                                                sizeof(comm_sample.psend), 
                                                sizeof(comm_sample.cpu_recv_id), 
                                                sizeof(comm_sample.ptask_recv_id), 
                                                sizeof(comm_sample.task_recv_id), 
                                                sizeof(comm_sample.thread_recv_id), sizeof(comm_sample.lrecv), 
                                                sizeof(comm_sample.precv), 
                                                sizeof(comm_sample.size), 
                                                sizeof(comm_sample.tag)};

    H5TBappend_records(loc_id, STATE_DATASET_NAME, state.elements, sizeof(state_row), State_offset, state_field_size, (state_row *) state.array);

    H5TBappend_records(loc_id, EVENT_DATASET_NAME, event.elements, sizeof(event_row), __Event_offset, event_field_size, (event_row *) event.array);

    H5TBappend_records(loc_id, COMM_DATASET_NAME, comm.elements, sizeof(comm_row), __Comm_offset, comm_field_size, (comm_row *) comm.array);
    #ifdef PROFILING
    REGISTER_TIME(&end);
    printf("==PROFILING== El. time to extend HDF5T: %.3f sec.\n", GET_ELAPSED_TIME(start, end));
    #endif
}

/*Principal function that reads-parses-writes.*/
void parse_prv_to_hdf5(const char * prv_file, const char * hdf5_file) {
    size_t read_bytes, ret;
    read_bytes = ret = 0;
    file_data file_d;
    record_Array records[3];
    hid_t file_id, record_group_id;
    int8_t first = TRUE;  // Bool
    file_id = create_HDF5(hdf5_file);
    record_group_id = create_HDF5_group(file_id, HDF5_GROUP_NAME);
    // Reads the files in chunks
    while ( (ret = read_and_preprocess(prv_file, __ReadSize, read_bytes, &file_d)) > 0) {
        #ifdef PROFILING
        struct timeval start, end;
        REGISTER_TIME(&start);
        #endif
        
        if (__Verbose)
            printf("==VERBOSE== Read chunk of %.2f MB\n", (float)ret/(1024*1024));

        read_bytes += ret;
        // Parses the read data
        data_parser(&file_d, &records[0], &records[1], &records[2]);
        /* Frees buffers holdings file's data */
        free(file_d.buffer);
        free(file_d.lengths);
        free(file_d.types);
        if (first) {
            create_HDF5tables(record_group_id, records[0], records[1], records[2]);
            first = FALSE;
        }
        else extend_HDF5tables(record_group_id, records[0], records[1], records[2]);
        size_t i;
        for (i = 0; i < 3; i++) {
            free(records[i].array);
        }

        #ifdef PROFILING
        REGISTER_TIME(&end);
        printf("==PROFILING== El. time to process 1 chunk: %.3f sec.\n", GET_ELAPSED_TIME(start, end));
        #endif   
    }
    /*Frees HDF5 data structures.*/
    status = H5Fclose(file_id);
    if (__Verbose)
        printf("==VERBOSE== Total read %.2f MB.\n", (float)read_bytes/(1024*1024)); 
}

void init() {
    /*Initializes data structures to write an HDF5 file
    using the Table API.*/
    __State_field_type[0] = H5T_NATIVE_UINT; 
    __State_field_type[1] = H5T_NATIVE_USHORT; 
    __State_field_type[2] = H5T_NATIVE_UINT; 
    __State_field_type[3] = H5T_NATIVE_UINT; 
    __State_field_type[4] =  H5T_NATIVE_ULLONG; 
    __State_field_type[5] = H5T_NATIVE_ULLONG; 
    __State_field_type[6] = H5T_NATIVE_USHORT;
    State_offset[0] = HOFFSET( state_row, cpu_id );
    State_offset[1] = HOFFSET( state_row, appl_id );
    State_offset[2] = HOFFSET( state_row, task_id );
    State_offset[3] = HOFFSET( state_row, thread_id );
    State_offset[4] = HOFFSET( state_row, time_ini );
    State_offset[5] = HOFFSET( state_row, time_fi );
    State_offset[6] = HOFFSET( state_row, state );

    __Event_field_type[0] = H5T_NATIVE_UINT;
    __Event_field_type[1] = H5T_NATIVE_USHORT; 
    __Event_field_type[2] = H5T_NATIVE_UINT; 
    __Event_field_type[3] = H5T_NATIVE_UINT; 
    __Event_field_type[4] = H5T_NATIVE_ULLONG; 
    __Event_field_type[5] =  H5T_NATIVE_ULLONG; 
    __Event_field_type[6] = H5T_NATIVE_ULLONG;
    __Event_offset[0] = HOFFSET( event_row, cpu_id ); 
    __Event_offset[1] = HOFFSET( event_row, appl_id ); 
    __Event_offset[2] = HOFFSET( event_row, task_id ); 
    __Event_offset[3] = HOFFSET( event_row, thread_id ); 
    __Event_offset[4] = HOFFSET( event_row, time ); 
    __Event_offset[5] = HOFFSET( event_row, event_t ); 
    __Event_offset[6] = HOFFSET( event_row, event_v );

    __Comm_field_type[0] = H5T_NATIVE_UINT;
    __Comm_field_type[1] = H5T_NATIVE_UINT; 
    __Comm_field_type[2] = H5T_NATIVE_UINT; 
    __Comm_field_type[3] = H5T_NATIVE_UINT; 
    __Comm_field_type[4] = H5T_NATIVE_ULLONG; 
    __Comm_field_type[5] = H5T_NATIVE_ULLONG; 
    __Comm_field_type[6] = H5T_NATIVE_UINT; 
    __Comm_field_type[7] = H5T_NATIVE_UINT; 
    __Comm_field_type[8] = H5T_NATIVE_UINT; 
    __Comm_field_type[9] = H5T_NATIVE_UINT; 
    __Comm_field_type[10] = H5T_NATIVE_ULLONG; 
    __Comm_field_type[11] = H5T_NATIVE_ULLONG; 
    __Comm_field_type[12] = H5T_NATIVE_ULLONG; 
    __Comm_field_type[13] = H5T_NATIVE_ULLONG;
    __Comm_offset[0] = HOFFSET( comm_row, cpu_send_id );
    __Comm_offset[1] = HOFFSET( comm_row, ptask_send_id );
    __Comm_offset[2] = HOFFSET( comm_row, task_send_id );
    __Comm_offset[3] = HOFFSET( comm_row, thread_send_id );
    __Comm_offset[4] = HOFFSET( comm_row, lsend );
    __Comm_offset[5] = HOFFSET( comm_row, psend );
    __Comm_offset[6] = HOFFSET( comm_row, cpu_recv_id );
    __Comm_offset[7] = HOFFSET( comm_row, ptask_recv_id );
    __Comm_offset[8] = HOFFSET( comm_row, task_recv_id );
    __Comm_offset[9] = HOFFSET( comm_row, thread_recv_id );
    __Comm_offset[10] = HOFFSET( comm_row, lrecv );
    __Comm_offset[11] = HOFFSET( comm_row, precv );
    __Comm_offset[12] = HOFFSET( comm_row, size );
    __Comm_offset[13] = HOFFSET( comm_row, tag );
}

//const char *argp_program_version = "uberparser 0.0.1";
static char doc[] = "Parses the provided .prv trace generating an HDF5 with equivalent data";
static char args_doc[] = "PRV_FILE";

static struct argp_option options[] = {
    {"verbose", 'v', 0, 0, "Produces verbose output"},
    {"output", 'o', "FILE", 0, "Specifies the name of the output file"},
    {"chunk_size", 490, "MB", 0, "Limits maximum size of the file to hold in memory (default 1GB)"},
    {"comp_lvl", 'c', "LEVEL", 0, "Sets the compression level (between 0 and 9). Default is 0 (no compression)"},
    {"max_hdf5_chunk_size", 500, "MB", OPTION_HIDDEN, "Sets maximum HDF5 chunk size (defaul 4194304 elements)"},
    {"min_hdf5_chunk_size", 501, "MB", OPTION_HIDDEN, "Sets minimum HDF5 chunk size (default 4096 elements)"},
    {"event_capacity_extend_factor", 510, "FACTOR", OPTION_HIDDEN, "Sets the increase factor of the event buffer"},
    {0}
};

struct arguments {
    char *args[1];
    char *output_file;
};

static error_t parse_opt(int key, char *arg, struct argp_state *state) {
    /*Parses program's options.*/
    struct arguments *arguments = state->input;
    switch(key) {
        case 'v':
            __Verbose = TRUE;
            break;

        case 'o': ;
        /* Ensures that the provided output file name ends with ".h5" */
            char *correct_name;
            if (strstr(arg, ".h5") == NULL) {
                correct_name = (char *)malloc(MAXBUF);
                strcpy(correct_name, arg);
                strncat(correct_name, ".h5", 3);
            }
            else correct_name = arg;
            arguments->output_file = correct_name;
            break;

        case 490: ;
            long long chunk;
            if ( (sscanf(arg, "%lld", &chunk) != 1) || (chunk <= 0) ) {
                printf("==ERROR== Bad option value: chunk_size must be a positive integer.\n");
                exit(EXIT_FAILURE);
            }
            __ReadSize = chunk*1024*1024;
            break;

        case 'c': ;
            int level;
            if ( (sscanf(arg, "%d", &level) != 1) || (level < 0) || (level > 9) ) {
                printf("==ERROR== Bad option value: comp_lvl must be an integer between 0 and 9.\n");
                exit(EXIT_FAILURE);
            }
            __CompressionLevel = level;
            break;

        case 500: ;
            long long size_max;
            if ( (sscanf(arg, "%lld", &size_max) != 1) || (size_max <= 0) ) {
                printf("==ERROR== Bad option value: max_hdf5_chunk_size must be a positive integer.\n");
                exit(EXIT_FAILURE);
            }
            __MaxHDF5ChunkSize = size_max;
            break;

        case 501: ;
            long long size_min;
            if ( (sscanf(arg, "%lld", &size_min) != 1) || (size_min <= 0) ) {
                printf("==ERROR== Bad option value: min_hdf5_chunk_size must be a positive integer.\n");
                exit(EXIT_FAILURE);
            }
            __MinHDF5ChunkSize = size_min;
            break;

        case 510: ;
            int factor;
            if ( (scanf(arg, "%d", &factor) != 1) || (factor <= 0) ) {
                printf("==ERROR== Bad option value: event_capacity_factor must be a positive integer.\n");
                exit(EXIT_FAILURE);
            }
            __ExtendEventCapacity = factor;
            break;

        case ARGP_KEY_INIT:
            arguments->output_file = NULL;
            break;

        case ARGP_KEY_ARG:
            if (state->arg_num >= 1) 
                argp_usage(state);
            arguments->args[state->arg_num] = arg;
            break;
        
        case ARGP_KEY_END:
            if (state->arg_num < 1)
                argp_usage(state);

            if (arguments->output_file == NULL) {
                char *name;
                name = (char *)malloc(MAXBUF);
                strcpy(name, arguments->args[0]);
                strncat(name, ".h5", 3);
                arguments->output_file = name;
            }
            break;
        
        default:
            return ARGP_ERR_UNKNOWN;
    }
    return 0;
}

static struct argp argp = {options, parse_opt, args_doc, doc};

void print_exec_environment(struct arguments arguments) {
    printf("==VERBOSE== Trace: %s\n", arguments.args[0]);
    printf("==VERBOSE== Output file: %s\n", arguments.output_file);
    printf("==VERBOSE== Chunk size: %.2f MB\n", __ReadSize / (1024.0*1024.0));
    printf("==VERBOSE== Compression level: %d\n", __CompressionLevel);
    printf("==VERBOSE== Max. HDF5 chunk size: %lld elements\n", __MaxHDF5ChunkSize);
    printf("==VERBOSE== Min. HDF5 chunk size: %lld elements\n", __MinHDF5ChunkSize);
    printf("==VERBOSE== Event capacity extend factor: %d\n", __ExtendEventCapacity);
}

int main(int argc, char **argv) {
    /*Program's main control flow.*/

    #ifdef PROFILING
    struct timeval start, end;
    REGISTER_TIME(&start);
    #endif
    // Argument's parsing
    struct arguments arguments;
    argp_parse(&argp, argc, argv, 0, 0, &arguments);
    if (__Verbose)
        print_exec_environment(arguments);

    // Initialization of some necessary data
    init();

    // Main function: parses the data and writes it to disk
    parse_prv_to_hdf5(arguments.args[0], arguments.output_file);

    // printf("==INFO== The output file is %s\n", arguments.output_file);
    
    #ifdef PROFILING
    REGISTER_TIME(&end);
    printf("==PROFILING== Tot. el. time: %.3f sec.\n", GET_ELAPSED_TIME(start, end));
    #endif
    return EXIT_SUCCESS;
}