"""Linear MANATEE command scheduling, without voice allocation or synthesis.

One isolated group, available FIFO capacity and ordinary free-slot gates only.
Full gate tables, continuation records and looping are unsupported.
"""
from dc_sound_timing import LinearSequenceClock
from dc_sound_gate import NoteGate


class SequenceCommands:
    def __init__(self, sequence, group=1, priority=0):
        if not 0 <= group < 8 or not 0 <= priority <= 255:
            raise ValueError('Invalid sequence group or priority')
        self.clock = LinearSequenceClock(sequence)
        self.group = group
        self.priority = priority & 0xf8
        self.gates = [NoteGate(0, 0, 0) for _ in range(64)]

    def update(self, increment=0x4000):
        commands = []
        for gate in self.gates:
            command = gate.advance(increment)
            if command is not None:
                commands.append(command)

        def event(row, timing):
            kind = row['type']
            if kind == 'sysex':
                payload = bytes(row['data'])
                if not 1 <= len(payload) <= 5:
                    raise ValueError('System-exclusive payloads over five bytes are not validated')
                commands.append((self.priority | 7) << 24 | self.group << 20 |
                                (len(payload) & 255) << 8 | payload[0])
                for offset in range(1, len(payload), 4):
                    commands.append(int.from_bytes(payload[offset:offset + 4].ljust(4, b'\0'), 'big'))
            elif kind == 'note':
                gate = NoteGate.from_note(self.priority, self.group, row['channel'],
                                          row['note'], row['velocity'], row['gate'],
                                          timing.scale, sequence_time=timing.time)
                index = next((i for i, g in enumerate(self.gates) if not g.command), None)
                if index is None:
                    raise ValueError('Full gate-table stealing is not implemented')
                self.gates[index] = gate
                commands.append(gate.command | 0x1000000)
            elif kind in ('control', 'program', 'pressure', 'pitch'):
                tag = {'control': 3, 'program': 4, 'pressure': 5, 'pitch': 6}[kind]
                command = ((self.priority | tag) << 24 | self.group << 20 | row['channel'] << 16)
                if kind == 'control':
                    command |= row['controller'] << 8 | row['value']
                elif kind == 'pitch':
                    command |= row['value'] + 64
                else:
                    command |= row['value'] << 8
                commands.append(command)

        self.clock.update(increment, on_event=event)
        return commands
