/*
 * display.c -- formats everything the simulator prints.
 *
 * printf() is the ONLY library function used in the whole project,
 * and it is used only in this file.
 *
 * Conventions in the output
 *   binary   8-bit values as 8 digits, instruction words as oooo aa bb iiiiiiii
 *   hex      0x..
 *   ASCII    'c' for a printable character, ' .' for a control character
 *   *        value changed by the current instruction
 */
#include <stdio.h>
#include "display.h"

#define LINE  "=========================================================================================="
#define THIN  "------------------------------------------------------------------------------------------"

/* ======================================================================= */
/* Small printing helpers                                                  */
/* ======================================================================= */
static void spaces(int n)
{
    while (n-- > 0)
        printf(" ");
}

/* value as 'bits' binary digits, most significant first */
static void print_bits(unsigned value, int bits)
{
    while (bits-- > 0)
        printf("%c", ((value >> bits) & 1) ? '1' : '0');
}

/* instruction word split into its fields: oooo aa bb iiiiiiii */
static void print_fields(u16 w)
{
    print_bits(OPCODE(w), 4); printf(" ");
    print_bits(RA(w), 2);     printf(" ");
    print_bits(RB(w), 2);     printf(" ");
    print_bits(IMM(w), 8);
}

/* ASCII column: 'A' when printable, ' .' for a control character */
static void print_ascii(u8 c)
{
    if (c >= 0x20 && c <= 0x7E)
        printf("'%c'", c);
    else
        printf(" .");
}

static char changed(int c)
{
    return c ? '*' : ' ';
}

/* Assembly text of a word, e.g. "LOAD  R0, [0xF0]". Returns characters printed. */
static int disassemble(u16 w)
{
    const InstrInfo *in = &ISA[OPCODE(w)];

    if (!isa_valid(w))
        return printf("(invalid 0x%04X)", w);
    switch (in->format) {
    case F_NONE:    return printf("%s", in->mnemonic);
    case F_REG_IMM: return printf("%-5s R%d, %d", in->mnemonic, RA(w), IMM(w));
    case F_REG_MEM: return printf("%-5s R%d, [0x%02X]", in->mnemonic, RA(w), IMM(w));
    case F_REG_REG: return printf("%-5s R%d, R%d", in->mnemonic, RA(w), RB(w));
    case F_REG:     return printf("%-5s R%d", in->mnemonic, RA(w));
    case F_ADDR:    return printf("%-5s 0x%02X", in->mnemonic, IMM(w));
    default:        return printf("(invalid 0x%04X)", w);
    }
}

/* Generic binary pattern of an instruction format, e.g. "aa bb 00000000" */
static const char *format_pattern(Format f)
{
    switch (f) {
    case F_NONE:    return "00 00 00000000";
    case F_REG_IMM: return "aa 00 iiiiiiii";
    case F_REG_MEM: return "aa 00 dddddddd";
    case F_REG_REG: return "aa bb 00000000";
    case F_REG:     return "aa 00 00000000";
    case F_ADDR:    return "00 00 dddddddd";
    default:        return "-- -- --------";
    }
}

/* ======================================================================= */
/* Architecture and ISA                                                    */
/* ======================================================================= */
void show_architecture(void)
{
    printf("%s\n", LINE);
    printf(" MiniCPU-8 : 8-bit CPU, 16-bit instructions, 256-byte RAM\n");
    printf("%s\n", LINE);
    printf("   +------------------------------- CPU --------------------------------+\n");
    printf("   |  CONTROL UNIT : clock, phase FETCH -> DECODE -> EXECUTE             |\n");
    printf("   |  SPECIAL REGS : PC (8)   IR (16)   MAR (8)   MDR (8)                |\n");
    printf("   |  GENERAL REGS : R0  R1  R2  R3   (8 bits each)                      |\n");
    printf("   |  ALU          : ADD SUB MUL INC DEC CMP  (A, B -> Y)    FLAGS: Z  N |\n");
    printf("   +-------------------------------------+------------------------------+\n");
    printf("            MAR -> address bus (8 bits)  |  MDR <-> data bus (8 bits)\n");
    printf("            READ / WRITE control line    |\n");
    printf("   ======================================+=================== SYSTEM BUS\n");
    printf("                                         |\n");
    printf("                          +--------------+--------------+\n");
    printf("                          |        RAM  256 x 8 bits    |\n");
    printf("                          |  0x00-0x7F code             |\n");
    printf("                          |  0x80-0xEF free             |\n");
    printf("                          |  0xF0-0xFF data (a, b, c)   |\n");
    printf("                          +-----------------------------+\n\n");
}

