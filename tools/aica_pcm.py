"""AICA sample stepping, amplitude/filter envelopes and periodic pitch LFO.

Consumes captured channel state. Direct output includes pan/attenuation, sample
end/loops, amplitude/filter envelope evolution and timestamped key-offs.
Register-based note starts preserve an explicit channel LFO clock. This is not
a finished sound-effect renderer. Hardware field/step reference: Flycast core
3a5267a, core/hw/aica/sgc_if.cpp; compare with original core snapshots.
"""
import math
import struct


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


DECAY_MS = (-1, -1, 118200, 101300, 88600, 70900, 59100, 50700, 44300, 35500,
            29600, 25300, 22200, 17700, 14800, 12700, 11100, 8900, 7400, 6300,
            5500, 4400, 3700, 3200, 2800, 2200, 1800, 1600, 1400, 1100,
            920, 790, 690, 550, 460, 390, 340, 270, 230, 200, 170, 140, 110,
            98, 85, 68, 57, 49, 43, 34, 28, 25, 22, 18, 14, 12, 11, 8.5, 7.1,
            6.1, 5.4, 4.3, 3.6, 3.1)

ATTACK_MS = (-1, -1, 8100, 6900, 6000, 4800, 4000, 3400, 3000, 2400, 2000,
             1700, 1500, 1200, 1000, 860, 760, 600, 500, 430, 380, 300, 250,
             220, 190, 150, 130, 110, 95, 76, 63, 55, 47, 38, 31, 27, 24,
             19, 15, 13, 12, 9.4, 7.9, 6.8, 6, 4.7, 3.8, 3.4, 3, 2.4, 2,
             1.8, 1.6, 1.3, 1.1, .93, .85, .65, .53, .44, .40, .35, 0, 0)


