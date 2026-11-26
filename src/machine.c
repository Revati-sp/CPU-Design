/*
 * machine.c -- RAM, BUS, ALU and CPU of MiniCPU-8, all in one place.
 *
 * The CPU runs one clock cycle per call to cpu_clock_tick():
 *
 *   cycle 1  FETCH (hi)  MAR <- PC, MDR <- RAM[MAR] (bus READ), IR[15:8] <- MDR, PC++
 *   cycle 2  FETCH (lo)  MAR <- PC, MDR <- RAM[MAR] (bus READ), IR[7:0]  <- MDR, PC++
 *   cycle 3  DECODE      opcode, ra, rb, imm8 <- IR ; check the word is legal
 *   cycle 4  EXECUTE     do the operation (ALU, bus READ/WRITE, or PC change)
 *
 * No library functions are used in this file.
 */
#include "machine.h"

/* ======================================================================= */
/* RAM                                                                     */
/* ======================================================================= */
void ram_clear(RAM *ram)
{
    int i;
    for (i = 0; i < RAM_SIZE; i++)
        ram->cell[i] = 0;
}

/* ======================================================================= */
/* BUS                                                                     */
/* ======================================================================= */
void bus_init(Bus *bus, RAM *ram)
{
    bus->ram = ram;
    bus_idle(bus);
}

/* Nothing on the bus this cycle. */
void bus_idle(Bus *bus)
{
    bus->address = 0;
    bus->data    = 0;
    bus->control = BUS_IDLE;
}

/* READ cycle: put address on the bus, RAM answers on the data lines. */
u8 bus_read(Bus *bus, u8 address)
{
    bus->address = address;
    bus->control = BUS_READ;
    bus->data    = bus->ram->cell[address];
    return bus->data;
}

/* WRITE cycle: put address and data on the bus, RAM stores the data. */
void bus_write(Bus *bus, u8 address, u8 data)
{
    bus->address = address;
    bus->control = BUS_WRITE;
    bus->data    = data;
    bus->ram->cell[address] = data;
}

/* ======================================================================= */
/* ALU                                                                     */
/* ======================================================================= */
u8 alu_compute(ALU *alu, AluOp op, u8 a, u8 b)
{
    unsigned int y;              /* wide result, cut to 8 bits below */

    switch (op) {
    case ALU_ADD: y = a + b;  break;
    case ALU_SUB: y = a - b;  break;
    case ALU_MUL: y = a * b;  break;
    case ALU_INC: y = a + 1;  break;
    case ALU_DEC: y = a - 1;  break;
    case ALU_CMP: y = a - b;  break;   /* like SUB, result only used for flags */
    default:      y = 0;      break;
    }

    alu->op = op;
    alu->a  = a;
    alu->b  = b;
    alu->y  = (u8)(y & 0xFF);          /* 8-bit result, wraps modulo 256 */
    alu->z  = (alu->y == 0);           /* Z = result is zero             */
    alu->n  = (alu->y >> 7) & 1;       /* N = sign bit (bit 7)           */
    return alu->y;
}

/* ======================================================================= */
/* CPU                                                                     */
/* ======================================================================= */
void cpu_reset(CPU *cpu, Bus *bus)
{
    int i;
    cpu->pc = 0;  cpu->ir = 0;  cpu->mar = 0;  cpu->mdr = 0;
    for (i = 0; i < NUM_REGS; i++)
        cpu->r[i] = 0;
    cpu->z = 0;   cpu->n = 0;
    cpu->alu.op = ALU_NONE;
    cpu->alu.a = cpu->alu.b = cpu->alu.y = cpu->alu.z = cpu->alu.n = 0;
    cpu->phase  = PHASE_FETCH_HI;
    cpu->opcode = cpu->ra = cpu->rb = cpu->imm = 0;
    cpu->clock  = 0;
    cpu->halted = 0;
    cpu->fault  = FAULT_NONE;
    cpu->bus    = bus;
}

/* Stop the CPU because of an illegal state. */
static void cpu_fault(CPU *cpu, Fault f)
{
    cpu->fault  = f;
    cpu->halted = 1;
}

