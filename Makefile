# MiniCPU-8 -- build and run
#
#   make            build ./minicpu
#   make run        run both programs (full trace)
#   make test       build and run the automated tests
#   make traces     save the traces to output/
#   make check-c    compile and run the original C programs natively
#   make zip        create the submission zip
#   make clean      remove build files

CC     ?= cc
CFLAGS ?= -std=c99 -Wall -Wextra -O2

SRC  = src/isa.c src/machine.c src/programs.c src/display.c src/main.c
LIB  = src/isa.c src/machine.c src/programs.c
HDR  = src/isa.h src/machine.h src/programs.h src/display.h

.PHONY: all run test traces check-c zip clean

all: minicpu

minicpu: $(SRC) $(HDR)
	$(CC) $(CFLAGS) $(SRC) -o minicpu

run: minicpu
	./minicpu

build/test_cpu: tests/test_cpu.c $(LIB) $(HDR)
	@mkdir -p build
	$(CC) $(CFLAGS) tests/test_cpu.c $(LIB) -o build/test_cpu

test: build/test_cpu
	./build/test_cpu

traces: minicpu
	@mkdir -p output
	./minicpu add > output/add_trace.txt
	./minicpu mul > output/multiply_trace.txt
	./minicpu     > output/full_run.txt
	@echo "traces written to output/"

check-c:
	@mkdir -p build
	$(CC) $(CFLAGS) programs/add.c -o build/add && ./build/add
	$(CC) $(CFLAGS) programs/multiply.c -o build/multiply && ./build/multiply

# the zip unpacks into one folder, MiniCPU-8/
zip: traces
	rm -rf build/MiniCPU-8 MiniCPU-8.zip
	mkdir -p build/MiniCPU-8/docs
	cp -R README.md Makefile src tests programs output build/MiniCPU-8/
	cp docs/CPU_Design_Report.pdf build/MiniCPU-8/docs/
	cd build && zip -qr ../MiniCPU-8.zip MiniCPU-8
	@echo "created MiniCPU-8.zip"

clean:
	rm -rf build minicpu MiniCPU-8.zip