class SampleStream:
    @classmethod
    def from_registers(cls, channel, sound_ram, *, lfo_counter, lfo_phase):
        """Start a sampled voice, preserving the caller's channel LFO clock.

        KEY_ON does not reset that clock; register-write timing controls it.
        The remaining runtime fields are initialized without a saved voice.
        """
        if not isinstance(lfo_phase, int) or not 0 <= lfo_phase <= 255:
            raise ValueError('Invalid channel LFO phase')
        initial = dict(channel)
        initial['runtime'] = dict(sample_address=channel['sample_address'], position=0,
            fraction=0, s0=0, s1=0, lfo_counter=lfo_counter, lfo_phase=lfo_phase,
            enabled=True, looped=0, amplitude_value=0x3ff << 16, amplitude_state=3,
            filter_value=channel['register_words'][11] << 16, filter_state=3,
            filter_previous1=0, filter_previous2=0, filter_fraction=0,
            adpcm_quant=127, adpcm_loop_quant=0, adpcm_loop_previous=0, adpcm_in_loop=False)
        model = cls(initial, sound_ram)
        model.key_on()
        return model

    def __init__(self, channel, sound_ram):
        if channel['pcm_mode'] not in (0, 1, 2, 3) or not channel['runtime']['enabled']:
            raise ValueError('An enabled sampled channel is required')
        if channel['register_words'][0] & 0x400:
            raise ValueError('Noise voices are not yet supported')
        self.channel = channel
        self.ram = sound_ram
        self.state = dict(channel['runtime'])
        self.output_samples = 0
        self.lfo = channel['lfo_raw']
        if ((self.lfo >> 8) & 3) == 3:
            raise ValueError('Random pitch LFO is not yet validated')
        octave = channel['octave_raw']
        rate = 1024 + channel['fns']
        self.rate = rate >> (16 - octave) if octave & 8 else rate << octave
        frequency = (self.lfo >> 10) & 31
        division = 128 >> (frequency >> 2)
        self.period = (division - 1) * 4 + division * (((~frequency) & 3) + 1)
        if not 1 <= self.state['lfo_counter'] <= self.period or not 0 <= self.state['fraction'] < 1024:
            raise ValueError('Invalid captured stream phase')
        cents = (0, 3.61, 7.22, 14.44, 28.88, 57.75, 115.5, 231)[(self.lfo >> 5) & 7]
        self.pitch_scale = []
        for i in range(-128, 128):
            exponent = f32(f32(f32(cents) * i) / 128)
            exponent = f32(exponent / 1200)
            self.pitch_scale.append(int(f32(1024 * f32(math.pow(2, exponent)))))
        words = channel['register_words']
        if self.state['amplitude_state'] not in range(4):
            raise ValueError('Invalid amplitude envelope state')
        rate_scale = 0
        key_scale = (words[5] >> 10) & 15
        if key_scale < 15:
            signed_octave = (octave ^ 8) - 8
            rate_scale += (channel['fns'] >> 9) & 1
            rate_scale += max(0, (key_scale + signed_octave) * 2)

        def decay_delta(rate):
            milliseconds = f32(DECAY_MS[min(63, rate * 2 + rate_scale)])
            return int(math.floor(((1024 << 16) - 1) / (44.1 * milliseconds) + 0.5)) if milliseconds > 0 else 0

        self.release_delta = decay_delta(words[5] & 31)
        self.decay1_delta = decay_delta((words[4] >> 6) & 31)
        self.decay2_delta = decay_delta((words[4] >> 11) & 31)
        self.decay2_value = ((words[5] >> 5) & 31) << 5
        milliseconds = f32(ATTACK_MS[min(63, (words[4] & 31) * 2 + rate_scale)])
        self.attack_delta = (0 if milliseconds < 0 else 65536 if milliseconds == 0 else
                             int(math.floor(65536 / (1 - 1 / math.pow(640, 1 / (44.1 * milliseconds))) + .5)))
        self.loop_link = bool(words[5] & 0x4000)
        self.filter_active = not (words[10] & 32) and (any(v < 0x1ff8 for v in words[11:16]) or (words[10] & 31) != 4)
        if self.filter_active:
            if self.state['filter_state'] not in range(4):
                raise ValueError('Invalid filter envelope state')
            self.filter_deltas = (decay_delta((words[16] >> 8) & 31), decay_delta(words[16] & 31),
                                  decay_delta((words[17] >> 8) & 31), decay_delta(words[17] & 31))
            self.filter_targets = [value << 16 for value in words[12:16]]
            self.resonance = (2048, 1536, 1024, 512, 0, -256, -512, -768, -1024, -1280,
                         -1536, -1792, -2048, -2176, -2304, -2432, -2560, -2688,
                         -2816, -2944, -3072, -3136, -3200, -3264, -3328, -3392,
                         -3456, -3520, -3584, -3648, -3712, -3776)[words[10] & 31]
            self.filter_cached_value = None

    def step_filter_envelope(self):
        if not self.filter_active:
            return
        state = self.state
        phase = state['filter_state']
        value, target = state['filter_value'], self.filter_targets[phase]
        delta = self.filter_deltas[phase]
        if value < target:
            state['filter_value'] = min(target, value + delta)
        elif value > target:
            state['filter_value'] = max(target, value - delta)
        elif phase < 2:
            state['filter_state'] += 1

    def filter(self, sample):
        if not self.filter_active:
            return sample
        state = self.state
        value = state['filter_value'] >> 16
        if value != self.filter_cached_value:
            exponent, mantissa = value >> 9, (value & 511) | 512
            a0 = ((((mantissa << 30) >> ((15 - exponent) * 2)) * ((mantissa - 1) // 8)) >> 17)
            feedback = (mantissa << exponent) << 5
            product = self.resonance * feedback
            feedback += (abs(product) // 4096) * (-1 if product < 0 else 1)
            self.filter_coefficients = a0, (1 << 31) - feedback - a0, (1 << 30) - feedback
            self.filter_exponent = exponent
            self.filter_cached_value = value
        a0, b1, b2 = self.filter_coefficients
        fraction = state['filter_fraction'] if self.filter_exponent else 0
        accumulator = -a0 * sample + b1 * state['filter_previous1'] - b2 * state['filter_previous2'] - fraction
        value = accumulator >> 30
        state['filter_fraction'] = (value << 30) - accumulator
        state['filter_previous2'] = state['filter_previous1']
        state['filter_previous1'] = min(524287, max(-524288, value))
        return state['filter_previous1']

    def end(self):
        value = self.channel['loop_end']
        return (value + 3) & ~3 if self.channel['pcm_mode'] == 3 else value

    @staticmethod
    def adpcm(nibble, previous, quant):
        magnitude = nibble & 7
        delta = min(32767, (quant * (2 * magnitude + 1)) >> 3)
        sample = previous + (-delta if nibble & 8 else delta)
        quant = min(24576, max(127, (quant * (230, 230, 230, 230, 307, 409, 512, 614)[magnitude]) >> 8))
        return min(32767, max(-32768, sample)), quant

    def decode(self, last):
        state = self.state
        mode = self.channel['pcm_mode']
        if mode < 2 and not last:
            return
        position, address = state['position'], state['sample_address']
        start, end = self.channel['loop_start'], self.end()
        following = position + 1
        if following >= end and end > start:
            following = start
        if mode == 0:
            state['s0'] = struct.unpack_from('<h', self.ram, (address + 2 * position) & 0x1ffffe)[0]
            state['s1'] = struct.unpack_from('<h', self.ram, (address + 2 * following) & 0x1ffffe)[0]
        elif mode == 1:
            state['s0'] = struct.unpack_from('<b', self.ram, (address + position) & 0x1fffff)[0] << 8
            state['s1'] = struct.unpack_from('<b', self.ram, (address + following) & 0x1fffff)[0] << 8
        else:
            previous, quant = state['s0'], state['adpcm_quant']
            if position == start:
                if not state['adpcm_in_loop']:
                    state['adpcm_loop_quant'], state['adpcm_loop_previous'] = quant, previous
                    state['adpcm_in_loop'] = True
                elif mode == 2:
                    quant, previous = state['adpcm_loop_quant'], state['adpcm_loop_previous']
            nibble = (self.ram[(address + (position >> 1)) & 0x1fffff] >> (4 * (position & 1))) & 15
            sample, quant = self.adpcm(nibble, previous, quant)
            state['s0'], state['adpcm_quant'] = sample, quant
            state['s1'] = 0
            if last:
                if following == start and state['adpcm_in_loop'] and mode == 2:
                    quant, sample = state['adpcm_loop_quant'], state['adpcm_loop_previous']
                nibble = (self.ram[(address + (following >> 1)) & 0x1fffff] >> (4 * (following & 1))) & 15
                state['s1'], _ = self.adpcm(nibble, sample, quant)

    def key_off(self):
        if self.state['amplitude_state'] != 3:
            self.state['amplitude_state'] = 3
            self.state['filter_state'] = 3

    def key_on(self):
        """AICA KEY_ON ignores voices whose amplitude state is not release."""
        state = self.state
        if state['amplitude_state'] != 3:
            return
        state.update(enabled=True, amplitude_state=0, amplitude_value=640 << 16,
                     filter_state=0, filter_value=self.channel['register_words'][11] << 16,
                     filter_previous1=0, filter_previous2=0, filter_fraction=0,
                     position=0, fraction=0, looped=0, s0=0, adpcm_quant=127,
                     adpcm_loop_quant=0, adpcm_loop_previous=0, adpcm_in_loop=False)
        self.decode(last=True)

    def render(self, count, filtered=False, key_off_samples=()):
        if count < 0:
            raise ValueError('Negative sample count')
        out = []
        self.attenuation = []
        key_off_samples = set(key_off_samples)
        if any(not isinstance(v, int) or v < 0 for v in key_off_samples):
            raise ValueError('Key-off sample indices must be nonnegative integers')
        state = self.state
        for _ in range(count):
            if self.output_samples in key_off_samples:
                self.key_off()
            self.output_samples += 1
            if not state['enabled']:
                out.append(0)
                self.attenuation.append(255)
                continue
            fraction = state['fraction']
            sample = ((state['s0'] * (1024 - fraction)) >> 10) + ((state['s1'] * fraction) >> 10)
            signal = self.filter(sample << 4)
            out.append(signal if filtered else sample)
            self.attenuation.append(min(255, state['amplitude_value'] >> 18))
            if state['amplitude_state'] == 0 and self.attack_delta:
                state['amplitude_value'] -= ((state['amplitude_value'] << 16) // self.attack_delta) + 1
                if state['amplitude_value'] >> 16 <= 0:
                    state['amplitude_value'] = 0
                    if not self.loop_link:
                        state['amplitude_state'] = 1
            elif state['amplitude_state'] == 1:
                state['amplitude_value'] += self.decay1_delta
                if state['amplitude_value'] >> 16 >= self.decay2_value:
                    state['amplitude_state'] = 2
            elif state['amplitude_state'] == 2:
                state['amplitude_value'] += self.decay2_delta
                if state['amplitude_value'] >> 16 >= 0x3ff:
                    state['amplitude_value'] = 0x3ff << 16
                    state['amplitude_state'] = 3
            elif state['amplitude_state'] == 3:
                state['amplitude_value'] += self.release_delta
                if state['amplitude_value'] >> 16 >= 0x3ff:
                    state['amplitude_value'] = 0x3ff << 16
                    state['enabled'] = False
                    state['position'] = 0
                    continue
            self.step_filter_envelope()
            phase = state['lfo_phase']
            wave = (self.lfo >> 8) & 3
            if wave == 0:
                level = phase
            elif wave == 1:
                level = 255 if phase & 128 else 0
            else:
                level = 2 * ((phase & 127) if phase < 128 else (127 - (phase & 127)))
            accumulated = fraction + ((self.rate * self.pitch_scale[level]) >> 10)
            advance, state['fraction'] = divmod(accumulated, 1024)
            if advance:
                start, end = self.channel['loop_start'], self.end()
                for step in range(advance):
                    position = state['position'] + 1
                    if self.loop_link and state['amplitude_state'] == 0 and position >= start:
                        state['amplitude_state'] = 1
                    if position >= end:
                        if start > end:
                            stop = position >= start
                        else:
                            stop = not self.channel['loop']
                            state['looped'] = 1
                            position = start
                        if stop:
                            state['looped'] = 1
                            state['enabled'] = False
                            state['amplitude_state'] = 3
                            state['amplitude_value'] = 0x3ff << 16
                            position = 0
                    state['position'] = position
                    self.decode(last=step == advance - 1)
            state['lfo_counter'] -= 1
            if state['lfo_counter'] == 0:
                state['lfo_counter'] = self.period
                state['lfo_phase'] = (phase + 1) & 255
        return out


def direct_stereo(channel, sound_ram, count, key_off_samples=(), start=False):
    """Render captured state or start from registers, without DSP returns."""
    state = channel['runtime']
    words = channel['register_words']
    if words[10] & 64:
        raise ValueError('Attenuation bypass is not yet validated')
    if channel['lfo_raw'] & 7:
        raise ValueError('Amplitude LFO is not yet validated')
    model = (SampleStream.from_registers(channel, sound_ram, lfo_counter=state['lfo_counter'],
                                         lfo_phase=state['lfo_phase']) if start else SampleStream(channel, sound_ram))
    signal = model.render(count, filtered=True, key_off_samples=key_off_samples)
    levels = [255] + [(15 - i) * 8 for i in range(1, 16)]
    attenuation = [channel['total_level'] + levels[channel['direct_level']]] * 2
    pan = channel['pan_raw']
    attenuation[1 if pan & 16 else 0] += levels[(~pan) & 15]
    gains = [int(32768 / math.pow(2, a / 16)) for a in range(256)]
    output = [tuple((sample * gains[min(255, ofs + a)]) >> 19 for a in attenuation)
              for sample, ofs in zip(signal, model.attenuation)]
    return output, model.state


def direct_stereo_words(words, sound_ram, count, *, lfo_counter, lfo_phase, key_off_samples=()):
    """Fresh native note from 18 prepared registers and an explicit LFO clock.

    No captured stream, envelope, filter or ADPCM runtime is consumed.
    DSP returns and command/sample scheduling are outside this function.
    """
    if len(words) != 18 or any(not isinstance(w, int) or not 0 <= w <= 0xffffffff for w in words):
        raise ValueError('Expected 18 unsigned AICA register words')
    control = words[0]
    channel = dict(register_words=list(words), pcm_mode=(control >> 7) & 3,
        sample_address=(control & 127) << 16 | words[1], loop=bool(control & 0x200),
        loop_start=words[2], loop_end=words[3], fns=words[6] & 1023,
        octave_raw=(words[6] >> 11) & 15, lfo_raw=words[7], pan_raw=words[9] & 31,
        direct_level=(words[9] >> 8) & 15, total_level=words[10] >> 8,
        runtime=dict(lfo_counter=lfo_counter, lfo_phase=lfo_phase))
    return direct_stereo(channel, sound_ram, count, key_off_samples, start=True)
