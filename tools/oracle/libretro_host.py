"""Headless libretro host (development only): runs a libretro core (e.g. Flycast) via ctypes without any window or audio output.
Keeps BIOS/save directories away from the user's own RetroArch folders (system dir = a local copy, save dir = temp).
usage: h = Host(core_dll, system_dir, save_dir); h.load(content_path); h.run(n); h.ram() -> bytes"""
import ctypes, os, sys
from ctypes import c_char_p, c_void_p, c_uint, c_int, c_bool, c_size_t, c_float, POINTER, CFUNCTYPE, Structure, byref

class GameInfo(Structure): _fields_ = [('path', c_char_p), ('data', c_void_p), ('size', c_size_t), ('meta', c_char_p)]
class SysAV(Structure): _fields_ = [('base_w', c_uint), ('base_h', c_uint), ('max_w', c_uint), ('max_h', c_uint), ('aspect', c_float)]
class SysTiming(Structure): _fields_ = [('fps', ctypes.c_double), ('sample_rate', ctypes.c_double)]
class AVInfo(Structure): _fields_ = [('geometry', SysAV), ('timing', SysTiming)]
class Var(Structure): _fields_ = [('key', c_char_p), ('value', c_char_p)]
ENV = CFUNCTYPE(c_bool, c_uint, c_void_p); VIDEO = CFUNCTYPE(None, c_void_p, c_uint, c_uint, c_size_t); AUDIO1 = CFUNCTYPE(None, ctypes.c_int16, ctypes.c_int16)
AUDIO = CFUNCTYPE(c_size_t, c_void_p, c_size_t); POLL = CFUNCTYPE(None); INPUT = CFUNCTYPE(ctypes.c_int16, c_uint, c_uint, c_uint, c_uint)
LOG = CFUNCTYPE(None, c_int, c_char_p)

class Host:
    def __init__(self, dll, system_dir, save_dir, options=None):
        os.makedirs(save_dir, exist_ok=True); os.add_dll_directory(os.path.dirname(dll))
        self.lib = ctypes.CDLL(dll); self.system = system_dir.encode(); self.save = save_dir.encode(); self.options = options or {}
        self.buttons = {}; self.frames = 0; self.pixfmt = None; self.log = []
        self._keep = [ENV(self._env), VIDEO(lambda d, w, h, p: None), AUDIO1(lambda l, r: None), AUDIO(lambda d, n: n), POLL(lambda: None), INPUT(self._input)]
        L = self.lib
        L.retro_set_environment(self._keep[0]); L.retro_set_video_refresh(self._keep[1]); L.retro_set_audio_sample(self._keep[2])
        L.retro_set_audio_sample_batch(self._keep[3]); L.retro_set_input_poll(self._keep[4]); L.retro_set_input_state(self._keep[5])
        L.retro_get_memory_data.restype = c_void_p; L.retro_get_memory_size.restype = c_size_t
        L.retro_init()
    def _input(self, port, device, index, id_): return self.buttons.get((port, id_), 0)
    def _env(self, cmd, data):
        cmd &= 0xffff
        if cmd == 9: ctypes.cast(data, POINTER(c_char_p))[0] = self.system; return True          # GET_SYSTEM_DIRECTORY
        if cmd == 31: ctypes.cast(data, POINTER(c_char_p))[0] = self.save; return True           # GET_SAVE_DIRECTORY
        if cmd == 10: self.pixfmt = ctypes.cast(data, POINTER(c_int))[0]; return True            # SET_PIXEL_FORMAT
        if cmd == 3: ctypes.cast(data, POINTER(c_bool))[0] = True; return True                   # GET_CAN_DUPE
        if cmd == 15:                                                                           # GET_VARIABLE
            v = ctypes.cast(data, POINTER(Var))[0]; k = v.key.decode() if v.key else ''
            if k in self.options: self._val = self.options[k].encode(); v.value = self._val; ctypes.cast(data, POINTER(Var))[0] = v; return True
            return False
        if cmd in (17,): ctypes.cast(data, POINTER(c_bool))[0] = False; return True                # GET_VARIABLE_UPDATE
        if cmd in (16, 11, 35, 18, 36, 37, 44): return True                                      # SET_VARIABLES/INPUT_DESCRIPTORS/CONTROLLER_INFO/SUPPORT_NO_GAME/MEMORY_MAPS ...
        if cmd == 27: return False
        return False
    def load(self, path):
        info = GameInfo(path.encode(), None, 0, None); ok = self.lib.retro_load_game(byref(info))
        av = AVInfo(); self.lib.retro_get_system_av_info(byref(av)); self.av = av
        return bool(ok)
    def run(self, n=1):
        for _ in range(n): self.lib.retro_run(); self.frames += 1
    def ram(self, kind=2):
        p = self.lib.retro_get_memory_data(kind); n = self.lib.retro_get_memory_size(kind)
        return ctypes.string_at(p, n) if p and n else b''

if __name__ == '__main__':
    h = Host(r'C:\Users\Tideg\My Drive\RetroArch\Cores\flycast_libretro.dll', r'C:\Dev\ChuChu Rocket\local\dcsys', r'C:\Dev\ChuChu Rocket\local\dcsave')
    ok = h.load(sys.argv[1]); print('loaded', ok, 'av', h.av.geometry.base_w, h.av.geometry.base_h, h.av.timing.fps)
    h.run(int(sys.argv[2]) if len(sys.argv) > 2 else 60); r = h.ram(); print('frames', h.frames, 'ram bytes', len(r))
