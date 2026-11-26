/*
 * programs.h -- demo programs, hand-translated from C into MiniCPU-8 binary.
 */
#ifndef PROGRAMS_H
#define PROGRAMS_H

#include "machine.h"

/* One initialised data byte (a C variable living in RAM). */
typedef struct {
    u8          addr;    /* RAM address              */
    u8          value;   /* initial value            */
    const char *name;    /* C variable name          */
} DataByte;

typedef struct {
    const char  *key;          /* command-line name, e.g. "add"            */
    const char  *title;        /* e.g. "ADD two numbers"                   */
    const char  *c_file;       /* path of the original C program           */
    const char **c_source;     /* C source lines shown in the trace (NULL-ended) */
    const u16   *code;         /* hand-encoded instruction words           */
    const char **c_meaning;    /* C meaning of each instruction            */
    int          code_len;     /* number of instruction words              */
    const DataByte *data;      /* initialised variables                    */
    int          data_len;
    u8           result_addr;  /* where the answer is stored               */
    u8           expected;     /* answer the C program gives               */
} Program;

extern const Program PROGRAM_ADD;
extern const Program PROGRAM_MUL;

/* Clear RAM, then write the program's bytes and data into RAM via the bus. */
void program_load(const Program *p, Bus *bus);

#endif
