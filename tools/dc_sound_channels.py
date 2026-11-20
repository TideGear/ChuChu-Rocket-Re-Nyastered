"""MANATEE MIDI channel changes, derived from the original ARM driver."""
import struct
from dc_sound_controls import MixTables, modulation_word, VoiceSetup
from dc_sound_pitch import PitchTable
from dc_sound_voices import allocate_voice


class ChannelCommands:
    """Native MIDI channel and voice dispatch; no ARM execution or sample clock.

    RAM contains the original loaded bank/controller/voice fields. Unsupported
    commands raise instead of dropping changes needed by a sound sequence.
    """
    def __init__(self, driver, ram, registers):
        self.pitch = PitchTable(driver)
        self.mix = MixTables(driver)
        self.setup = VoiceSetup(driver)
        self.ram, self.registers = bytearray(ram), bytearray(registers)
        self.writes = []
        if len(self.ram) != 0x200000 or len(self.registers) != 0x8000:
            raise ValueError('Expected 2 MiB sound RAM and AICA register block')
        image = driver[32:]
        self.count_at = struct.unpack_from('<I', image, 0x1884)[0]
        self.melodic_at, a, self.drums_at, b = struct.unpack_from('<4I', image, 0x195c)
        self.fallbacks = a, b
        self.group_at = struct.unpack_from('<I', image, 0x2708)[0]
        self.bank_error_at = struct.unpack_from('<I', image, 0x3544)[0]
        self.voice_map_at = struct.unpack_from('<I', image, 0x188c)[0]
        self.monitor_register = struct.unpack_from('<I', image, 0xd58)[0] - 0x800000
        self.prestop_mask = struct.unpack_from('<I', image, 0x16cc)[0]
        self.ignored_controls = set()
        for control in range(128):
            address = 0x2174 + control * 4
            instruction = struct.unpack_from('<I', image, address)[0]
            if instruction >> 24 != 0xea:
                raise ValueError('Unsupported controller dispatch table')
            displacement = ((instruction & 0xffffff) ^ 0x800000) - 0x800000
            if address + 8 + displacement * 4 == 0x2374:
                self.ignored_controls.add(control)

    def read32(self, at):
        return struct.unpack_from('<I', self.ram, at)[0]

    def write32(self, at, value):
        struct.pack_into('<I', self.ram, at, value & 0xffffffff)

    def write_register(self, at, value, size=4):
        value &= (1 << (size * 8)) - 1
        self.registers[at:at + size] = value.to_bytes(size, 'little')
        self.writes.append((at, size, value))

    def count(self):
        count = self.ram[self.count_at]
        if count > 64:
            raise ValueError('Voice count exceeds AICA capacity')
        return count

    def update_voices(self):
        """ARM 0xb6c..0xc08: age held notes, start delays, stop ended drums.

        The hardware-status observer supplies voice+0x2b separately. This
        worker does not infer sample completion or consume KYONEX itself.
        """
        self.writes.clear()
        for index in range(self.count()):
            at, reg = 0x10000 + index * 64, index * 128
            flags = self.ram[at]
            if not flags:
                continue
            if flags & 0xc0:
                self.ram[at + 0x3f] = (self.ram[at + 0x3f] + 1) & 255
            delay = self.read32(at + 0x38)
            if delay:
                self.write32(at + 0x38, delay - 1)
                if delay == 1:
                    self.write_register(reg, int.from_bytes(self.registers[reg:reg + 4], 'little') | 0xc000)
            if flags & 0x20 and self.ram[at + 0x2b]:
                control = int.from_bytes(self.registers[reg:reg + 4], 'little')
                self.write_register(reg, (control & ~0x4000) | 0x8000)
                self.ram[at] = 0

    def observe_voice(self, index, status):
        """Sampled-voice branch of ARM 0x93c..0x9cc, given AICA monitor data.

        Streaming-channel branches are separate. The hardware chooses the
        status word and clears its loop latch on read; this models RAM effects.
        """
        if not 0 <= index < self.count() or not 0 <= status <= 0xffffffff:
            raise ValueError('Expected a sampled voice index and monitor word')
        at = 0x10000 + index * 64
        if status & 0x8000 and self.ram[at + 0x3c]:
            self.ram[at + 0x2b] = self.ram[at + 0x3c]
        level = 0xff if status & 0x1f00 else status & 0xff
        level ^= 0xff
        if (status >> 13 & 3) != 3:
            level = 0xff
        self.ram[at + 3] = level
        if not self.read32(at):
            self.ram[self.voice_map_at + index] = 0

    def matching(self, group, channel, include_empty=False):
        for index in range(self.count()):
            at = 0x10000 + index * 64
            if (include_empty or self.read32(at)) and tuple(self.ram[at + 4:at + 6]) == (group, channel):
                yield index, at, index * 128

    def program(self, at, value):
        record = self.ram[at:at + 128]
        mode = record[0x3c] & 1
        selected = self.read32((self.drums_at if mode else self.melodic_at) + record[1] * 8)
        melodic, drums = ({}, {record[1]: selected}) if mode else ({record[1]: selected}, {})
        address = selected or self.fallbacks[mode]
        banks = {address: bytes(self.ram[address:address + self.read32(address + 8)])}
        self.ram[at:at + 128] = program_change(record, value, melodic, drums, banks, self.fallbacks)

    def all_notes_off(self, group, channel):
        # ARM 0x33a4 scans all 48 records, clears the held bit, and only
        # triggers KEY_OFF for held notes not protected by sustain.
        for index in range(48):
            voice, reg = 0x10000 + index * 64, index * 128
            flags = self.ram[voice]
            if (not self.read32(voice) or self.ram[voice + 4] != group or
                    self.ram[voice + 5] != channel or not flags & 0x80):
                continue
            self.ram[voice] = flags & 0x7f
            if flags & 0x40:
                continue
            self.ram[voice + 0x3f] = 0
            control = struct.unpack_from('<I', self.registers, reg)[0]
            self.write_register(reg, (control & 0x0000bfff) | 0x8000)

    def note_off(self, group, channel, note):
        # 0xdd8..0xe80: held-key bit gates release. Flags 0x40/0x20
        # suppress hardware stop while still clearing the held-key bit.
        for _, voice, reg in self.matching(group, channel):
            flags = self.ram[voice]
            if not flags & 0x80 or self.ram[voice + 6] != note:
                continue
            flags &= ~0x80
            self.ram[voice] = flags
            if flags & 0x60:
                continue
            self.ram[voice + 0x3f] = 0
            self.write32(voice + 0x38, 0)
            self.ram[voice + 3] = 255
            self.ram[voice] &= ~0x20
            control = struct.unpack_from('<I', self.registers, reg)[0]
            self.write_register(reg, (control & 0x7ff) | 0x8000)

    def arm_word(self, at):
        at &= 0xffffffff
        if at > len(self.ram) - 4:
            raise NotImplementedError('Bank reference needs unmapped ARM-bus behavior')
        value = self.read32(at & ~3)
        shift = (at & 3) * 8
        return ((value >> shift) | value << ((32 - shift) & 31)) & 0xffffffff

    def drum_exclusion(self, group, channel, exclusion):
        # 0x1814..0x1880 intentionally checks even inactive/stale records.
        for _, voice, reg in self.matching(group, channel, include_empty=True):
            if self.ram[voice + 0x3d] == exclusion:
                control = struct.unpack_from('<I', self.registers, reg)[0]
                self.write_register(reg, (control & ~0x4000) | 0x8000)
                self.ram[voice] = 0

    def note_on(self, group, channel, note, velocity, priority):
        at = 0xc000 + group * 0x800 + channel * 128
        if self.ram[at + 0x3f]:
            return
        controller = bytes(self.ram[at:at + 128])
        bank, program, curves = struct.unpack_from('<3I', controller, 0x10)
        parameters_at = self.group_at + group * 64
        parameters = bytes(self.ram[parameters_at:parameters_at + 32])
        for layer_index in range(4):
            relative = self.arm_word(program + layer_index * 4)
            if not relative:
                continue
            layer_at = (bank + relative) & 0xffffffff
            if layer_at + 16 > len(self.ram):
                raise NotImplementedError('Program layer needs unmapped ARM-bus behavior')
            layer = bytearray(self.ram[layer_at:layer_at + 16])
            for offset in (0, 4, 8):
                struct.pack_into('<I', layer, offset, self.arm_word(layer_at + offset))
            count, first = struct.unpack_from('<2I', layer)
            if count & 128:
                continue
            for index in range(count & 127):
                split_at = (bank + first + index * 48) & 0xffffffff
                if split_at + 48 > len(self.ram) or split_at & 3:
                    raise NotImplementedError('Split requires unverified ARM-bus/bank-layout behavior')
                split = bytes(self.ram[split_at:split_at + 48])
                if not split[36] <= note <= split[37] or not split[43] <= velocity <= split[44]:
                    continue
                if split[45] and split[46]:
                    self.drum_exclusion(group, channel, split[46])
                voice_count = self.count()
                if not voice_count:
                    return
                records = [bytes(self.ram[0x10000 + i * 64:0x10040 + i * 64]) for i in range(voice_count)]
                allocated = allocate_voice(records, priority, self.ram[:264])
                if allocated.status:
                    continue
                voice_index = allocated.index(voice_count)
                if voice_index is None:
                    raise NotImplementedError('Allocator raw non-voice return requires ARM-bus handling')
                voice, reg = allocated.voice_address, allocated.register_address - 0x800000
                curve_at = (curves + split[42] * 128) & 0xffffffff
                curve = bytes(self.ram[curve_at:curve_at + 128])
                words = self.setup.words(split, layer, controller, parameters, curve, bank, note, velocity)
                record = self.setup.record(records[voice_index], split, layer, controller, parameters, curve,
                    split_address=split_at, group_address=parameters_at, group=group, channel=channel,
                    note=note, velocity=velocity, priority=priority)
                self.ram[voice:voice + 64] = record
                self.ram[self.voice_map_at + voice_index] = group | 128
                old_control = struct.unpack_from('<I', self.registers, reg)[0]
                self.write_register(reg, (old_control & self.prestop_mask) | 0x8000)
                if split[45]:
                    self.write_register(self.monitor_register, voice_index, 1)
                for word in range(1, 6):
                    self.write_register(reg + word * 4, words[word])
                lfo = modulation_word(struct.unpack_from('<H', split, 14)[0], controller[2])
                self.write_register(reg + 28, lfo)
                self.write_register(reg + 32, words[8])
                for word in range(11, 18):
                    self.write_register(reg + word * 4, words[word])
                self.write_register(reg + 40, words[10])
                self.write_register(reg + 36, words[9])
                if split[45]:
                    poll = (self.ram[0xadc] + 1) & 63
                    self.write_register(self.monitor_register, poll, 1)
                    self.ram[0xadc] = poll
                if struct.unpack_from('<I', self.registers, reg + 24)[0] != words[6]:
                    self.write_register(reg + 24, words[6])
                self.write_register(reg + 28, words[7])
                self.write_register(reg, words[0])
                break

    def apply(self, command):
        self.writes.clear()
        if command == 0:  # 0xd68: the zero command is the FIFO sentinel.
            return
        tag, group, channel = command >> 24 & 7, command >> 20 & 7, command >> 16 & 15
        at = 0xc000 + group * 0x800 + channel * 128
        value = command & 127
        if tag == 0 or tag == 1 and value == 0:
            self.note_off(group, channel, command >> 8 & 127)
            return
        if tag == 1:
            self.note_on(group, channel, command >> 8 & 127, value, command >> 27 & 31)
            return
        if tag == 4:
            self.program(at, command >> 8 & 127)
            return
        if tag == 5:  # 0x1958: pressure command is a no-op in this driver.
            return
        if tag == 6:
            bend = ((command << 7 & 0x3f80) | (command >> 8 & 127)) - 0x2000
            self.write32(at + 4, bend)
            for _, voice, reg in self.matching(group, channel):
                depth = self.ram[voice + (11 if bend & 0xffff0000 else 10)]
                offset = (((bend & 0xffffffff) * depth & 0xffffffff) >> 5) & 0xffff
                self.write32(voice + 12, offset)
                pitch = offset + self.read32(voice + 0x14) + self.read32(self.read32(voice + 0x18) + 0x10) - 0x8000
                split = self.read32(voice + 0x10)
                fine = struct.unpack_from('<b', self.ram, split + 0x27)[0]
                word = self.pitch.word(self.ram[voice + 6], self.ram[split + 0x26] & 127, fine, pitch)
                if struct.unpack_from('<I', self.registers, reg + 24)[0] != word:
                    self.write_register(reg + 24, word)
            return
        if tag != 3:
            raise NotImplementedError('Note/extended command dispatch is not yet connected')
        control = command >> 8 & 127
        if control in self.ignored_controls:
            return
        if control == 123:
            self.all_notes_off(group, channel)
        elif control == 121:
            self.ram[at:at + 128] = reset_controllers(self.ram[at:at + 128])
            count = self.count()
            voices = [bytes(self.ram[0x10000 + i * 64:0x10040 + i * 64]) for i in range(count)]
            words = [struct.unpack_from('<I', self.registers, i * 128)[0] for i in range(count)]
            originals = voices
            voices, words = reset_sustain(voices, words, group, channel)
            self.ram[0x10000:0x10000 + count * 64] = b''.join(voices)
            for index, word in enumerate(words):
                original = originals[index]
                if any(original[:4]) and tuple(original[4:6]) == (group, channel) and not original[0] & 0x80:
                    self.write_register(index * 128, word)
        elif control == 32:
            drum = self.ram[at + 0x3c] & 1
            if drum and value >= 2:
                return
            table = (self.drums_at if drum else self.melodic_at) + value * 8
            bank, size = self.read32(table), self.read32(table + 4)
            if drum:
                if bank and size:
                    self.ram[at + 1] = value
                    self.write32(at + 0x10, bank)
                else:
                    self.write32(at + 0x10, self.fallbacks[1])
            else:
                self.ram[at + 1] = value
                if not bank or not size:
                    self.ram[self.bank_error_at] |= 1
        elif control == 1:
            # 0x2378 returns before storing the controller if voice count=0.
            if not self.count():
                return
            self.ram[at + 2] = value
            for _, voice, reg in self.matching(group, channel, include_empty=True):
                split = self.read32(voice + 0x10)
                lfo = struct.unpack_from('<H', self.ram, split + 14)[0]
                self.write_register(reg + 28, modulation_word(lfo, value) & 0x7fff)
        elif control in (7, 11):
            self.ram[at + (8 if control == 7 else 9)] = value
            self.ram[at + 10] = ((self.ram[at + 8] + 1) * (self.ram[at + 9] + 1) - 1) >> 7
            parameters = self.ram[self.group_at + group * 64:self.group_at + group * 64 + 32]
            for _, voice, reg in self.matching(group, channel):
                split = self.read32(voice + 0x10)
                curve = self.read32(at + 0x18) + self.ram[voice + 0x1c] * 128
                _, _, level, volume, _ = self.mix.words(self.ram[split:split + 48], self.ram[at:at + 128],
                    parameters, self.ram[curve:curve + 128], self.ram[voice + 7])
                self.ram[voice + 8] = volume
                self.write_register(reg + 41, level >> 8, 1)
        elif control == 10:
            self.ram[at + 11] = value
            offset = self.ram[self.group_at + group * 64 + 6] - 128
            for _, voice, reg in self.matching(group, channel):
                split = self.read32(voice + 0x10)
                pan = min(127, max(0, self.mix.split_pan[self.ram[split + 0x12] & 31] + value - 64))
                self.ram[voice + 9] = pan
                self.write_register(reg + 36, self.mix.pan[min(127, max(0, pan + offset))], 1)
        else:
            raise NotImplementedError(f'Controller {control} is not yet connected')


