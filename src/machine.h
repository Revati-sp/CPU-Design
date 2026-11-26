/*
 * machine.h -- the simulated hardware: RAM, BUS, ALU and CPU.
 *
 *     +--------------------------- CPU ---------------------------+
 *     |  CONTROL UNIT      special: PC  IR  MAR  MDR              |
 *     |  (clock, phase)    general: R0  R1  R2  R3                |
 *     |  ALU (A, B, Y)     flags  : Z  N                          |
 *     +-------------------------------+---------------------------+
 *                                     |  address (8) / data (8) / control
 *     ================================+=========================== BUS
 *                                     |
 *                          +----------+----------+
 *                          |  RAM  256 x 8 bits  |
 *                          +---------------------+
 *
 * The CPU never touches RAM directly: every access goes through the bus
 * (MAR -> address lines, MDR <-> data lines, READ/WRITE on control line).
 */
#ifndef MACHINE_H
#define MACHINE_H

#include "isa.h"

/* ======================================================================= */
/* RAM : 256 cells of 8 bits (8-bit address)                               */
/* ======================================================================= */
#define RAM_SIZE 256

typedef struct {
    u8 cell[RAM_SIZE];
} RAM;

void ram_clear(RAM *ram);

/* ======================================================================= */
/* BUS : address lines, data lines, control line                           */
/* ======================================================================= */
typedef enum { BUS_IDLE, BUS_READ, BUS_WRITE } BusControl;

typedef struct {
    u8         address;   /* address lines (driven by MAR)      */
    u8         data;      /* data lines    (to/from MDR)        */
    BusControl control;   /* READ, WRITE or IDLE                */
    RAM       *ram;       /* the device on the other end        */
} Bus;

void bus_init (Bus *bus, RAM *ram);
void bus_idle (Bus *bus);
u8   bus_read (Bus *bus, u8 address);
void bus_write(Bus *bus, u8 address, u8 data);

/* ======================================================================= */
/* ALU : combinational unit, inputs A and B, output Y, flag outputs Z/N    */
/* ======================================================================= */
typedef enum { ALU_NONE, ALU_ADD, ALU_SUB, ALU_MUL, ALU_INC, ALU_DEC, ALU_CMP } AluOp;

typedef struct {
    AluOp op;      /* operation used this instruction (ALU_NONE = idle) */
    u8    a, b;    /* input operands                                    */
    u8    y;       /* 8-bit result (wraps modulo 256)                   */
    u8    z, n;    /* Z = (y == 0), N = bit 7 of y                      */
} ALU;

u8 alu_compute(ALU *alu, AluOp op, u8 a, u8 b);

/* ======================================================================= */
/* CPU                                                                     */
/* ======================================================================= */

/* One instruction = 4 clock cycles, in this order: */
typedef enum {
    PHASE_FETCH_HI,   /* cycle 1: IR[15:8] <- RAM[PC], PC <- PC + 1  */
    PHASE_FETCH_LO,   /* cycle 2: IR[7:0]  <- RAM[PC], PC <- PC + 1  */
    PHASE_DECODE,     /* cycle 3: split IR into opcode, ra, rb, imm8 */
    PHASE_EXECUTE     /* cycle 4: ALU / memory / branch              */
} Phase;
#define CYCLES_PER_INSTRUCTION 4

typedef enum {
    FAULT_NONE,
    FAULT_BAD_OPCODE,      /* opcode 0xE is reserved            */
    FAULT_RESERVED_BITS,   /* an unused field is not zero       */
    FAULT_BAD_PC           /* PC is odd (instructions are 2 B)  */
} Fault;

typedef struct {
    /* special-purpose registers */
    u8  pc;            /* program counter: address of next byte to fetch */
    u16 ir;            /* instruction register: current 16-bit word      */
    u8  mar;           /* memory address register -> bus address lines   */
    u8  mdr;           /* memory data register   <-> bus data lines      */

    /* general-purpose registers R0..R3 */
    u8  r[NUM_REGS];

    /* flags register */
    u8  z;             /* zero     */
    u8  n;             /* negative */

    /* arithmetic logic unit */
    ALU alu;

    /* control unit */
    Phase         phase;                 /* phase the NEXT clock tick runs */
    u8            opcode, ra, rb, imm;   /* decoded fields of IR           */
    unsigned long clock;                 /* clock cycles elapsed           */
    int           halted;                /* 1 after HALT or a fault        */
    Fault         fault;

    Bus *bus;          /* the system bus this CPU drives */
} CPU;

void  cpu_reset(CPU *cpu, Bus *bus);
Phase cpu_clock_tick(CPU *cpu);   /* run ONE clock cycle; returns its phase */

#endif
