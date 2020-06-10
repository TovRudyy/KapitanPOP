CC          = gcc
CFLAGS      = -O3 -march=native
LDLIBS      = -lhdf5 -lhdf5_hl

ifneq (${HDF5_HOME},)
    HDF5_DIR    = $(HDF5_HOME)
    CFLAGS     += -I$(HDF5_DIR)/include
    LDFLAGS    += -L$(HDF5_DIR)/lib
endif

.PHONY: clean default install

default: ./src/prv_parser

install: ./src/prv_parser
	mkdir -p ./bin
	mv ./src/prv_parser ./bin

clean:
	$(RM) ./src/prv_parser

cleanall:
	$(RM) prv_parser
	$(RM) -rf ./bin
