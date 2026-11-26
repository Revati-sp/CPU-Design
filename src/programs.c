/*
 * programs.c -- the two demo programs.
 *
 * Each program was written in C first (programs/add.c, programs/multiply.c),
 * then translated BY HAND:   C statement -> assembly -> 16-bit binary word.
 * The binary words below are what gets loaded into RAM.
 *
 * Memory map used by both programs
 *     0x00 - 0x09   code (5 instructions x 2 bytes)
 *     0xF0          a   (input)
 *     0xF1          b   (input)
 *     0xF2          c   (result)
 *
 * WORD(opcode, ra, rb, imm8) packs the four fields: oooo aa bb iiiiiiii
 * (binary constants such as 0b0010 are supported by GCC and Clang).
 */
#include "programs.h"

/* ======================================================================= */
/* Program 1:  c = a + b;      a = 40, b = 25   ->   c = 65 (ASCII 'A')    */
/* ======================================================================= */
static const char *add_c_source[] = {
    "unsigned char a = 40;   /* RAM[0xF0] */",
    "unsigned char b = 25;   /* RAM[0xF1] */",
    "unsigned char c;        /* RAM[0xF2] */",
    "",
    "c = a + b;              /* c = 65    */",
    0
};

static const u16 add_code[] = {
    /*        opcode  ra    rb    imm8 / addr8         addr  assembly           */
    WORD(0b0010, 0b00, 0b00, 0b11110000),  /* 0x00  LOAD  R0, [0xF0]          */
    WORD(0b0010, 0b01, 0b00, 0b11110001),  /* 0x02  LOAD  R1, [0xF1]          */
    WORD(0b0101, 0b00, 0b01, 0b00000000),  /* 0x04  ADD   R0, R1              */
    WORD(0b0011, 0b00, 0b00, 0b11110010),  /* 0x06  STORE R0, [0xF2]          */
    WORD(0b1111, 0b00, 0b00, 0b00000000),  /* 0x08  HALT                      */
};

static const char *add_c_meaning[] = {
    "R0 = a",
    "R1 = b",
    "R0 = a + b",
    "c = R0",
    "end of program",
};

static const DataByte add_data[] = {
    {0xF0, 40, "a"},
    {0xF1, 25, "b"},
    {0xF2,  0, "c"},
};

const Program PROGRAM_ADD = {
    "add", "ADD two numbers  (c = a + b)", "programs/add.c",
    add_c_source, add_code, add_c_meaning, 5,
    add_data, 3,
    0xF2, 65
};

/* ======================================================================= */
/* Program 2:  c = a * b;      a = 8, b = 9     ->   c = 72 (ASCII 'H')    */
/* ======================================================================= */
static const char *mul_c_source[] = {
    "unsigned char a = 8;    /* RAM[0xF0] */",
    "unsigned char b = 9;    /* RAM[0xF1] */",
    "unsigned char c;        /* RAM[0xF2] */",
    "",
    "c = a * b;              /* c = 72    */",
    0
};

static const u16 mul_code[] = {
    /*        opcode  ra    rb    imm8 / addr8         addr  assembly           */
    WORD(0b0010, 0b00, 0b00, 0b11110000),  /* 0x00  LOAD  R0, [0xF0]          */
    WORD(0b0010, 0b01, 0b00, 0b11110001),  /* 0x02  LOAD  R1, [0xF1]          */
    WORD(0b0111, 0b00, 0b01, 0b00000000),  /* 0x04  MUL   R0, R1              */
    WORD(0b0011, 0b00, 0b00, 0b11110010),  /* 0x06  STORE R0, [0xF2]          */
    WORD(0b1111, 0b00, 0b00, 0b00000000),  /* 0x08  HALT                      */
};

static const char *mul_c_meaning[] = {
    "R0 = a",
    "R1 = b",
    "R0 = a * b",
    "c = R0",
    "end of program",
};

static const DataByte mul_data[] = {
    {0xF0, 8, "a"},
    {0xF1, 9, "b"},
    {0xF2, 0, "c"},
};

const Program PROGRAM_MUL = {
    "mul", "MULTIPLY two numbers  (c = a * b)", "programs/multiply.c",
    mul_c_source, mul_code, mul_c_meaning, 5,
    mul_data, 3,
    0xF2, 72
};

/* ======================================================================= */
/* Loader: copy the hand-encoded words into RAM, high byte first.          */
/* ======================================================================= */
void program_load(const Program *p, Bus *bus)
{
    int i;
    u8 addr = 0x00;                         /* code starts at address 0x00 */

    ram_clear(bus->ram);
    for (i = 0; i < p->code_len; i++) {
        bus_write(bus, addr++, (u8)(p->code[i] >> 8));    /* bits 15..8 */
        bus_write(bus, addr++, (u8)(p->code[i] & 0xFF));  /* bits  7..0 */
    }
    for (i = 0; i < p->data_len; i++)
        bus_write(bus, p->data[i].addr, p->data[i].value);
    bus_idle(bus);
}
