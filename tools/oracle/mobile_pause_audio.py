"""Check whether the original mobile pause and release helpers affect music."""
import argparse
from pathlib import Path

from unicorn import UC_HOOK_CODE

from ccr_oracle import BASE, Oracle
from ios_oracle import IOSOracle
from extract_android import elf_symbols


def verify(path):
    android = path.suffix == '.so'
    oracle = Oracle(str(path)) if android else IOSOracle(str(path))
    if android:
        symbols = {name: value for name, (value, _) in elf_symbols(oracle.d)[0].items()}
    else:
        symbols = {name: value for name, value, _, _ in oracle.m.syms}
    instructions = []

    def trace(uc, address, size, data):
        instructions.append((address, size))

    oracle.uc.hook_add(UC_HOOK_CODE, trace)
    prefix = '' if android else '_'
    for name in ('_Z9BGM_Pausev', '_Z11BGM_Releasev'):
        entry = symbols[prefix + name] & ~1
        address = (BASE if android else 0) + entry
        # Thumb MOVS r0,#1 followed by BX lr. Check that the actual call
        # executes only those two instructions.
        assert oracle.read(address, 4) == bytes.fromhex('01207047'), (path, name)
        instructions.clear()
        assert oracle.call(entry, 0) == 1, (path, name)
        assert instructions == [(address, 2), (address + 2, 2)], (path, name, instructions)
    print(f'{path.parents[2].name if android else path.name}: pause and release return without touching music')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', nargs='+', type=Path, help='Android armeabi .so or thinned iOS Mach-O')
    for binary in parser.parse_args().binary:
        verify(binary)
