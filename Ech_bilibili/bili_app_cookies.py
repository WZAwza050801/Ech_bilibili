# -*- coding: utf-8 -*-
"""bili_app_cookies.py — 解密 B 站桌面客户端(Electron/Chromium)的 cookie, 导出 Netscape cookies.txt
v10/v11 前缀 = AES-256-GCM(key 在 Local State, DPAPI 解); 无前缀 = 直接 DPAPI
用 Windows CNG (BCrypt) 做 AES-GCM, 零第三方依赖。只打印 cookie 名, 不打印值。
"""
import ctypes, json, sqlite3, shutil, sys, io, os, time, tempfile, base64
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

APP = Path(os.environ["APPDATA"]) / "bilibili"
CK = APP / "Network" / "Cookies"
LS = APP / "Local State"
if len(sys.argv) >= 3:  # 指定其他 Chromium 内核浏览器: <Cookies路径> <LocalState路径>
    CK, LS = Path(sys.argv[1]), Path(sys.argv[2])
OUT = Path(r"D:\视频观看agent编写\Ech_bilibili\bili_cookies.txt")
print(f"来源: {CK}")

# ---------- DPAPI ----------
def dpapi(data: bytes) -> bytes:
    class BLOB(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("bp", ctypes.POINTER(ctypes.c_char))]
    buf = ctypes.create_string_buffer(data, len(data))
    b_in = BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    b_out = BLOB()
    r = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(b_in), None, None, None, None, 0, ctypes.byref(b_out))
    if not r:
        raise OSError("CryptUnprotectData failed")
    out = ctypes.string_at(b_out.bp, b_out.cb)
    ctypes.windll.kernel32.LocalFree(b_out.bp)
    return out

# ---------- AES-GCM via CNG ----------
class AUTHINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("dwInfoVersion", ctypes.c_ulong),
                ("pbNonce", ctypes.c_void_p), ("cbNonce", ctypes.c_ulong),
                ("pbTag", ctypes.c_void_p), ("cbTag", ctypes.c_ulong),
                ("pbAAD", ctypes.c_void_p), ("cbAAD", ctypes.c_ulong),
                ("pbMacContext", ctypes.c_void_p), ("cbMacContext", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong)]

def aes_gcm_decrypt(key: bytes, nonce: bytes, ct_and_tag: bytes) -> bytes:
    ct, tag = ct_and_tag[:-16], ct_and_tag[-16:]
    bcrypt = ctypes.windll.bcrypt
    hAlg = ctypes.c_void_p()
    bcrypt.BCryptOpenAlgorithmProvider(ctypes.byref(hAlg), "AES", None, 0)
    val = ctypes.create_unicode_buffer("ChainingModeGCM")
    str_ = ctypes.create_unicode_buffer("ChainingMode")
    bcrypt.BCryptSetProperty(hAlg, str_, val, 2 * len("ChainingModeGCM"), 0)
    hKey = ctypes.c_void_p()
    kb = ctypes.create_string_buffer(key, len(key))
    bcrypt.BCryptGenerateSymmetricKey(hAlg, ctypes.byref(hKey), None, 0, kb, len(key), 0)
    nb = ctypes.create_string_buffer(nonce, len(nonce))
    tb = ctypes.create_string_buffer(tag, len(tag))
    ai = AUTHINFO()
    ai.cbSize = ctypes.sizeof(ai); ai.dwInfoVersion = 1
    ai.pbNonce = ctypes.cast(nb, ctypes.c_void_p); ai.cbNonce = len(nonce)
    ai.pbTag = ctypes.cast(tb, ctypes.c_void_p); ai.cbTag = len(tag)
    cb = ctypes.create_string_buffer(ct, max(len(ct), 1))
    out = ctypes.create_string_buffer(len(ct) + 16)
    res = ctypes.c_ulong()
    st = bcrypt.BCryptDecrypt(hKey, ctypes.cast(cb, ctypes.c_void_p), len(ct),
                              ctypes.byref(ai), None, 0, out, len(out), ctypes.byref(res), 0)
    bcrypt.BCryptDestroyKey(hKey); bcrypt.BCryptCloseAlgorithmProvider(hAlg, 0)
    if st != 0:
        raise OSError(f"BCryptDecrypt status=0x{st:08x}")
    return out.raw[:res.value]

# ---------- 1. AES key from Local State ----------
ls = json.loads(LS.read_text(encoding="utf-8"))
enc_key_b64 = ls["os_crypt"]["encrypted_key"]
aes_key = dpapi(base64.b64decode(enc_key_b64)[5:])
print(f"AES key 解出: {len(aes_key)} 字节")

# ---------- 2. 读 cookie 库 ----------
tmp = Path(tempfile.gettempdir()) / f"bili_ck_{int(time.time())}.sqlite"
shutil.copy2(CK, tmp)
con = sqlite3.connect(str(tmp))
cols = [r[1] for r in con.execute("PRAGMA table_info(cookies)").fetchall()]
host_col = "host_key" if "host_key" in cols else "host"
rows = con.execute(
    f"SELECT {host_col}, name, path, is_secure, expires_utc, encrypted_value, value "
    "FROM cookies WHERE " + host_col + " LIKE '%bilibili%'").fetchall()
con.close(); tmp.unlink()
print(f"bilibili cookie 共 {len(rows)} 条")

# chromium 时间: 1601 起的 0.1us
def to_epoch(ts):
    return int((ts - 11644473600000000) / 1_000_000) if ts else 0

jar, names = [], []
for host, name, path, secure, expires, ev, plain in rows:
    val = None
    if plain:
        val = plain
    elif ev[:3] in (b"v10", b"v11"):
        try:
            val = aes_gcm_decrypt(aes_key, ev[3:15], ev[15:]).decode("utf-8", "replace")
        except Exception as e:
            print(f"  [AES失败] {name}: {e}")
    else:
        try:
            val = dpapi(ev).decode("utf-8", "replace")
        except Exception as e:
            print(f"  [DPAPI失败] {name}: {e}")
    if val:
        names.append(name)
        jar.append((host, path, secure, to_epoch(expires) or 2145916800, name, val))

print("解出的 cookie 名:", ", ".join(sorted(set(names))))
print(f"SESSDATA: {'✓ 有' if 'SESSDATA' in names else '✗ 无'}")

# ---------- 3. Netscape 格式导出 ----------
lines = ["# Netscape HTTP Cookie File"]
for host, path, secure, exp, name, val in jar:
    dom_flag = "TRUE" if host.startswith(".") else "FALSE"
    sec_flag = "TRUE" if secure else "FALSE"
    lines.append(f"{host}\t{dom_flag}\t{path}\t{sec_flag}\t{exp}\t{name}\t{val}")
OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"导出: {OUT} ({len(jar)} 条)")
