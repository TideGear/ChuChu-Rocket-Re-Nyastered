"""PCM16 stream stepping, periodic pitch LFO and fixed filter validation.

Consumes captured channel state. Output precedes amplitude, attenuation, effects
and stereo mixing. Only constant filter-envelope windows are accepted. This is
not a finished sound-effect renderer. Hardware field/step reference: Flycast core
3a5267a, core/hw/aica/sgc_if.cpp; compare with original core snapshots.
"""
import math
import struct


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


class Pcm16Stream:
    def __init__(self, channel, sound_ram):
        if channel['pcm_mode'] != 0 or not channel['runtime']['enabled']:
            raise ValueError('An enabled PCM16 channel is required')
        self.channel = channel
        self.ram = sound_ram
        self.state = dict(channel['runtime'])
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
        self.filter_active = not (words[10] & 32) and (any(v < 0x1ff8 for v in words[11:16]) or (words[10] & 31) != 4)
        if self.filter_active:
            value = self.state['filter_value'] >> 16
            if self.state['filter_state'] != 2 or self.state['filter_value'] != value << 16 or any(v != value for v in words[11:16]):
                raise ValueError('Changing filter envelopes are not yet validated')
            resonance = (2048, 1536, 1024, 512, 0, -256, -512, -768, -1024, -1280,
                         -1536, -1792, -2048, -2176, -2304, -2432, -2560, -2688,
                         -2816, -2944, -3072, -3136, -3200, -3264, -3328, -3392,
                         -3456, -3520, -3584, -3648, -3712, -3776)[words[10] & 31]
            exponent, mantissa = value >> 9, (value & 511) | 512
            a0 = ((((mantissa << 30) >> ((15 - exponent) * 2)) * ((mantissa - 1) // 8)) >> 17)
            feedback = (mantissa << exponent) << 5
            product = resonance * feedback
            feedback += (abs(product) // 4096) * (-1 if product < 0 else 1)
            self.filter_coefficients = a0, (1 << 31) - feedback - a0, (1 << 30) - feedback
            self.filter_exponent = exponent

    def filter(self, sample):
        if not self.filter_active:
            return sample
        state = self.state
        a0, b1, b2 = self.filter_coefficients
        fraction = state['filter_fraction'] if self.filter_exponent else 0
        accumulator = -a0 * sample + b1 * state['filter_previous1'] - b2 * state['filter_previous2'] - fraction
        value = accumulator >> 30
        state['filter_fraction'] = (value << 30) - accumulator
        state['filter_previous2'] = state['filter_previous1']
        state['filter_previous1'] = min(524287, max(-524288, value))
        return state['filter_previous1']

    def render(self, count, filtered=False):
        if count < 0:
            raise ValueError('Negative sample count')
        out = []
        state = self.state
        for _ in range(count):
            fraction = state['fraction']
            sample = ((state['s0'] * (1024 - fraction)) >> 10) + ((state['s1'] * fraction) >> 10)
            signal = self.filter(sample << 4)
            out.append(signal if filtered else sample)
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
                position = state['position'] + advance
                if position >= self.channel['loop_end']:
                    raise ValueError('Loop/end transition is outside this verified stream window')
                state['position'] = position
                offset = state['sample_address'] + 2 * position
                state['s0'], state['s1'] = struct.unpack_from('<2h', self.ram, offset)
            state['lfo_counter'] -= 1
            if state['lfo_counter'] == 0:
                state['lfo_counter'] = self.period
                state['lfo_phase'] = (phase + 1) & 255
        return out


def direct_stereo(channel, sound_ram, count):
    """Render the verified constant-envelope PCM16 window, without DSP returns."""
    state = channel['runtime']
    words = channel['register_words']
    if state['amplitude_value'] != 0 or state['amplitude_state'] != 2 or (words[4] >> 11) & 31:
        raise ValueError('Changing amplitude envelopes are not yet validated')
    if channel['lfo_raw'] & 7:
        raise ValueError('Amplitude LFO is not yet validated')
    model = Pcm16Stream(channel, sound_ram)
    signal = model.render(count, filtered=True)
    levels = [255] + [(15 - i) * 8 for i in range(1, 16)]
    attenuation = [channel['total_level'] + levels[channel['direct_level']]] * 2
    pan = channel['pan_raw']
    attenuation[1 if pan & 16 else 0] += levels[(~pan) & 15]
    gains = [int(32768 / math.pow(2, min(a, 255) / 16)) for a in attenuation]
    return [tuple((sample * gain) >> 19 for gain in gains) for sample in signal], model.state
