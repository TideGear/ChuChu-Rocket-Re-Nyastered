"""Controller calculations from the tested MANATEE ARM driver, not synthesis."""
import struct


def sample_words(split, bank_address):
    """ARM 0x1058..0x10ac: sample address, format/loop flags and endpoints.

    The control word excludes key-on/execute bits set later by the driver.
    """
    if len(split) < 8 or not isinstance(bank_address, int) or not 0 <= bank_address <= 0xffffffff:
        raise ValueError('Expected split bytes and unsigned bank address')
    packed, loops = struct.unpack_from('<2I', split)
    relative = ((packed >> 16) | (packed << 16)) & 0x7fffff
    address = (bank_address + relative) & 0xffffffff
    return ((packed & 0x780) | (address >> 16 & 127), address & 0xffff,
            loops & 0xffff, loops >> 16)


def modulation_word(lfo, modulation):
    """ARM 0x1188..0x11ec: scale split LFO depths by controller byte +2.

    Frequency, waveform and reset bits pass through. The note-on path clears the
    reset bit separately at 0x1674..0x167c, after preparing the channel.
    """
    if not 0 <= lfo <= 65535 or not 0 <= modulation <= 127:
        raise ValueError('Invalid LFO word or modulation controller')
    pitch = (((modulation + 1) * (((lfo >> 5) & 7) + 1) - 1) >> 7) & 7
    amplitude = (((modulation + 1) * ((lfo & 7) + 1) - 1) >> 7) & 7
    return (lfo & 0xff18) | (pitch << 5) | amplitude


def envelope_words(split_amplitude, attack, decay, decay_level, release):
    """ARM 0x10b0..0x1184: apply channel offsets to split amplitude fields.

    Offsets are stored around neutral 32. Both decay rates share one offset;
    release has a minimum raw rate of one. KRS/LPSLNK pass through unchanged.
    """
    if not isinstance(split_amplitude, int) or not 0 <= split_amplitude <= 0xffffffff:
        raise ValueError('Invalid split amplitude word')
    if any(not isinstance(value, int) or not 0 <= value <= 255
           for value in (attack, decay, decay_level, release)):
        raise ValueError('Envelope controller offsets must be bytes')

    def adjusted(value, control):
        return min(31, max(0, value + control - 32))

    lower, upper = split_amplitude & 0xffff, split_amplitude >> 16
    word4 = (adjusted(lower & 31, attack) | adjusted((lower >> 6) & 31, decay) << 6 |
             adjusted((lower >> 11) & 31, decay) << 11)
    word5 = (max(1, adjusted(upper & 31, release)) |
             adjusted((upper >> 5) & 31, decay_level) << 5 | upper & 0x7c00)
    return word4, word5


def filter_words(split, controller):
    """ARM 0x1258..0x1464: Q/bypass, five levels and four filter rates.

    Returns word 10's filter bits followed by words 11..17. Word 10's
    high-byte total level is prepared separately and must be retained.
    Keep the original wrapped arithmetic and
    bit-mask saturation: it is not a generic floating-point filter clamp.
    Controller offsets are the driver's 0x80-byte MIDI channel record.
    """
    if len(split) < 36 or len(controller) < 0x44:
        raise ValueError('Expected complete filter split and controller fields')
    raw = struct.unpack_from('<I', split, 0x14)[0]
    resonance = min(31, max(0, (raw & 31) + controller[0x27] - 64))
    bypass = controller[0x3d]
    bypass = (raw & 32) if not bypass else (0 if bypass & 64 else 32)
    coarse = struct.unpack_from('<I', controller, 0x40)[0]
    levels = []
    for index in range(5):
        level = struct.unpack_from('<H', split, 0x16 + index * 2)[0]
        offset = struct.unpack_from('<H', controller, 0x28 + index * 2)[0]
        value = (level + offset - 0x2000 + coarse) & 0xffffffff
        if value & 0x80000000 or value < 8:
            value = 8
        if (value + 8) & 0xe000:
            value = 0x1ff8
        levels.append(value)
    rates = struct.unpack_from('<I', split, 0x20)[0]
    adjusted = [min(31, max(0, ((rates >> shift) & 31) + controller[at] - 32))
                for shift, at in ((8, 0x32), (0, 0x33), (24, 0x34), (16, 0x35))]
    return (resonance | bypass, *levels, adjusted[0] << 8 | adjusted[1],
            adjusted[2] << 8 | adjusted[3])
