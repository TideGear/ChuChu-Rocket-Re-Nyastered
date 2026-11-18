"""Add optional per-sample key-state tracing to a local Flycast 3a5267a source.

Usage: patch_flycast_aica_trace.py <source directory>
This development-only insertion preserves synthesis and is disabled without
FLYCAST_AICA_TRACE=<csv path>. Rebuild the core, then compare its WAV with the
unmodified core before using the timestamps. No emulator sources are bundled.
"""
import argparse
import hashlib
import shutil
from pathlib import Path


ORIGINAL_SHA256 = '5b78b05dbd29d8c41d1e610bd4d6035625627cb48722275da84f2c8322ebc5e2'
MARKER = '// CCR development key-state trace'
TRACE = r'''
// CCR development key-state trace
namespace {
std::FILE* ccr_trace_file = nullptr;
bool ccr_trace_initialized = false;
bool ccr_trace_baseline = false;
unsigned long long ccr_trace_sample = 0;
u32 ccr_trace_control[64] {};

void ccr_trace_keys()
{
    if (!ccr_trace_initialized) {
        ccr_trace_initialized = true;
        if (const char* path = std::getenv("FLYCAST_AICA_TRACE")) {
            ccr_trace_file = std::fopen(path, "w");
            if (ccr_trace_file)
                std::fprintf(ccr_trace_file, "sample,channel,control,driver_tick,arm_pc_at_sample\n");
        }
    }
    if (!ccr_trace_file) return;
    for (unsigned channel = 0; channel < 64; ++channel) {
        const u32 control = *(const u32*)&aica_reg[channel * 128];
        if (!ccr_trace_baseline || ((control ^ ccr_trace_control[channel]) & 0x4000)) {
            const u32 tick = *(const u32*)&aica_ram[0x12418];
            std::fprintf(ccr_trace_file, "%llu,%u,%08x,%u,%08x\n", ccr_trace_sample,
                         channel, control, tick, arm::arm_Reg[arm::RN_PC].I);
            std::fflush(ccr_trace_file);
        }
        ccr_trace_control[channel] = control;
    }
    ccr_trace_baseline = true;
    ++ccr_trace_sample;
}
}
'''


def patch(root, msvc=False, glext=None):
    path = root / 'core/hw/aica/sgc_if.cpp'
    raw = path.read_bytes()
    if MARKER.encode() in raw:
        raise ValueError('Trace insertion is already present; use a clean pinned source to reapply')
    if hashlib.sha256(raw).hexdigest() != ORIGINAL_SHA256:
        raise ValueError('Unexpected Flycast synthesis source; expected pristine 3a5267a')
    extension_header = root / 'core/deps/libretro-common/include/GL/glext.h'
    if msvc and not extension_header.exists() and (glext is None or not glext.is_file()):
        raise ValueError('MSVC needs --glext pointing to a Khronos GL extension header (SDL_opengl_glext.h also works)')
    text = raw.decode('utf-8')
    text = text.replace('namespace aica::sgc\n{',
                        '#include <cstdio>\n#include <cstdlib>\n#include "hw/arm7/arm7.h"\n\nnamespace aica::sgc\n{\n' + TRACE, 1)
    text = text.replace('void AICA_Sample()\n{', 'void AICA_Sample()\n{\n\tccr_trace_keys();', 1)
    text = text.replace('void deserialize(Deserializer& deser)\n{',
                        'void deserialize(Deserializer& deser)\n{\n\tccr_trace_sample = 0;\n\tccr_trace_baseline = false;', 1)
    if text.count('ccr_trace_keys();') != 1 or text.count('ccr_trace_sample = 0;') != 2:
        raise ValueError('Trace anchors did not resolve uniquely')
    path.write_bytes(text.encode('utf-8'))
    if msvc:
        # Build-only compatibility for this upstream libretro target. None of
        # these changes touch emulated CPU, sound, timing or rendering behavior.
        folder = root / 'shell/libretro'
        prefix = '// CCR local MSVC reference compatibility\n'
        common = '#if defined(_MSC_VER) && !defined(PATH_MAX)\n#define PATH_MAX 4096\n#endif\n'
        entries = (
            ('libretro.cpp', '#ifdef _MSC_VER\n#include <intrin.h>\n#define __builtin_trap() __debugbreak()\n#endif\n'),
            ('oslib.cpp', '#ifdef _MSC_VER\n#include <cstring>\nextern "C" char* retro_strdup__(const char* text) { return _strdup(text); }\n#endif\n'),
        )
        for name, extra in entries:
            target = folder / name
            target.write_bytes((prefix + common + extra).encode() + target.read_bytes())
        if not extension_header.exists():
            extension_header.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(glext, extension_header)
    print('Inserted optional sample/key-state tracing into pinned source')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--msvc', action='store_true', help='apply build-only MSVC libretro compatibility')
    parser.add_argument('--glext', type=Path, help='Khronos/SDL OpenGL extension header for MSVC')
    args = parser.parse_args()
    patch(args.source, args.msvc, args.glext)
