"""Exact transform of a drawn mesh instance from the real PowerVR stream: unproject the vertices (1/w = 1/(218 - height), screen centre (320, 240), 2.5427 px per model unit at the floor
plane) and fit a similarity transform (Umeyama) to the model's own vertices in strip order. Used to read tilt, yaw, scale and animation frame of every mesh. See docs/dreamcast_models.md."""
import sys, os, struct, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import numpy as np
BASE = 0x8c010000
CELL_PX = 457.67653 / 12            # floor plane in 640 x 480 pixels per cell (Flycast frames), 15 world units per cell
PX_PER_UNIT = CELL_PX / 15.0
DIST = 218.0
FOCAL = PX_PER_UNIT * DIST
def unproject(sx, sy, inv_w):
    depth = 1.0 / inv_w
    return np.array([(sx - 320.0) * depth / FOCAL, DIST - depth, (sy - 240.0) * depth / FOCAL])   # X right, Y up (height above the floor plane), Z down the screen
def umeyama(src, dst, allow_reflection=False):
    mu_s, mu_d = src.mean(0), dst.mean(0); s0, d0 = src - mu_s, dst - mu_d
    cov = d0.T @ s0 / len(src); U, S, Vt = np.linalg.svd(cov)
    D = np.eye(3)
    if not allow_reflection and np.linalg.det(U) * np.linalg.det(Vt) < 0: D[2, 2] = -1
    R = U @ D @ Vt; var = (s0 ** 2).sum() / len(src); k = np.trace(np.diag(S) @ D) / var
    t = mu_d - k * R @ mu_s
    return k, R, t
def euler_yxz(R):
    """R = Ry(yaw) Rx(pitch) Rz(roll) (column vectors); degrees"""
    pitch = math.asin(max(-1, min(1, -R[1, 2])))
    yaw = math.atan2(R[0, 2], R[2, 2]); roll = math.atan2(R[1, 0], R[1, 1])
    return [math.degrees(x) for x in (yaw, pitch, roll)]
def uv_of(poly, v):
    """UV of a stream vertex: packed 16-bit when the header's ctrl bit 0 is set, else two floats"""
    return (v[8], v[9]) if poly['ctrl'] & 1 else (v[4], v[5])