void show_isa_table(void)
{
    int op;

    printf("%s\n", LINE);
    printf(" INSTRUCTION SET   (word = oooo aa bb iiiiiiii : opcode, reg A, reg B, imm8/addr8)\n");
    printf("%s\n", LINE);
    printf("  MNEMONIC  OPCODE  BINARY ENCODING       OPERANDS     OPERATION                   FLAGS\n");
    printf("  --------  ------  --------------------  -----------  --------------------------  -----\n");
    for (op = 0; op < 16; op++) {
        const InstrInfo *in = &ISA[op];
        printf("  %-8s  0x%X     ", in->mnemonic, op);
        print_bits(op, 4);
        printf(" %-14s   %-11s  %-26s  %s\n",
               format_pattern(in->format), in->operands, in->operation, in->flags);
    }
    printf("  Registers: 00 = R0, 01 = R1, 10 = R2, 11 = R3.   Unused fields must be 0.\n");
    printf("  Flags: Z = 1 if result is 0;  N = bit 7 of result.  Arithmetic wraps modulo 256.\n\n");
}

/* ======================================================================= */
/* Program: C source and hand translation                                  */
/* ======================================================================= */
void show_program(const Program *p)
{
    int i;

    printf("%s\n", LINE);
    printf(" PROGRAM : %s\n", p->title);
    printf("%s\n", LINE);

    printf("[1] C SOURCE  (%s)\n\n", p->c_file);
    for (i = 0; p->c_source[i]; i++) {
        if (p->c_source[i][0])
            printf("      %s", p->c_source[i]);
        printf("\n");
    }

    printf("\n[2] HAND TRANSLATION  C -> ASSEMBLY -> BINARY  (words loaded into RAM, high byte first)\n\n");
    printf("  ADDR  BINARY (oooo aa bb iiiiiiii)  HEX     ASSEMBLY           C MEANING\n");
    printf("  ----  ----------------------------  ------  -----------------  --------------\n");
    for (i = 0; i < p->code_len; i++) {
        u16 w = p->code[i];
        printf("  0x%02X  ", i * 2);
        print_fields(w);
        printf("           0x%04X  ", w);
        spaces(19 - disassemble(w));
        printf("%s\n", p->c_meaning[i]);
    }
    printf("\n  ADDR  BINARY    HEX   DEC  C VARIABLE\n");
    printf("  ----  --------  ----  ---  ----------\n");
    for (i = 0; i < p->data_len; i++) {
        printf("  0x%02X  ", p->data[i].addr);
        print_bits(p->data[i].value, 8);
        printf("  0x%02X  %3u  %s\n", p->data[i].value, p->data[i].value, p->data[i].name);
    }
    printf("\n");
}

/* ======================================================================= */
/* RAM block: code area (left) and data area (right)                       */
/* ======================================================================= */

/* Name of the C variable stored at addr, or "" */
static const char *var_name(const Program *p, int addr)
{
    int i;
    for (i = 0; i < p->data_len; i++)
        if (p->data[i].addr == addr)
            return p->data[i].name;
    return "";
}