def program_change(controller, program, melodic, drums, banks, fallback_addresses):
    """ARM 0x18ac..0x1950: select a bank/program and velocity-curve base.

    melodic/drums map bank numbers to loaded RAM addresses; banks maps those
    addresses to original bank payloads. Missing selections use the driver's
    built-in melodic/drum fallback banks (literals 0x1960/0x1968), not the
    previous bank. An invalid program retains all previous channel fields.
    """
    if len(controller) != 128 or not 0 <= program <= 127:
        raise ValueError('Expected a controller record and seven-bit program')
    mode = controller[0x3c] & 1
    registry = drums if mode else melodic
    selected = registry.get(controller[1], 0) or fallback_addresses[mode]
    if selected not in banks:
        raise ValueError('Program selection requires the loaded selected/fallback bank')
    payload = banks[selected]
    if len(payload) < 28:
        raise ValueError('Truncated program bank')
    table, count, velocities = struct.unpack_from('<3I', payload, 16)
    if program >= count:
        return bytes(controller)
    if table + program * 4 + 4 > len(payload):
        raise ValueError('Program table exceeds bank payload')
    entry = struct.unpack_from('<I', payload, table + program * 4)[0]
    result = bytearray(controller)
    result[0] = program
    struct.pack_into('<3I', result, 0x10, selected, (selected + entry) & 0xffffffff,
                     (selected + velocities) & 0xffffffff)
    return bytes(result)


