#!/bin/sh
# Build docs/CPU_Design_Report.pdf from docs/report/report.html.
#
# The template's markers are filled with LIVE output of the C simulator,
# so every trace and listing in the PDF is exactly what the code prints:
#   <!--@trace:FILE-->   simulator output, split into per-instruction blocks
#   <!--@code:FILE-->    source code listing
#   <!--@text:NAME-->    one short value (test count, PASS/FAIL)
#
# Needs: make, a C compiler, Google Chrome (headless print to PDF).
# Usage: sh docs/report/build.sh
set -e

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
OUT="$ROOT/build/report"
PDF="$ROOT/docs/CPU_Design_Report.pdf"
CHROME=${CHROME:-"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"}
mkdir -p "$OUT"

# ---- 1. build and run the simulator and tests -------------------------
make -s minicpu build/test_cpu
./minicpu add > "$OUT/add_trace.txt" && echo PASS > "$OUT/add_status.txt" || echo FAIL > "$OUT/add_status.txt"
./minicpu mul > "$OUT/mul_trace.txt" && echo PASS > "$OUT/mul_status.txt" || echo FAIL > "$OUT/mul_status.txt"
./build/test_cpu | tail -n 1 > "$OUT/tests.txt"

# ---- 2. code excerpts -------------------------------------------------
cp programs/add.c programs/multiply.c "$OUT/"
# the four hardware structs (RAM, Bus, ALU, CPU) from machine.h
awk '/^typedef struct {/{f=1} f{print} f && /^} [A-Za-z]+;/{f=0; print ""}' src/machine.h > "$OUT/machine_structs.txt"
# cpu_clock_tick() and bus_read()/bus_write() from machine.c
awk '/^\/\* Run exactly one clock cycle/{f=1} f{print} f && /^}/{exit}' src/machine.c > "$OUT/clock_tick.txt"
awk '/^\/\* READ cycle/{f=1} f{print} f && /^}/{n++; if (n == 2) exit}' src/machine.c > "$OUT/bus.txt"
# hand-encoded words of Program 1 and the loader, from programs.c
awk '/^static const u16 add_code/{f=1} f{print} f && /^};/{exit}' src/programs.c > "$OUT/add_code.txt"
awk '/^void program_load/{f=1} f{print} f && /^}/{exit}' src/programs.c > "$OUT/loader.txt"

# ---- 3. fill the template -----------------------------------------------
awk -v dir="$OUT" '
function esc(s) { gsub(/&/, "\\&amp;", s); gsub(/</, "\\&lt;", s); gsub(/>/, "\\&gt;", s); return s }

# source listing with grey comments
function code(file,    line, incom, out) {
    print "<pre>"
    incom = 0
    while ((getline line < file) > 0) {
        line = esc(line)
        if (incom) {
            if (line ~ /\*\//) { sub(/^.*\*\//, "<span class=\"cm\">&</span>", line); incom = 0 }
            else line = "<span class=\"cm\">" line "</span>"
        } else if (line ~ /\/\*/ && line !~ /\*\//) {
            sub(/\/\*.*$/, "<span class=\"cm\">&</span>", line); incom = 1
        } else {
            gsub(/\/\*[^*]*\*\//, "<span class=\"cm\">&</span>", line)
        }
        print line
    }
    close(file)
    print "</pre>"
}

# simulator trace: start at [3], one <pre> block per instruction
function trace(file,    line, on, prev, blanks, i) {
    on = 0; prev = ""; blanks = 0
    while ((getline line < file) > 0) {
        if (!on && line ~ /^ *\[3\]/) { on = 1; print "<pre class=\"blk\">" }
        if (!on) continue
        if (line == "") { blanks++; prev = line; continue }
        if ((line ~ /^-----+$/ && prev == "") || line ~ /^\[4\]/ || (line ~ /^=====+$/ && prev == "")) {
            print "</pre><pre class=\"blk\">"; blanks = 0
        }
        for (i = 0; i < blanks; i++) print ""
        blanks = 0
        prev = line
        line = esc(line)
        if (line ~ /RESULT/) line = "<span class=\"res\">" line "</span>"
        else if (line !~ /\/\*/) gsub(/[^ ]+\*/, "<span class=\"chg\">&</span>", line)
        print line
    }
    close(file)
    print "</pre>"
}

function text(name,    file, line) {
    file = dir "/" name ".txt"
    getline line < file; close(file)
    return esc(line)
}

{
    if (match($0, /<!--@code:[^>]*-->/))  { code(dir "/" substr($0, RSTART + 10, RLENGTH - 13)); next }
    if (match($0, /<!--@trace:[^>]*-->/)) { trace(dir "/" substr($0, RSTART + 11, RLENGTH - 14)); next }
    while (match($0, /<!--@text:[a-z_]+-->/)) {
        name = substr($0, RSTART + 10, RLENGTH - 13)
        $0 = substr($0, 1, RSTART - 1) text(name) substr($0, RSTART + RLENGTH)
    }
    print
}' docs/report/report.html > "$OUT/report.html"

# ---- 4. print to PDF ----------------------------------------------------
"$CHROME" --headless=new --disable-gpu --no-pdf-header-footer \
    --print-to-pdf="$PDF" "file://$OUT/report.html" 2>/dev/null
echo "wrote $PDF"
