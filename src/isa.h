/*
 * isa.h -- MiniCPU-8 Instruction Set Architecture (ISA)
 *
 * Every instruction is ONE 16-bit word, stored in RAM high byte first
 * (big-endian): RAM[PC] = bits 15..8, RAM[PC+1] = bits 7..0.
 *
 *     15      12 11  10 9    8 7                0
 *    +---------+------+------+------------------+
 *    | opcode  |  ra  |  rb  |   imm8 / addr8   |
 *    +---------+------+------+------------------+
 *      4 bits   2 bits 2 bits       8 bits
 *
 * A field that an instruction does not use MUST be 0, otherwise the CPU
 * stops with a fault. That way every 16-bit word has exactly one meaning.
 */
#ifndef ISA_H
#define ISA_H

typedef unsigned char  u8;   /* 8 bits : registers, RAM cells, addresses */
typedef unsigned short u16;  /* 16 bits: one instruction word            */

/* ---- Opcodes (bits 15..12) -------------------------------------------- */
enum {
    OP_NOP   = 0x0,  /* 0000  no operation                        */
    OP_LDI   = 0x1,  /* 0001  Ra <- imm8                          */
    OP_LOAD  = 0x2,  /* 0010  Ra <- RAM[addr8]                    */
    OP_STORE = 0x3,  /* 0011  RAM[addr8] <- Ra                    */
    OP_MOV   = 0x4,  /* 0100  Ra <- Rb                            */
    OP_ADD   = 0x5,  /* 0101  Ra <- Ra + Rb          (sets Z, N)  */
    OP_SUB   = 0x6,  /* 0110  Ra <- Ra - Rb          (sets Z, N)  */
    OP_MUL   = 0x7,  /* 0111  Ra <- Ra * Rb, low 8 bits (Z, N)    */
    OP_INC   = 0x8,  /* 1000  Ra <- Ra + 1           (sets Z, N)  */
    OP_DEC   = 0x9,  /* 1001  Ra <- Ra - 1           (sets Z, N)  */
    OP_CMP   = 0xA,  /* 1010  Ra - Rb, flags only    (sets Z, N)  */
    OP_JMP   = 0xB,  /* 1011  PC <- addr8                         */
    OP_JZ    = 0xC,  /* 1100  if Z = 1: PC <- addr8               */
    OP_JNZ   = 0xD,  /* 1101  if Z = 0: PC <- addr8               */
                     /* 1110  reserved -> fault                   */
    OP_HALT  = 0xF   /* 1111  stop the clock                      */
};

/* ---- Register codes (ra / rb fields) ----------------------------------- */
enum { R0 = 0, R1 = 1, R2 = 2, R3 = 3 };   /* 00, 01, 10, 11 */
#define NUM_REGS 4

/* ---- Build / split an instruction word --------------------------------- */
#define WORD(op, ra, rb, imm) \
    ((u16)(((op) << 12) | ((ra) << 10) | ((rb) << 8) | (imm)))

#define OPCODE(w) (((w) >> 12) & 0xF)   /* bits 15..12 */
#define RA(w)     (((w) >> 10) & 0x3)   /* bits 11..10 */
#define RB(w)     (((w) >>  8) & 0x3)   /* bits  9..8  */
#define IMM(w)    ((w) & 0xFF)          /* bits  7..0  */

/* ---- Operand formats: which fields an instruction uses ----------------- */
typedef enum {
    F_NONE,     /* oooo 00 00 00000000   NOP, HALT                 */
    F_REG_IMM,  /* oooo aa 00 iiiiiiii   LDI Ra, imm8              */
    F_REG_MEM,  /* oooo aa 00 dddddddd   LOAD/STORE Ra, [addr8]    */
    F_REG_REG,  /* oooo aa bb 00000000   MOV ADD SUB MUL CMP       */
    F_REG,      /* oooo aa 00 00000000   INC DEC                   */
    F_ADDR,     /* oooo 00 00 dddddddd   JMP JZ JNZ                */
    F_INVALID   /* reserved opcode                                 */
} Format;

/* One row of the instruction table */
typedef struct {
    const char *mnemonic;   /* e.g. "ADD"                    */
    Format      format;     /* operand format (see above)    */
    const char *operands;   /* e.g. "Ra, Rb"                 */
    const char *operation;  /* register-transfer meaning     */
    const char *flags;      /* "Z N" = updates flags, "-" = no */
} InstrInfo;

extern const InstrInfo ISA[16];          /* indexed by opcode 0x0..0xF */

int isa_valid(u16 word);                 /* 1 = legal instruction word */

#endif