/* One RAM cell: "0xF2  01000001  41*  'A'". Returns characters printed (23 or 24). */
#define CELL_W 24
#define CELL_GAP 14
static int print_cell(const RAM *ram, int changed_addr, int addr)
{
    u8 v = ram->cell[addr];
    printf("0x%02X  ", addr);
    print_bits(v, 8);
    printf("  %02X%c  ", v, changed(addr == changed_addr));
    print_ascii(v);
    return (v >= 0x20 && v <= 0x7E) ? CELL_W : CELL_W - 1;
}

/* changed_addr = address written by this instruction (bus WRITE), or -1 */
void show_ram(const char *title, const RAM *ram, int changed_addr, const Program *p)
{
    int code_rows = p->code_len * 2 + 2;      /* program bytes + 2 empty cells */
    int data_start = 0xF0, data_rows = 4;     /* 0xF0 .. 0xF3                  */
    int row;

    printf("  %s\n", title);
    printf("  CODE AREA");
    spaces(CELL_W + CELL_GAP - 9);
    printf("DATA AREA\n");
    printf("  ADDR  BINARY    HEX  ASCII");
    spaces(CELL_W + CELL_GAP - 26);
    printf("ADDR  BINARY    HEX  ASCII  VARIABLE\n");
    for (row = 0; row < code_rows || row < data_rows; row++) {
        int width = 0;
        printf("  ");
        if (row < code_rows)
            width = print_cell(ram, changed_addr, row);
        if (row < data_rows) {
            spaces(CELL_W + CELL_GAP - width);
            width = print_cell(ram, changed_addr, data_start + row);
            if (var_name(p, data_start + row)[0]) {
                spaces(CELL_W + 2 - width);
                printf("%s", var_name(p, data_start + row));
            }
        }
        printf("\n");
    }
    printf("\n");
}

/* ======================================================================= */
/* One instruction: clock cycles, then CPU state                           */
/* ======================================================================= */
/* Copy the visible CPU and bus state into a snapshot, field by field. */
void take_snapshot(Snapshot *s, const CPU *cpu, Phase phase)
{
    int i;
    s->phase       = phase;
    s->bus_control = cpu->bus->control;
    s->bus_address = cpu->bus->address;
    s->bus_data    = cpu->bus->data;
    s->pc  = cpu->pc;   s->ir  = cpu->ir;
    s->mar = cpu->mar;  s->mdr = cpu->mdr;
    for (i = 0; i < NUM_REGS; i++)
        s->r[i] = cpu->r[i];
    s->z = cpu->z;      s->n = cpu->n;
    s->alu_op = cpu->alu.op;
    s->alu_a  = cpu->alu.a;  s->alu_b = cpu->alu.b;  s->alu_y = cpu->alu.y;
    s->opcode = cpu->opcode; s->ra = cpu->ra; s->rb = cpu->rb; s->imm = cpu->imm;
    s->clock  = cpu->clock;
    s->halted = cpu->halted;
    s->fault  = cpu->fault;
}

void show_execution_header(void)
{
    printf("[4] EXECUTION  (fetch-decode-execute, %d clock cycles per instruction)\n",
           CYCLES_PER_INSTRUCTION);
    printf("    '*' = changed by this instruction\n\n");
}

static const char *phase_name(Phase ph)
{
    switch (ph) {
    case PHASE_FETCH_HI:
    case PHASE_FETCH_LO: return "FETCH";
    case PHASE_DECODE:   return "DECODE";
    default:             return "EXECUTE";
    }
}

static const char *alu_symbol(AluOp op)
{
    switch (op) {
    case ALU_ADD: case ALU_INC:  return "+";
    case ALU_SUB: case ALU_DEC:
    case ALU_CMP:                return "-";
    case ALU_MUL:                return "*";
    default:                     return "?";
    }
}