/* ALU instruction: Ra <- Ra (op) Rb, copy ALU flags into the flags register. */
static void execute_alu(CPU *cpu, AluOp op, int write_back)
{
    u8 b = (op == ALU_INC || op == ALU_DEC) ? 1 : cpu->r[cpu->rb];
    u8 y = alu_compute(&cpu->alu, op, cpu->r[cpu->ra], b);

    if (write_back)                    /* CMP keeps Ra unchanged */
        cpu->r[cpu->ra] = y;
    cpu->z = cpu->alu.z;
    cpu->n = cpu->alu.n;
}

/* Cycle 4: carry out the decoded instruction. */
static void execute(CPU *cpu)
{
    Bus *bus = cpu->bus;
    u8 ra = cpu->ra;

    switch (cpu->opcode) {
    case OP_NOP:                                              break;
    case OP_LDI:   cpu->r[ra] = cpu->imm;                     break;
    case OP_LOAD:  cpu->mar = cpu->imm;                       /* address -> MAR   */
                   cpu->mdr = bus_read(bus, cpu->mar);        /* bus READ -> MDR  */
                   cpu->r[ra] = cpu->mdr;                     /* MDR -> Ra        */
                   break;
    case OP_STORE: cpu->mar = cpu->imm;                       /* address -> MAR   */
                   cpu->mdr = cpu->r[ra];                     /* Ra -> MDR        */
                   bus_write(bus, cpu->mar, cpu->mdr);        /* bus WRITE        */
                   break;
    case OP_MOV:   cpu->r[ra] = cpu->r[cpu->rb];              break;
    case OP_ADD:   execute_alu(cpu, ALU_ADD, 1);              break;
    case OP_SUB:   execute_alu(cpu, ALU_SUB, 1);              break;
    case OP_MUL:   execute_alu(cpu, ALU_MUL, 1);              break;
    case OP_INC:   execute_alu(cpu, ALU_INC, 1);              break;
    case OP_DEC:   execute_alu(cpu, ALU_DEC, 1);              break;
    case OP_CMP:   execute_alu(cpu, ALU_CMP, 0);              break;
    case OP_JMP:   cpu->pc = cpu->imm;                        break;
    case OP_JZ:    if (cpu->z)  cpu->pc = cpu->imm;           break;
    case OP_JNZ:   if (!cpu->z) cpu->pc = cpu->imm;           break;
    case OP_HALT:  cpu->pc = (u8)(cpu->pc - 2);               /* PC stays on HALT */
                   cpu->halted = 1;
                   break;
    default:       cpu_fault(cpu, FAULT_BAD_OPCODE);          break;
    }
}

/* Run exactly one clock cycle. Returns the phase that was executed. */
Phase cpu_clock_tick(CPU *cpu)
{
    Phase now = cpu->phase;

    if (cpu->halted)
        return now;

    bus_idle(cpu->bus);                 /* bus is free unless this cycle uses it */
    cpu->clock++;

    switch (now) {
    case PHASE_FETCH_HI:
        if (cpu->pc & 1) {              /* instructions start at even addresses */
            cpu_fault(cpu, FAULT_BAD_PC);
            break;
        }
        cpu->alu.op = ALU_NONE;         /* new instruction: ALU not used yet */
        cpu->mar = cpu->pc;
        cpu->mdr = bus_read(cpu->bus, cpu->mar);
        cpu->ir  = (u16)(cpu->mdr << 8);            /* high byte */
        cpu->pc++;
        cpu->phase = PHASE_FETCH_LO;
        break;

    case PHASE_FETCH_LO:
        cpu->mar = cpu->pc;
        cpu->mdr = bus_read(cpu->bus, cpu->mar);
        cpu->ir  = (u16)(cpu->ir | cpu->mdr);       /* low byte */
        cpu->pc++;
        cpu->phase = PHASE_DECODE;
        break;

    case PHASE_DECODE:
        cpu->opcode = OPCODE(cpu->ir);
        cpu->ra     = RA(cpu->ir);
        cpu->rb     = RB(cpu->ir);
        cpu->imm    = IMM(cpu->ir);
        if (ISA[cpu->opcode].format == F_INVALID)
            cpu_fault(cpu, FAULT_BAD_OPCODE);
        else if (!isa_valid(cpu->ir))
            cpu_fault(cpu, FAULT_RESERVED_BITS);
        cpu->phase = PHASE_EXECUTE;
        break;

    case PHASE_EXECUTE:
        execute(cpu);
        cpu->phase = PHASE_FETCH_HI;
        break;
    }
    return now;
}
