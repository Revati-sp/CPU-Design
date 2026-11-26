/*
 * isa.c -- the MiniCPU-8 instruction table (one row per opcode).
 * The CPU decoder, the display code and the tests all use this table.
 */
#include "isa.h"

const InstrInfo ISA[16] = {
    /* opcode  mnemonic  format      operands      operation                     flags */
    /* 0x0 */ {"NOP",   F_NONE,    "-",          "no operation",               "-"  },
    /* 0x1 */ {"LDI",   F_REG_IMM, "Ra, imm8",   "Ra <- imm8",                 "-"  },
    /* 0x2 */ {"LOAD",  F_REG_MEM, "Ra, [addr]", "Ra <- RAM[addr]",            "-"  },
    /* 0x3 */ {"STORE", F_REG_MEM, "Ra, [addr]", "RAM[addr] <- Ra",            "-"  },
    /* 0x4 */ {"MOV",   F_REG_REG, "Ra, Rb",     "Ra <- Rb",                   "-"  },
    /* 0x5 */ {"ADD",   F_REG_REG, "Ra, Rb",     "Ra <- Ra + Rb",              "Z N"},
    /* 0x6 */ {"SUB",   F_REG_REG, "Ra, Rb",     "Ra <- Ra - Rb",              "Z N"},
    /* 0x7 */ {"MUL",   F_REG_REG, "Ra, Rb",     "Ra <- Ra * Rb (low 8 bits)", "Z N"},
    /* 0x8 */ {"INC",   F_REG,     "Ra",         "Ra <- Ra + 1",               "Z N"},
    /* 0x9 */ {"DEC",   F_REG,     "Ra",         "Ra <- Ra - 1",               "Z N"},
    /* 0xA */ {"CMP",   F_REG_REG, "Ra, Rb",     "Ra - Rb (flags only)",       "Z N"},
    /* 0xB */ {"JMP",   F_ADDR,    "addr",       "PC <- addr",                 "-"  },
    /* 0xC */ {"JZ",    F_ADDR,    "addr",       "if Z = 1: PC <- addr",       "-"  },
    /* 0xD */ {"JNZ",   F_ADDR,    "addr",       "if Z = 0: PC <- addr",       "-"  },
    /* 0xE */ {"---",   F_INVALID, "-",          "reserved (fault)",           "-"  },
    /* 0xF */ {"HALT",  F_NONE,    "-",          "stop the clock",             "-"  },
};

/* A word is legal if its opcode exists and every unused field is 0. */
int isa_valid(u16 word)
{
    Format f = ISA[OPCODE(word)].format;
    int uses_ra  = (f == F_REG_IMM || f == F_REG_MEM || f == F_REG_REG || f == F_REG);
    int uses_rb  = (f == F_REG_REG);
    int uses_imm = (f == F_REG_IMM || f == F_REG_MEM || f == F_ADDR);

    if (f == F_INVALID)           return 0;
    if (!uses_ra  && RA(word))    return 0;
    if (!uses_rb  && RB(word))    return 0;
    if (!uses_imm && IMM(word))   return 0;
    return 1;
}
