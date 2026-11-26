# MiniCPU-8

**CMPE-220 – Systems Software** · Instructor: Prof. Ishie Eswar
**Team:** Revati Dharmadhikari, Renuka Patwari, Atharva Mokashi

A simulator, written in C, for an 8-bit CPU we designed with our own 16-bit
instruction set. The CPU reaches RAM only through a simulated bus, and the
simulator runs one clock cycle at a time (fetch, fetch, decode, execute).
After every instruction it prints the clock cycles, the bus, all registers,
the ALU, the flags, and RAM in binary, hex and ASCII.

| Program | C source | Result in RAM[0xF2] |
|---------|----------|---------------------|
| 1: add two numbers | `c = a + b;` (40 + 25) | `01000001` = 0x41 = **65** = `'A'` |
| 2: multiply two numbers | `c = a * b;` (8 × 9) | `01001000` = 0x48 = **72** = `'H'` |

Each C program was translated by hand into assembly and then into binary.
The binary words sit in [src/programs.c](src/programs.c) and are loaded into
RAM before the program runs.

Report (diagrams, ISA table, traces, team contributions):
[docs/CPU_Design_Report.pdf](docs/CPU_Design_Report.pdf)

## Requirements

- A C compiler: GCC or Clang (on macOS run `xcode-select --install` once).
  The binary constants such as `0b0010` need GCC or Clang.
- `make` (optional: see "Without make" below).

The code uses no library functions except `printf`, as the assignment requires.

## Compile and Run

```bash
make            # builds ./minicpu
./minicpu       # architecture, ISA table, both programs, summary
```

The run ends with:

```text
SUMMARY
  [PASS] ADD two numbers  (c = a + b)
  [PASS] MULTIPLY two numbers  (c = a * b)
```

### Without make

```bash
cc -std=c99 src/*.c -o minicpu
./minicpu
```

## Commands

| Command | What it does |
|---------|--------------|
| `./minicpu` | architecture diagram, ISA table, both programs, PASS/FAIL summary |
| `./minicpu add` | Program 1 only |
| `./minicpu mul` | Program 2 only |
| `./minicpu isa` | architecture diagram and ISA table only |
| `make test` | run the automated tests (64 checks) |
| `make check-c` | compile and run the original C programs natively (prints `c = 65`, `c = 72`) |
| `make traces` | save the output to `output/` |
| `make zip` | build the submission zip `MiniCPU-8.zip` |
| `make clean` | remove build files |

Tip: `./minicpu add | less` lets you scroll through the trace.

## How to Read the Output

For each instruction the simulator prints:

```text
 INSTRUCTION 3 | PC = 0x04 | IR = 0101 00 01 00000000 = 0x5100 | ADD   R0, R1
  CLK  PHASE    BUS: CTRL   ADDR  DATA   MICRO-OPERATIONS
  009  FETCH         READ   0x04  0x51   MAR<-PC, MDR<-RAM[MAR], IR[15:8]<-MDR, PC<-PC+1
  010  FETCH         READ   0x05  0x00   MAR<-PC, MDR<-RAM[MAR], IR[7:0]<-MDR,  PC<-PC+1
  011  DECODE        IDLE   ----  ----   opcode=0101 (ADD)  ra=00  rb=01  imm8=00000000
  012  EXECUTE       IDLE   ----  ----   ALU: R0 <- R0 + R1; update Z N

  CPU STATE after this instruction
  SPECIAL-PURPOSE REGISTERS               GENERAL-PURPOSE REGISTERS (bin, hex, dec)
    PC  = 00000110         0x06*          R0 = 01000001  0x41   65*
    IR  = 0101000100000000 0x5100*        R1 = 00011001  0x19   25
    MAR = 00000101         0x05*          R2 = 00000000  0x00    0
    MDR = 00000000         0x00*          R3 = 00000000  0x00    0
  ALU   : ADD  A = 00101000 (40) + B = 00011001 (25) -> Y = 01000001 (65)
  FLAGS : Z = 0   N = 0      CLOCK: 12 cycles
```

This is followed by the RAM block (code area and data area) in binary, hex
and ASCII. A `*` marks a value the instruction changed.

## Project Structure