def reset_controllers(controller):
    """Control 121, ARM 0x3280..0x331c; preserve all unassigned bytes.

    In particular only the low byte of pitch offset +0x1c is cleared.
    Program/bank selection and pointer fields are not reset.
    """
    if len(controller) != 128:
        raise ValueError('Expected one 128-byte MIDI controller record')
    result = bytearray(controller)
    for value, offsets in (
        (100, (8, 10)), (127, (9, 0x46)), (64, (11, 0x27, 0x44, 0x45)),
        (32, (0x32, 0x33, 0x34, 0x35, 0x29, 0x2b, 0x2d, 0x2f, 0x31,
              0x37, 0x38, 0x3a, 0x3b, 0x39)),
        (0, (3, 2, 0x28, 0x2a, 0x2c, 0x2e, 0x30, 0x3d, 0x26, 0x36, 0x1c))):
        for offset in offsets:
            result[offset] = value
    result[4:8] = bytes(4)
    result[0x40:0x44] = bytes(4)
    return bytes(result)


def reset_sustain(voices, controls, group, channel):
    """Control 121 continuation, ARM 0x3320..0x339c.

    Voice records and AICA control words retain their original order. Clear
    sustain on matching nonempty records. Release only notes no longer held;
    hardware consumes the returned KYONEX write, not this helper.
    """
    if len(voices) != len(controls) or len(voices) > 64 or any(len(v) != 64 for v in voices):
        raise ValueError('Expected equally sized voice records and control words')
    if not 0 <= group < 8 or not 0 <= channel < 16:
        raise ValueError('Invalid MIDI group/channel')
    records, words = list(voices), list(controls)
    for index, original in enumerate(voices):
        if not any(original[:4]) or tuple(original[4:6]) != (group, channel):
            continue
        voice = bytearray(original)
        voice[0] &= ~0x40
        if not voice[0] & 0x80:
            voice[0x3f] = 0
            words[index] = (words[index] & 0xbfff) | 0x8000
        records[index] = bytes(voice)
    return records, words
