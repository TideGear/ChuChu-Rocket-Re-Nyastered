"""Add opt-in pre-render TA capture to local Flycast 3a5267a source.

Usage: patch_flycast_ta_capture.py <source directory>; rebuild the reference core.
FLYCAST_TA_CAPTURE=<prefix> writes raw TA streams as <prefix><render>_<context>.ta.
FLYCAST_TA_FIRST/LAST select inclusive render-call indices (not flyhost frames).
Disabled without the prefix. Does not alter emulated data or rendering options.
Compare screenshots with capture disabled/enabled before using new evidence.
No emulator source or captured game data is bundled in this repository.
"""
import argparse
import hashlib
from pathlib import Path


SHA256 = 'd90e29f988fdfc5e5e28b7ffa8d8d2b9c8f8ce549b9ea451be135b0526ae5a63'
MARKER = '// CCR optional raw TA capture before rendering'
CAPTURE = r'''
// CCR optional raw TA capture before rendering
static void ccrCaptureTA(TA_context* context)
{
    const char* prefix = std::getenv("FLYCAST_TA_CAPTURE");
    if (prefix == nullptr || *prefix == 0)
        return;
    static unsigned render = 0;
    const unsigned index = render++;
    const char* first = std::getenv("FLYCAST_TA_FIRST");
    const char* last = std::getenv("FLYCAST_TA_LAST");
    if ((first && index < std::strtoul(first, nullptr, 10))
            || (last && index > std::strtoul(last, nullptr, 10)))
        return;
    unsigned part = 0;
    for (TA_context* ctx = context; ctx != nullptr; ctx = ctx->nextContext, ++part)
    {
        char filename[2048];
        const int length = std::snprintf(filename, sizeof filename, "%s%05u_%02u.ta", prefix, index, part);
        if (length < 0 || static_cast<size_t>(length) >= sizeof filename)
            return;
        const size_t size = ctx->tad.End() - ctx->tad.thd_root;
        if (std::FILE* out = std::fopen(filename, "wb"))
        {
            const bool wrote = std::fwrite(ctx->tad.thd_root, 1, size, out) == size;
            const bool closed = std::fclose(out) == 0;
            std::fprintf(stderr, "CCR TA render %u context %u address %08x bytes %zu %s\n",
                         index, part, ctx->Address, size, wrote && closed ? "ok" : "WRITE FAILED");
        }
        else
            std::fprintf(stderr, "CCR TA cannot open %s\n", filename);
    }
}
'''


def patch(root):
    path = root / 'core/hw/pvr/ta_ctx.cpp'
    data = path.read_bytes()
    if MARKER.encode() in data:
        print('TA capture already installed')
        return
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise SystemExit('Unexpected ta_ctx.cpp; expected pinned Flycast 3a5267a')
    text = data.decode('utf-8')
    text = '#include <cstdio>\n#include <cstdlib>\n' + text
    anchor = 'bool QueueRender(TA_context* ctx)\n{\n\tverify(ctx != 0);'
    if text.count(anchor) != 1:
        raise SystemExit('QueueRender anchor mismatch')
    text = text.replace(anchor, CAPTURE + '\n' + anchor + '\n\tccrCaptureTA(ctx);')
    path.write_bytes(text.encode('utf-8'))
    print('Installed opt-in raw TA capture')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    patch(parser.parse_args().source)
