/*
 * display.h -- all screen output (the only code that calls printf).
 */
#ifndef DISPLAY_H
#define DISPLAY_H

#include "machine.h"
#include "programs.h"

/*
 * Snapshot of the CPU and bus taken right after one clock cycle.
 * Filled field by field (no structure copies), so the display can show
 * what each cycle did and which values changed.
 */
typedef struct {
    Phase         phase;                      /* phase this cycle ran      */
    BusControl    bus_control;                /* bus lines during the cycle */
    u8            bus_address, bus_data;
    u8            pc, mar, mdr;               /* special-purpose registers */
    u16           ir;
    u8            r[NUM_REGS];                /* general-purpose registers */
    u8            z, n;                       /* flags                     */
    AluOp         alu_op;                     /* ALU inputs and output     */
    u8            alu_a, alu_b, alu_y;
    u8            opcode, ra, rb, imm;        /* decoded fields            */
    unsigned long clock;
    int           halted;
    Fault         fault;
} Snapshot;

void take_snapshot(Snapshot *s, const CPU *cpu, Phase phase);

void show_architecture(void);
void show_isa_table(void);
void show_program(const Program *p);
void show_ram(const char *title, const RAM *ram, int changed_addr, const Program *p);
void show_execution_header(void);
void show_instruction(int number, const Snapshot *cycles, int count,
                      const Snapshot *before);
int  show_result(const Program *p, const CPU *cpu, const RAM *ram, int instructions);
void show_summary(const Program *const *programs, const int *passed, int count);
void show_usage(const char *exe);

#endif