/* Register-transfer description of what one clock cycle did. */
static void print_micro_ops(const Snapshot *cpu)
{
    int ra = cpu->ra, rb = cpu->rb;

    if (cpu->fault != FAULT_NONE && cpu->halted) {
        switch (cpu->fault) {
        case FAULT_BAD_OPCODE:    printf("FAULT: reserved opcode -> CPU stopped"); return;
        case FAULT_RESERVED_BITS: printf("FAULT: unused field not 0 -> CPU stopped"); return;
        case FAULT_BAD_PC:        printf("FAULT: PC is odd -> CPU stopped"); return;
        default:                  break;
        }
    }

    switch (cpu->phase) {
    case PHASE_FETCH_HI:
        printf("MAR<-PC, MDR<-RAM[MAR], IR[15:8]<-MDR, PC<-PC+1");
        return;
    case PHASE_FETCH_LO:
        printf("MAR<-PC, MDR<-RAM[MAR], IR[7:0]<-MDR,  PC<-PC+1");
        return;
    case PHASE_DECODE:
        printf("opcode=");  print_bits(cpu->opcode, 4);
        printf(" (%s)  ra=", ISA[cpu->opcode].mnemonic);  print_bits(ra, 2);
        printf("  rb=");    print_bits(rb, 2);
        printf("  imm8=");  print_bits(cpu->imm, 8);
        return;
    case PHASE_EXECUTE:
        break;
    }

    switch (cpu->opcode) {
    case OP_NOP:   printf("no operation"); break;
    case OP_LDI:   printf("R%d <- imm8 (%d)", ra, cpu->imm); break;
    case OP_LOAD:  printf("MAR<-0x%02X, MDR<-RAM[MAR], R%d<-MDR", cpu->imm, ra); break;
    case OP_STORE: printf("MAR<-0x%02X, MDR<-R%d, RAM[MAR]<-MDR", cpu->imm, ra); break;
    case OP_MOV:   printf("R%d <- R%d", ra, rb); break;
    case OP_ADD: case OP_SUB: case OP_MUL:
        printf("ALU: R%d <- R%d %s R%d; update Z N", ra, ra, alu_symbol(cpu->alu_op), rb); break;
    case OP_INC: case OP_DEC:
        printf("ALU: R%d <- R%d %s 1; update Z N", ra, ra, alu_symbol(cpu->alu_op)); break;
    case OP_CMP:   printf("ALU: R%d - R%d; update Z N only", ra, rb); break;
    case OP_JMP:   printf("PC <- 0x%02X", cpu->imm); break;
    case OP_JZ:    printf(cpu->z ? "Z=1 -> PC <- 0x%02X" : "Z=0 -> no jump (target 0x%02X)", cpu->imm); break;
    case OP_JNZ:   printf(!cpu->z ? "Z=0 -> PC <- 0x%02X" : "Z=1 -> no jump (target 0x%02X)", cpu->imm); break;
    case OP_HALT:  printf("stop the clock (PC stays on HALT)"); break;
    default:       break;
    }
}

static void print_bus(const Snapshot *s)
{
    if (s->bus_control == BUS_IDLE)
        printf("IDLE   ----  ----");
    else
        printf("%-5s  0x%02X  0x%02X", s->bus_control == BUS_READ ? "READ" : "WRITE",
               s->bus_address, s->bus_data);
}

/* Left half: one special-purpose register (binary, hex, changed mark) */
static void print_special(const char *name, unsigned v, unsigned old, int bits)
{
    printf("    %-3s = ", name);
    print_bits(v, bits);
    spaces(17 - bits);
    printf(bits == 16 ? "0x%04X%c   " : "0x%02X%c     ", v, changed(v != old));
}

/* Right half: one general-purpose register (binary, hex, decimal) */
static void print_general(int i, u8 v, u8 old)
{
    printf("     R%d = ", i);
    print_bits(v, 8);
    printf("  0x%02X  %3u%s\n", v, v, v != old ? "*" : "");
}

