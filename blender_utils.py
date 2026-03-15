import os
import subprocess
import re
import json
import struct
import sys
from functools import lru_cache

@lru_cache(maxsize=128)
def get_blender_label(exe: str, mtime: float = 0) -> str:
    """Get the version string of a Blender executable with caching.
    The mtime parameter is used to invalidate lru_cache if the file changed.
    """
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        r = subprocess.run([exe, "--version"], capture_output=True, text=True,
                           timeout=10, creationflags=flags)
        for line in r.stdout.splitlines():
            if "Blender" in line:
                return line.strip()
    except Exception:
        pass
    return os.path.basename(os.path.dirname(exe))

def get_blender_version_tuple(exe: str) -> tuple[int, ...]:
    label = get_blender_label(exe)
    m = re.search(r"Blender (\d+)\.(\d+)(?:\.(\d+))?", label)
    if m:
        parts = [int(m.group(1)), int(m.group(2))]
        if m.group(3):
            parts.append(int(m.group(3)))
        return tuple(parts)
    return (0,)

def parse_version_tuple(ver_str: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in ver_str.strip().split(".") if x.isdigit())
    except Exception:
        return (0,)

def get_blend_file_version(filepath: str) -> str:
    """Extract Blender version from .blend file header."""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(32)
            if header.startswith(b'BLENDER'):
                idx = header.find(b'v')
                if idx == -1:
                    idx = header.find(b'V')
                if idx != -1 and idx + 1 < len(header):
                    v_bytes = b''
                    for b in header[idx+1:]:
                        if ord(b'0') <= b <= ord(b'9'):
                            v_bytes += bytes([b])
                        else:
                            break
                    if v_bytes:
                        v = v_bytes.decode('ascii').lstrip('0')
                        if not v: v = '0'
                        if len(v) >= 3:
                            major = int(v[0])
                            minor, patch = v[1], v[2]
                            return f"{major}.{minor}" if patch == '0' else f"{major}.{minor}.{patch}" if major >= 3 else f"{major}.{v[1:]}"
                        elif len(v) == 2:
                            return f"{v[0]}.{v[1]}"
                        else:
                            return v
    except Exception:
        pass
    return ""

def extract_blend_thumbnail(filepath: str) -> "tuple[int, int, bytes] | None":
    """Extract RGBA thumbnail from .blend file."""
    try:
        with open(filepath, 'rb') as f:
            head = f.read(12)
            if head[0:2] == b'\x1f\x8b': # gzip
                import gzip, io
                f.seek(0)
                f = io.BytesIO(gzip.decompress(f.read()))
                head = f.read(12)

            if not head.startswith(b'BLENDER'): return None
            is_64_bit = (head[7] == ord('-'))
            is_big_endian = (head[8] == ord('V'))
            if head[9:11] <= b'24': return None # No thumbnails pre-2.5

            sizeof_bhead = 24 if is_64_bit else 20
            len_fmt = '>i' if is_big_endian else '<i'
            xy_fmt = '>ii' if is_big_endian else '<ii'

            while True:
                bhead = f.read(sizeof_bhead)
                if len(bhead) < sizeof_bhead: return None
                code_bytes = bhead[0:4]
                length = struct.unpack(len_fmt, bhead[4:8])[0]
                if code_bytes == b'REND':
                    f.seek(length, os.SEEK_CUR)
                    continue
                break

            if code_bytes != b'TEST': return None
            wh = f.read(8)
            if len(wh) < 8: return None
            x, y = struct.unpack(xy_fmt, wh)
            length -= 8
            if length != x * y * 4 or x <= 0 or y <= 0: return None
            return (x, y, f.read(length))
    except Exception:
        pass
    return None

def get_supported_engines(exe: str) -> list[str]:
    v = get_blender_version_tuple(exe)
    if v[0] >= 5: return ["BLENDER_EEVEE", "CYCLES"]
    if v[0] == 4 and v[1] >= 2: return ["BLENDER_EEVEE_NEXT", "CYCLES"]
    if v[0] == 4: return ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"]
    return ["BLENDER_EEVEE", "CYCLES"]

def get_supported_formats(exe: str) -> list[str]:
    v = get_blender_version_tuple(exe)
    base = ["PNG", "JPEG", "BMP", "TIFF", "OPEN_EXR", "OPEN_EXR_MULTILAYER"]
    dpx = ["CINEON", "DPX"]
    hdr = ["HDR"]
    video = ["FFMPEG"]
    if v[0] >= 5: return base + ["WEBP"] + hdr + video
    if v[0] == 4 and v[1] >= 2: return base + ["WEBP"] + dpx + hdr + video
    if v[0] == 4: return base + dpx + hdr + video
    return base + dpx + hdr + video + ["AVI_JPEG", "AVI_RAW", "IRIS"]
