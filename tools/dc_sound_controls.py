"""Controller calculations from the tested MANATEE ARM driver, not synthesis."""


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
