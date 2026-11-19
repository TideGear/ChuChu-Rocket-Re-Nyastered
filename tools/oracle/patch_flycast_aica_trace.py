"""Add optional per-sample key-state tracing to a local Flycast 3a5267a source.

Usage: patch_flycast_aica_trace.py <source directory>
This development-only insertion preserves synthesis and is disabled without
FLYCAST_AICA_TRACE=<csv path>. Rebuild the core, then compare its WAV with the
unmodified core before using the timestamps. Optional FLYCAST_AICA_KEY_ON=<hex
channel mask> invokes original KEY_ON once before the first sample, explicitly
changing the test fixture. Leave it unset for ordinary tracing or identity checks.
FLYCAST_AICA_TICKS=<csv> independently records driver-clock changes at their
first observed output sample, with sampled ARM PC for context.
FLYCAST_AICA_WRITES=<csv> is a synthetic fixture: ordered rows contain sample
(decimal), channel (decimal), offset (hex), width 1/2/4 (decimal), value (hex).
It applies original byte/halfword register handlers before that output sample.
Word writes call the original ARM handler, which truncates to a halfword.
Leave it unset for ordinary tracing and identity checks.
FLYCAST_AICA_READS=<csv> plus FLYCAST_AICA_READS_OUT=<csv> enables synthetic
monitor queries: sample(decimal),selector(hex),address(hex),width(decimal).
Results append the hexadecimal value. These reads consume loop latches;
leave both unset during ordinary original-loop observation.
No emulator sources are bundled.
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
bool ccr_keyon_done = false;
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

KEYON = r'''
// Synthetic reference control: invoke the core's own complete KEY_ON routine.
// Disabled unless an explicit hexadecimal channel mask is provided.
void ccr_keyon_controls()
{
    if (ccr_keyon_done) return;
    ccr_keyon_done = true;
    const char* value = std::getenv("FLYCAST_AICA_KEY_ON");
    if (!value) return;
    const unsigned long long mask = std::strtoull(value, nullptr, 16);
    for (unsigned index = 0; index < 64; ++index)
        if (mask & (1ull << index)) Chans[index].KEY_ON();
}
'''

TICKS = r'''
// CCR development driver-clock observation (no timing or synthesis changes).
namespace {
std::FILE* ccr_tick_file = nullptr;
bool ccr_tick_initialized = false;
bool ccr_tick_baseline = false;
unsigned long long ccr_tick_sample = 0;
u32 ccr_last_tick = 0;

void ccr_trace_ticks()
{
    if (!ccr_tick_initialized) {
        ccr_tick_initialized = true;
        if (const char* path = std::getenv("FLYCAST_AICA_TICKS")) {
            ccr_tick_file = std::fopen(path, "w");
            if (ccr_tick_file)
                std::fprintf(ccr_tick_file, "sample,driver_tick,arm_pc_at_sample\n");
        }
    }
    if (!ccr_tick_file) return;
    const u32 tick = *(const u32*)&aica_ram[0x12418];
    if (!ccr_tick_baseline || tick != ccr_last_tick) {
        std::fprintf(ccr_tick_file, "%llu,%u,%08x\n", ccr_tick_sample,
                     tick, arm::arm_Reg[arm::RN_PC].I);
        std::fflush(ccr_tick_file);
        ccr_last_tick = tick;
        ccr_tick_baseline = true;
    }
    ++ccr_tick_sample;
}
}
'''

WRITES = r'''
// Synthetic timed register writes. Disabled without an explicit fixture file.
namespace {
std::FILE* ccr_write_file = nullptr;
bool ccr_write_initialized = false;
bool ccr_write_pending = false;
unsigned long long ccr_write_sample = 0, ccr_write_next = 0;
unsigned ccr_write_channel = 0, ccr_write_offset = 0, ccr_write_size = 0, ccr_write_value = 0;
void ccr_read_write()
{
    int n = std::fscanf(ccr_write_file, "%llu,%u,%x,%u,%x", &ccr_write_next,
        &ccr_write_channel, &ccr_write_offset, &ccr_write_size, &ccr_write_value);
    if (n == EOF) { ccr_write_pending = false; return; }
    if (n != 5 || ccr_write_next < ccr_write_sample || ccr_write_channel >= 64 ||
        ccr_write_offset >= 0x48 || (ccr_write_size != 1 && ccr_write_size != 2 && ccr_write_size != 4) ||
        (ccr_write_size == 2 && (ccr_write_offset & 1)) ||
        (ccr_write_size == 4 && (ccr_write_offset & 3)) ||
        (ccr_write_size < 4 && ccr_write_value >= (1u << (ccr_write_size * 8)))) std::abort();
    ccr_write_pending = true;
}
void ccr_timed_writes()
{
    if (!ccr_write_initialized) {
        ccr_write_initialized = true;
        if (const char* path = std::getenv("FLYCAST_AICA_WRITES")) {
            ccr_write_file = std::fopen(path, "r");
            if (!ccr_write_file) std::abort();
            ccr_read_write();
        }
    }
    while (ccr_write_pending && ccr_write_next == ccr_write_sample) {
        u32 address = ccr_write_channel * 128 + ccr_write_offset;
        if (ccr_write_size == 1) aica::writeRegInternal<u8>(address, (u8)ccr_write_value);
        else if (ccr_write_size == 2) aica::writeRegInternal<u16>(address, (u16)ccr_write_value);
        else aica::arm::writeReg<u32>(address, ccr_write_value);
        ccr_read_write();
    }
    ++ccr_write_sample;
}
void ccr_reset_writes()
{
    if (ccr_write_file) std::fclose(ccr_write_file);
    ccr_write_file = nullptr;
    ccr_write_initialized = ccr_write_pending = false;
    ccr_write_sample = 0;
}
}
'''

READS = r'''
// Synthetic monitor reads. Each read changes the selected/latch state.
namespace {
std::FILE* ccr_read_file = nullptr;
std::FILE* ccr_read_output = nullptr;
bool ccr_read_initialized = false, ccr_read_pending = false;
unsigned long long ccr_read_sample = 0, ccr_read_next = 0;
unsigned ccr_read_select = 0, ccr_read_address = 0, ccr_read_size = 0;
void ccr_next_read()
{
    int n = std::fscanf(ccr_read_file, "%llu,%x,%x,%u", &ccr_read_next,
                       &ccr_read_select, &ccr_read_address, &ccr_read_size);
    if (n == EOF) { ccr_read_pending = false; return; }
    if (n != 4 || ccr_read_next < ccr_read_sample || ccr_read_select > 255 ||
        (ccr_read_size != 1 && ccr_read_size != 2 && ccr_read_size != 4) ||
        (ccr_read_address != 0x2810 && ccr_read_address != 0x2811 &&
         ccr_read_address != 0x2814 && ccr_read_address != 0x2815) ||
        (ccr_read_size != 1 && (ccr_read_address & 1))) std::abort();
    ccr_read_pending = true;
}
void ccr_timed_reads()
{
    if (!ccr_read_initialized) {
        ccr_read_initialized = true;
        if (const char* path = std::getenv("FLYCAST_AICA_READS")) {
            const char* output = std::getenv("FLYCAST_AICA_READS_OUT");
            if (!output) std::abort();
            ccr_read_file = std::fopen(path, "r");
            ccr_read_output = std::fopen(output, "w");
            if (!ccr_read_file || !ccr_read_output) std::abort();
            ccr_next_read();
        }
    }
    while (ccr_read_pending && ccr_read_next == ccr_read_sample) {
        aica::arm::writeReg<u8>(0x280d, (u8)ccr_read_select);
        u32 value;
        if (ccr_read_size == 1) value = aica::arm::readReg<u8>(ccr_read_address);
        else if (ccr_read_size == 2) value = aica::arm::readReg<u16>(ccr_read_address);
        else value = aica::arm::readReg<u32>(ccr_read_address);
        std::fprintf(ccr_read_output, "%llu,%x,%x,%u,%x\n", ccr_read_sample,
            ccr_read_select, ccr_read_address, ccr_read_size, value);
        std::fflush(ccr_read_output);
        ccr_next_read();
    }
    ++ccr_read_sample;
}
void ccr_reset_reads()
{
    if (ccr_read_file) std::fclose(ccr_read_file);
    if (ccr_read_output) std::fclose(ccr_read_output);
    ccr_read_file = ccr_read_output = nullptr;
    ccr_read_initialized = ccr_read_pending = false;
    ccr_read_sample = 0;
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
                        '#include <cstdio>\n#include <cstdlib>\n#include "hw/arm7/arm7.h"\n#include "hw/arm7/arm_mem.h"\n\nnamespace aica::sgc\n{\n' + TRACE + TICKS, 1)
    text = text.replace('void AICA_Sample()\n{', KEYON + WRITES + READS + '\nvoid AICA_Sample()\n{\n\tccr_keyon_controls();\n\tccr_timed_writes();\n\tccr_timed_reads();\n\tccr_trace_ticks();\n\tccr_trace_keys();', 1)
    text = text.replace('void deserialize(Deserializer& deser)\n{',
                        'void deserialize(Deserializer& deser)\n{\n\tccr_reset_reads();\n\tccr_reset_writes();\n\tccr_trace_sample = 0;\n\tccr_trace_baseline = false;\n\tccr_tick_sample = 0;\n\tccr_tick_baseline = false;\n\tccr_keyon_done = false;', 1)
    if text.count('ccr_trace_keys();') != 1 or text.count('ccr_trace_ticks();') != 1 or text.count('ccr_trace_sample = 0;') != 2:
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