/* cycles[0..count-1] = state after each clock cycle; before = state before the instruction */
void show_instruction(int number, const Snapshot *cycles, int count,
                      const Snapshot *before)
{
    int i;
    const Snapshot *after = &cycles[count - 1];

    /* ---- header ---- */
    printf("%s\n", THIN);
    printf(" INSTRUCTION %d | PC = 0x%02X | IR = ", number, before->pc);
    if (count >= 2) {
        print_fields(after->ir);
        printf(" = 0x%04X | ", after->ir);
        disassemble(after->ir);
    } else {
        printf("(not fetched)");
    }
    printf("\n%s\n", THIN);

    /* ---- clock cycles ---- */
    printf("  CLK  PHASE    BUS: CTRL   ADDR  DATA   MICRO-OPERATIONS\n");
    for (i = 0; i < count; i++) {
        printf("  %03lu  %-7s       ", cycles[i].clock, phase_name(cycles[i].phase));
        print_bus(&cycles[i]);
        printf("   ");
        print_micro_ops(&cycles[i]);
        printf("\n");
    }

    /* ---- CPU state ---- */
    printf("\n  CPU STATE after this instruction\n");
    printf("  SPECIAL-PURPOSE REGISTERS               GENERAL-PURPOSE REGISTERS (bin, hex, dec)\n");
    print_special("PC",  after->pc,  before->pc,  8);  print_general(0, after->r[0], before->r[0]);
    print_special("IR",  after->ir,  before->ir, 16);  print_general(1, after->r[1], before->r[1]);
    print_special("MAR", after->mar, before->mar, 8);  print_general(2, after->r[2], before->r[2]);
    print_special("MDR", after->mdr, before->mdr, 8);  print_general(3, after->r[3], before->r[3]);

    printf("  ALU   : ");
    if (after->alu_op == ALU_NONE) {
        printf("not used by this instruction\n");
    } else {
        printf("%-4s A = ", ISA[after->opcode].mnemonic);
        print_bits(after->alu_a, 8);  printf(" (%u) %s ", after->alu_a, alu_symbol(after->alu_op));
        printf("B = ");  print_bits(after->alu_b, 8);  printf(" (%u) -> ", after->alu_b);
        printf("Y = ");  print_bits(after->alu_y, 8);
        printf(" (%u)%s\n", after->alu_y, after->alu_op == ALU_CMP ? "  [discarded]" : "");
    }
    printf("  FLAGS : Z = %d%c  N = %d%c", after->z, changed(after->z != before->z),
           after->n, changed(after->n != before->n));
    printf("     CLOCK: %lu cycles%s\n\n", after->clock, after->halted ? "     >>> CPU HALTED" : "");
}

/* ======================================================================= */
/* Result and summary                                                      */
/* ======================================================================= */
int show_result(const Program *p, const CPU *cpu, const RAM *ram, int instructions)
{
    u8 v = ram->cell[p->result_addr];
    int pass = (cpu->fault == FAULT_NONE && v == p->expected);

    printf("%s\n", LINE);
    printf(" RESULT  %s = RAM[0x%02X] = ", var_name(p, p->result_addr), p->result_addr);
    print_bits(v, 8);
    printf(" = 0x%02X = %u = ", v, v);
    print_ascii(v);
    printf("   expected %u -> %s\n", p->expected, pass ? "PASS" : "FAIL");
    printf("         %d instructions, %lu clock cycles\n", instructions, cpu->clock);
    printf("%s\n\n", LINE);
    return pass;
}

void show_summary(const Program *const *programs, const int *passed, int count)
{
    int i;
    printf("SUMMARY\n");
    for (i = 0; i < count; i++)
        printf("  [%s] %s\n", passed[i] ? "PASS" : "FAIL", programs[i]->title);
}

void show_usage(const char *exe)
{
    printf("usage: %s [all | add | mul | isa]\n", exe);
    printf("  all  architecture + ISA table + both programs (default)\n");
    printf("  add  Program 1: c = a + b\n");
    printf("  mul  Program 2: c = a * b\n");
    printf("  isa  architecture + ISA table only\n");
}
