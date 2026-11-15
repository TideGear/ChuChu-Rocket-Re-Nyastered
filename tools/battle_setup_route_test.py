"""Exercise the live iPad Battle setup route without opening a window."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
EXE = ROOT / 'build' / 'game' / 'ccr.exe'
ASSETS = ROOT / 'local' / 'cache' / 'assets'


def main():
    with TemporaryDirectory() as temp:
        base = dict(os.environ, CCR_HEADLESS='1', CCR_SIZE='1024x768', CCR_LANG='en',
                    CCR_BATTLE_SETUP_TRACE='1')
        for key in ('CCR_KEYS', 'CCR_CLICKS', 'CCR_AUDIO_TEST', 'CCR_PAD_PLAYERS', 'CCR_PAD_RULES',
                    'CCR_PAD_PREVIEW', 'CCR_HUMANS', 'CCR_TEAM', 'CCR_MINUTES', 'CCR_WINPOINT'):
            base.pop(key, None)

        def capture(label, ticks, **options):
            path = Path(temp) / f'{label}.bmp'
            env = dict(base, CCR_SHOT=str(path), CCR_TICKS=str(ticks), **options)
            out = subprocess.run([EXE, ASSETS, 'menu'], env=env, check=True,
                                 text=True, capture_output=True).stdout
            with Image.open(path) as frame:
                return frame.convert('RGB'), out.splitlines()

        menu = '32:480,460;33:480,460'
        players, _ = capture('players', 99, CCR_CLICKS=menu)
        players_ref, _ = capture('players-ref', 1, CCR_PAD_PLAYERS='1,0,0,0,0,0,0,0,-1,-1')
        assert ImageChops.difference(players, players_ref).getbbox() is None

        configured = (menu + ';100:400,230;101:550,290;102:560,410;103:500,75;105:995,739;'
                      '106:410,270;107:480,460;108:480,520;109:550,270;110:550,270;111:810,330')
        settings, _ = capture('settings', 115, CCR_CLICKS=configured)
        settings_ref, _ = capture('settings-ref', 1, CCR_PAD_RULES='3,3,0,1,0', CCR_PAD_PREVIEW='3,1')
        assert ImageChops.difference(settings, settings_ref).getbbox() is None

        _, log = capture('battle', 260, CCR_CLICKS=configured + ';117:680,440')
        assert len(log) == 1, log
        name, stage, team, points, timer, speed, special, *levels = log[0].split()
        assert (name, stage, team, points, timer) == ('battle', '3', '1', '3', '3600'), log
        assert (float.fromhex(speed), float.fromhex(special)) == (1.25, 0.5), log
        assert list(map(int, levels)) == [-1, -1, 3, 0], log

        _, log = capture('split-refused', 140, CCR_CLICKS=configured + ';117:600,650;119:995,739')
        assert not log, log
        for team, setup in ((0, menu + ';105:995,739'), (1, configured)):
            _, log = capture(f'question-mark-{team}', 260,
                             CCR_CLICKS=setup + ';117:455,410;119:995,739')
            assert len(log) == 1 and log[0].split()[:3] == ['battle', '24', str(team)], log
        _, log = capture('back', 150, CCR_CLICKS=menu + ';100:995,739;102:25,740;104:25,740')
        assert not log, log
    print('Live Players and Settings frames match the verified pane draws, and the selected rules reach the match')


if __name__ == '__main__':
    main()
