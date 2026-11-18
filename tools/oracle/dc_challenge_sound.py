"""Trace Dreamcast Challenge transition sound requests on a Flycast RAM snapshot.

Usage: python dc_challenge_sound.py <snapshot.ram>
Requires the existing SH-4 interpreter's numpy dependency.
Runs transition routines directly. The two non-audio cleanup calls are stubbed.
The sound dispatcher executes normally through its bank/sequence mapping, while
the three AICA API calls are recorded without playback.
"""
import argparse
from pathlib import Path

from sh4 import SH4

TRANSITIONS = (
    ("success", 0x8C02A81A, 4, (21, 28)),
    ("result", 0x8C02A8A0, 5, (27, 28)),
    ("failure", 0x8C02A8D0, 6, (27,)),
)


def trace(ram, entry):
    machine = SH4()
    machine.ram[:] = ram
    cues = []
    sequences = []

    def observe(cpu, pc, opcode):
        if pc == 0x8C01203A:
            cues.append((cpu.r[4], cpu.r[5]))

    machine.trace = observe
    for address in (0x8C01A298, 0x8C016B1E):
        machine.hooks[address & 0x1FFFFFFF] = lambda cpu: None

    # Read the driver's function pointers from the original executable in RAM.
    for literal in (0x8C012174, 0x8C012178, 0x8C01217C):
        target = machine.rd32(literal)
        machine.hooks[target & 0x1FFFFFFF] = lambda cpu: None

    target = machine.rd32(0x8C012180)

    def sequence(cpu):
        sequences.append((cpu.r[5], cpu.r[6], cpu.r[7]))

    machine.hooks[target & 0x1FFFFFFF] = sequence
    machine.call(entry)
    return cues, sequences, machine.rd32(0x8C22D804)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ram", type=Path)
    args = parser.parse_args()
    ram = args.ram.read_bytes()
    if len(ram) != 16 * 1024 * 1024:
        parser.error("Expected a 16 MB Flycast main RAM dump")
    for name, address, expected_phase, expected_cues in TRANSITIONS:
        cues, sequences, phase = trace(ram, address)
        if phase != expected_phase or tuple(cue for cue, _ in cues) != expected_cues:
            raise RuntimeError(f"{name}: unexpected phase or cue list: {phase}, {cues}")
        if sequences != [(0, cue, 0) for cue in expected_cues]:
            raise RuntimeError(f"{name}: unexpected AICA sequence requests: {sequences}")
        print(f"{name} 0x{address:08x}: phase {phase}, cues {cues}, bank/sequence {sequences}")


if __name__ == "__main__":
    main()
