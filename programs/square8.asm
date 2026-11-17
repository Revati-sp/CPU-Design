; ==========================================================================
; Program A -- 8^2 = 64        (written directly in MiniCPU-8 assembly)
;
;   Input  : x      = RAM[0xF1] = 8
;   Output : result = RAM[0xF0] = 64 (0x40)
; ==========================================================================

        .org  0x00              ; ---- code ----
start:  LOAD  R0, [x]           ; R0 <- RAM[0xF1]   (R0 = 8)
        MOV   R1, R0            ; R1 <- R0          (R1 = 8)
        MUL   R0, R1            ; R0 <- R0 * R1     (R0 = 64)
        STORE R0, [result]      ; RAM[0xF0] <- R0   (result = 64)
        HALT                    ; stop

        .org  0xF0              ; ---- data ----
result: .byte 0                 ; result (written by STORE)
x:      .byte 8                 ; input operand x = 8
