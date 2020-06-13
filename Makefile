SRCDIR   = src
OBJDIR   = obj
BINDIR   = bin

TARGET   = prv_parser

CC       = gcc
CFLAGS   = -O3 -march=native -fPIC -shared

LINKER   = gcc
LDFLAGS   = -lhdf5 -lhdf5_hl

ifneq (${HDF5_HOME},)
	HDF5_DIR	= $(HDF5_HOME)
	CFLAGS	+= -I$(HDF5_DIR)/include
	LDFLAGS	+= -L$(HDF5_DIR)/lib -Wl,-rpath=$(HDF5_DIR)/lib
endif

SOURCES  := $(wildcard $(SRCDIR)/*.c)
INCLUDES := $(wildcard $(SRCDIR)/*.h)
OBJECTS  := $(SOURCES:$(SRCDIR)/%.c=$(OBJDIR)/%.o)
rm       = rm -f


$(BINDIR)/$(TARGET): $(OBJECTS)
	@$(LINKER) $(OBJECTS) $(LDFLAGS) -o $@

$(OBJECTS): $(OBJDIR)/%.o : $(SRCDIR)/%.c
	@$(CC) $(CFLAGS)  -c $< -o $@

.PHONY: clean
clean:
	@$(rm) $(OBJECTS)
	@$(rm) $(BINDIR)/$(TARGET)

