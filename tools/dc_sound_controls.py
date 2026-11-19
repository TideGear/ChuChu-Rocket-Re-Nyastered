"""Controller calculations from the tested MANATEE ARM driver, not synthesis."""
import struct
from dc_sound_pitch import PitchTable


class MixTables:
    """MANATEE 0x11f0..0x1254 and 0x1468..0x1588 routing/level setup."""
    def __init__(self, driver):
        PitchTable(driver)  # Reject unknown driver revisions/tables.
        image = driver[32:]
        pointers = struct.unpack_from('<4I', image, 0x1894)
        self.send, self.attenuation, self.split_pan, self.pan = [
            image[p:p + size] for p, size in zip(pointers, (64, 256, 32, 128))]

    def words(self, split, controller, group, curve, velocity):
        """Return words 8/9, word10 TL bits, retained volume/pan bytes.

        Word10's separate filter fields must be ORed in by the caller.
        curve is the selected split's 128-entry velocity curve; group is
        the original global/group parameter record addressed at 0x16bc.
        """
        if len(split) < 0x2b or len(controller) < 0x47 or len(group) < 12 or len(curve) != 128 or not 0 <= velocity <= 127:
            raise ValueError('Incomplete original mix fields or invalid velocity')
        if controller[10] > 127 or controller[11] > 127:
            raise ValueError('MIDI volume and pan must be seven-bit controller values')

        def send(raw, global_byte):
            level = min(63, max(0, raw + (global_byte >> 1) - 64))
            return self.send[level]

        raw = controller[0x36] or split[0x10]
        bus = split[0x10] if controller[0x46] & 0xf0 else controller[0x46]
        dsp = send((raw & 0xf0) >> 2, group[9]) << 4 | (bus & 15)
        volume = (((curve[velocity] + 1) * (controller[10] + 1) * (256 - split[0x15]) - 1) >> 14) & 255
        level = min(255, max(0, volume + group[4] * 2 - 256))
        total_level = self.attenuation[level] << 8
        pan = min(127, max(0, self.split_pan[split[0x12] & 31] + controller[11] - 64))
        final_pan = min(127, max(0, pan + group[6] - 128))
        packed = struct.unpack_from('<H', split, 0x12)[0]
        direct = self.pan[final_pan] | send((packed >> 6) & 63, group[11]) << 8
        return dsp, direct, total_level, volume, pan


class VoiceSetup:
    """Compose fresh note-on registers from original bank/controller fields.

    Allocation, delayed triggering, reused-channel clocks and later controller
    changes remain the caller's responsibility. No captured AICA runtime is used.
    """
    def __init__(self, driver):
        self.pitch = PitchTable(driver)
        self.mix = MixTables(driver)

    def words(self, split, layer, controller, group, curve, bank_address, note, velocity):
        if len(split) < 48 or len(layer) < 16 or len(controller) < 128 or len(group) < 20 or not 0 <= note <= 127 or not 1 <= velocity <= 127:
            raise ValueError('Incomplete note-on source fields')
        words = list(sample_words(split, bank_address))
        words += list(envelope_words(struct.unpack_from('<I', split, 8)[0],
            *(controller[at] for at in (0x37, 0x38, 0x39, 0x3b))))
        bend = struct.unpack_from('<I', controller, 4)[0]
        sensitivity = controller[3] & 127 if controller[3] & 128 else layer[13 if bend & 0xffff0000 else 12]
        adjusted = ((bend * sensitivity) & 0xffffffff) >> 5 & 0xffff
        adjusted += struct.unpack_from('<I', controller, 0x1c)[0]
        adjusted += struct.unpack_from('<I', group, 0x10)[0] - 0x8000
        words.append(self.pitch.word(note, split[0x26] & 127,
            struct.unpack_from('<b', split, 0x27)[0], adjusted))
        words.append(modulation_word(struct.unpack_from('<H', split, 14)[0], controller[2]) & 0x7fff)
        dsp, direct, level, _, _ = self.mix.words(split, controller, group, curve, velocity)
        words += [dsp, direct]
        filters = filter_words(split, controller)
        words += [filters[0] | level, *filters[1:]]
        if not struct.unpack_from('<I', layer, 8)[0]:
            words[0] |= 0xc000
        return tuple(words)

    def record(self, previous, split, layer, controller, group_parameters, curve,
               *, split_address, group_address, group, channel, note, velocity, priority):
        """ARM 0xfac..0x1658 voice-record writes; retain untouched bytes.

        Allocation, drum exclusion and physical-channel bookkeeping happen
        outside this helper. The accompanying registers come from words().
        """
        if len(previous) != 64 or len(split) < 48 or len(layer) < 16 or len(controller) < 128:
            raise ValueError('Incomplete voice-record source fields')
        if not 0 <= group < 8 or not 0 <= channel < 16 or not 0 <= priority <= 31 or not 0 <= note <= 127 or not 1 <= velocity <= 127:
            raise ValueError('Invalid note-on command fields')
        result = bytearray(previous)
        result[0x3e], result[5], result[4] = priority, channel, group
        struct.pack_into('<I', result, 0x38, struct.unpack_from('<I', layer, 8)[0])
        struct.pack_into('<I', result, 0x10, split_address)
        if controller[3] & 128:
            result[10:12] = bytes([controller[3] & 127] * 2)
        else:
            result[10:12] = layer[12:14]
        result[0x14:0x18] = controller[0x1c:0x20]
        result[6], result[7], result[0x1c] = note, velocity, split[0x2a]
        _, _, _, volume, pan = self.mix.words(split, controller, group_parameters, curve, velocity)
        result[8], result[9] = volume, pan
        struct.pack_into('<I', result, 0x18, group_address)
        bend = struct.unpack_from('<I', controller, 4)[0]
        depth = result[11 if bend & 0xffff0000 else 10]
        struct.pack_into('<I', result, 12, (((bend * depth) & 0xffffffff) >> 5) & 0xffff)
        flags = 0x80
        if split[0x2d]:
            result[0x3c:0x3e] = split[0x2d:0x2f]
            if not split[1] & 2:
                flags |= 0x20
        if controller[0x26] & 0x40:
            flags |= 0x40
        result[0], result[0x2b], result[0x3f], result[3] = flags, 0, 1, 0
        return bytes(result)


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