```text
.
├── README.md
├── Makefile
├── src/
│   ├── isa.h / isa.c            ISA: opcodes, instruction format, instruction table
│   ├── machine.h / machine.c    hardware: RAM, bus, ALU, CPU, clock (fetch-decode-execute)
│   ├── programs.h / programs.c  hand-encoded binary of both programs + loader
│   ├── display.h / display.c    all printing (the only file that uses printf)
│   └── main.c                   command line; runs the clock, prints each instruction
├── programs/
│   ├── add.c                    Program 1 in C
│   └── multiply.c               Program 2 in C
├── tests/
│   └── test_cpu.c               automated tests (make test)
├── output/                      saved simulator output (make traces)
└── docs/
    ├── CPU_Design_Report.pdf    the report
    └── report/                  report source (Git repository only, not in the zip)
```

## Instruction Set

Each instruction is one 16-bit word, stored high byte first:
`[15:12] opcode | [11:10] ra | [9:8] rb | [7:0] imm8/addr8`.
Fields an instruction does not use must be 0. Opcode `0xE` is reserved: the
CPU stops with a fault.

| Mnemonic | Opcode | Encoding | Operation | Flags |
|----------|--------|----------|-----------|-------|
| `NOP` | 0x0 | `0000 00 00 00000000` | no operation | - |
| `LDI` | 0x1 | `0001 aa 00 iiiiiiii` | Ra ← imm8 | - |
| `LOAD` | 0x2 | `0010 aa 00 dddddddd` | Ra ← RAM[addr] | - |
| `STORE` | 0x3 | `0011 aa 00 dddddddd` | RAM[addr] ← Ra | - |
| `MOV` | 0x4 | `0100 aa bb 00000000` | Ra ← Rb | - |
| `ADD` | 0x5 | `0101 aa bb 00000000` | Ra ← Ra + Rb | Z N |
| `SUB` | 0x6 | `0110 aa bb 00000000` | Ra ← Ra − Rb | Z N |
| `MUL` | 0x7 | `0111 aa bb 00000000` | Ra ← Ra × Rb (low 8 bits) | Z N |
| `INC` | 0x8 | `1000 aa 00 00000000` | Ra ← Ra + 1 | Z N |
| `DEC` | 0x9 | `1001 aa 00 00000000` | Ra ← Ra − 1 | Z N |
| `CMP` | 0xA | `1010 aa bb 00000000` | Ra − Rb, flags only | Z N |
| `JMP` | 0xB | `1011 00 00 dddddddd` | PC ← addr | - |
| `JZ` | 0xC | `1100 00 00 dddddddd` | if Z = 1: PC ← addr | - |
| `JNZ` | 0xD | `1101 00 00 dddddddd` | if Z = 0: PC ← addr | - |
| `HALT` | 0xF | `1111 00 00 00000000` | stop the clock | - |

Registers: `00` = R0, `01` = R1, `10` = R2, `11` = R3.
Z = 1 when the result is 0; N = bit 7 of the result. Arithmetic wraps modulo 256.

## Memory Map

| Address | Contents |
|---------|----------|
| `0x00–0x7F` | code area (both programs use `0x00–0x09`: 5 instructions × 2 bytes) |
| `0x80–0xEF` | free |
| `0xF0` | `a` (input) |
| `0xF1` | `b` (input) |
| `0xF2` | `c` (result) |
| `0xF3–0xFF` | spare |

## Team Contributions

| Member | Area | Contribution |
|--------|------|--------------|
| Revati Dharmadhikari | ISA, ALU & Program 1 | Designed the instruction format and opcode map (`src/isa.h`, `src/isa.c`) and wrote the ALU with Z/N flags (`alu_compute()`). Wrote Program 1 (`programs/add.c`) and its hand translation to binary. Wrote the automated tests (`tests/test_cpu.c`) and the ISA section of the report. |
| Renuka Patwari | RAM, bus & Program 2 | Wrote the RAM, the system bus and the program loader (`bus_read()`, `bus_write()`, `program_load()`). Wrote Program 2 (`programs/multiply.c`), its hand translation, and the RAM display in binary/hex/ASCII (`show_ram()`). Drew the CPU–Bus–RAM diagram and wrote the architecture and program sections of the report. |
| Atharva Mokashi | CPU, clock & trace | Wrote the CPU control unit and clock: fetch-decode-execute, instruction execution and fault checks (`cpu_clock_tick()`, `execute()`). Wrote the per-cycle trace of bus, registers, ALU and flags (`show_instruction()`, `src/main.c`), the Makefile and this README. Drew the clock diagram and wrote the code, clock and how-to-run sections of the report. |

## Rebuilding the Report (Git repository only)

The submitted zip already contains the finished PDF, but not the report's
source (`docs/report/`). To rebuild the PDF from a copy of the Git
repository, you need Google Chrome. The PDF's traces and code listings are
filled in from the simulator's live output:

```bash
sh docs/report/build.sh
```
