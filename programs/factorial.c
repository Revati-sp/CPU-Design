/*
 * Program B -- 5! = 120        (C source, manually translated to
 *                               programs/factorial.asm for MiniCPU-8)
 *
 * Each global variable maps to one fixed MiniCPU-8 RAM byte:
 *     result -> RAM[0xF0]      n -> RAM[0xF1]      i -> RAM[0xF2]
 *
 * unsigned char = 8 bits, matching the CPU word size (5! = 120 fits).
 *
 * Reference build on a normal computer (optional cross-check):
 *     cc programs/factorial.c -o factorial && ./factorial
 */
#include <stdio.h>

unsigned char result;           /* RAM[0xF0] */
unsigned char n = 5;            /* RAM[0xF1] */
unsigned char i;                /* RAM[0xF2] */

int main(void)
{
    result = 1;
    for (i = n; i > 1; i--) {
        result *= i;
    }

    printf("5! = %u\n", (unsigned)result);
    return 0;
}
