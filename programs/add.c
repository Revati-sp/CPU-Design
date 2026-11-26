/*
 * Program 1 -- add two numbers:  c = a + b  (40 + 25 = 65)
 *
 * Hand-translated to MiniCPU-8 binary in src/programs.c (PROGRAM_ADD).
 * Each variable lives at a fixed MiniCPU-8 RAM address:
 *     a -> RAM[0xF0]    b -> RAM[0xF1]    c -> RAM[0xF2]
 * unsigned char = 8 bits, the same as the CPU's data width.
 *
 * Optional cross-check on a normal computer:  make check-c
 */
#include <stdio.h>

unsigned char a = 40;           /* RAM[0xF0] */
unsigned char b = 25;           /* RAM[0xF1] */
unsigned char c;                /* RAM[0xF2] */

int main(void)
{
    c = a + b;                  /* LOAD R0,[a]  LOAD R1,[b]  ADD R0,R1  STORE R0,[c] */

    printf("c = %u\n", (unsigned)c);
    return 0;
}
