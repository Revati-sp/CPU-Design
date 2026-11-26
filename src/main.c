/*
 * main.c -- MiniCPU-8 simulator entry point.
 *
 *   ./minicpu          architecture, ISA table, then both programs
 *   ./minicpu add      Program 1 only   (c = a + b)
 *   ./minicpu mul      Program 2 only   (c = a * b)
 *   ./minicpu isa      architecture and ISA table only
 *
 * For every program:  load binary into RAM -> show RAM -> run the clock,
 * showing the cycles, CPU state and RAM after every instruction.
 */
#include "machine.h"
#include "programs.h"
#include "display.h"

#define MAX_INSTRUCTIONS 1000     /* safety stop for runaway programs */

/* 1 if the strings are equal (own helper: no string library) */
static int same(const char *s, const char *t)
{
    while (*s && *s == *t) {
        s++;
        t++;
    }
    return *s == *t;
}

/* Load, run and trace one program. Returns 1 if the result is correct. */
static int run_program(const Program *p)
{
    RAM ram;
    Bus bus;
    CPU cpu;
    Snapshot before, cycles[CYCLES_PER_INSTRUCTION];
    int i, count, written, instructions = 0;

    /* power on: connect RAM to the bus, load the program, reset the CPU */
    bus_init(&bus, &ram);
    program_load(p, &bus);
    cpu_reset(&cpu, &bus);

    show_program(p);
    show_ram("[3] RAM AFTER LOADING  (before execution)", &ram, -1, p);
    show_execution_header();

    while (!cpu.halted && instructions < MAX_INSTRUCTIONS) {
        take_snapshot(&before, &cpu, cpu.phase);

        /* clock the CPU until this instruction is finished (4 cycles) */
        count = 0;
        do {
            Phase ran = cpu_clock_tick(&cpu);
            take_snapshot(&cycles[count], &cpu, ran);
            count++;
        } while (cpu.phase != PHASE_FETCH_HI && !cpu.halted);
        instructions++;

        /* the only way RAM changes is a bus WRITE cycle */
        written = -1;
        for (i = 0; i < count; i++)
            if (cycles[i].bus_control == BUS_WRITE)
                written = cycles[i].bus_address;

        show_instruction(instructions, cycles, count, &before);
        show_ram("RAM after this instruction", &ram, written, p);
    }
    return show_result(p, &cpu, &ram, instructions);
}

int main(int argc, char **argv)
{
    const Program *all[2];
    int passed[2];
    int i, n = 0;
    const char *mode = (argc > 1) ? argv[1] : "all";

    all[0] = &PROGRAM_ADD;
    all[1] = &PROGRAM_MUL;

    if (same(mode, "all") || same(mode, "isa")) {
        show_architecture();
        show_isa_table();
        if (same(mode, "isa"))
            return 0;
        for (i = 0; i < 2; i++)
            passed[n++] = run_program(all[i]);
        show_summary(all, passed, n);
        return (passed[0] && passed[1]) ? 0 : 1;
    }
    if (same(mode, "add"))
        return run_program(&PROGRAM_ADD) ? 0 : 1;
    if (same(mode, "mul"))
        return run_program(&PROGRAM_MUL) ? 0 : 1;

    show_usage(argv[0]);
    return 2;
}
