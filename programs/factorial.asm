; ==========================================================================
; Program B -- 5! = 120
; Manual C-to-MiniCPU-8 Assembly Translation of programs/factorial.c
;   result = RAM[0xF0] (R0)   n = RAM[0xF1]   i = RAM[0xF2] (R1)   R2 = 1
;   "i > 1": CMP R1, R2 then JZ exits when i == 1  (valid for 1 <= n <= 5)
; ==========================================================================

        .org  0x00              ; ---- code ----
        LDI   R0, 1             ; result = 1;
        STORE R0, [result]      ;   (write variable back to RAM)
        LOAD  R1, [n]           ; for (i = n; ...
        STORE R1, [i]           ;   (write variable back to RAM)
        LDI   R2, 1             ;   (R2 = constant 1 for the loop test)
loop:   CMP   R1, R2            ; ... i > 1; ...  (flags <- i - 1)
        JZ    done              ;   (i == 1 -> leave loop)
        MUL   R0, R1            ;   result *= i;
        STORE R0, [result]      ;   (write variable back to RAM)
        DEC   R1                ; ... i--)
        STORE R1, [i]           ;   (write variable back to RAM)
        JMP   loop              ; }  (next iteration)
done:   HALT                    ; end: RAM[0xF0] = 120

        .org  0xF0              ; ---- data ----
result: .byte 0                 ; unsigned char result;
n:      .byte 5                 ; unsigned char n = 5;
i:      .byte 0                 ; unsigned char i;
