ifdef INTEL
    CC=icc
else
    CC=g++
endif

ifdef DEBUG
    CFLAGS=-c -g -fPIC -fpermissive -std=c++11
else
    CFLAGS=-c -fPIC -fpermissive -O3 -std=c++11
endif

LIBPATH=../../../libs/x64
INCLUDEPATH=../../../includes

INCLUDES=-I/usr/include -I$(INCLUDEPATH)
LDFLAGS=$(LIBPATH)/libstrategystudio_analytics.a $(LIBPATH)/libstrategystudio.a $(LIBPATH)/libstrategystudio_transport.a $(LIBPATH)/libstrategystudio_marketmodels.a $(LIBPATH)/libstrategystudio_utilities.a $(LIBPATH)/libstrategystudio_flashprotocol.a

LIBS=VWAP.so OFI.so VWAPOFI.so

VWAP_SOURCES=VWAP.cpp
VWAP_HEADERS=VWAP.h
VWAP_OBJECTS=$(VWAP_SOURCES:.cpp=.o)

OFI_SOURCES=OFI.cpp
OFI_HEADERS=OFI.h
OFI_OBJECTS=$(OFI_SOURCES:.cpp=.o)

VWAPOFI_SOURCES=VWAPOFI.cpp
VWAPOFI_HEADERS=VWAPOFI.h
VWAPOFI_OBJECTS=$(VWAPOFI_SOURCES:.cpp=.o)

all: $(LIBS)

VWAP.so: $(VWAP_OBJECTS)
	$(CC) -shared -Wl,-soname,$@.1 -o $@ $(VWAP_OBJECTS) $(LDFLAGS)

OFI.so: $(OFI_OBJECTS)
	$(CC) -shared -Wl,-soname,$@.1 -o $@ $(OFI_OBJECTS) $(LDFLAGS)

VWAPOFI.so: $(VWAPOFI_OBJECTS)
	$(CC) -shared -Wl,-soname,$@.1 -o $@ $(VWAPOFI_OBJECTS) $(LDFLAGS)

VWAP.o: VWAP.cpp $(VWAP_HEADERS)
	$(CC) $(CFLAGS) $(INCLUDES) $< -o $@

OFI.o: OFI.cpp $(OFI_HEADERS)
	$(CC) $(CFLAGS) $(INCLUDES) $< -o $@

VWAPOFI.o: VWAPOFI.cpp $(VWAPOFI_HEADERS)
	$(CC) $(CFLAGS) $(INCLUDES) $< -o $@

clean:
	rm -rf *.o *.so

copy_strategy: all
	cp *.so /student_work/howardd2/ss/bt/strategies_dlls/.
