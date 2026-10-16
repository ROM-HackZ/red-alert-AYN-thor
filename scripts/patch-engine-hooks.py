"""Maintain the single loop hook in the upstream file containing legacy bytes.

Byte-preserving and idempotent: do not recode old string literals or comments as
a side effect of adding a hook. Other engine changes use normal source edits.
"""
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "redalert/conquer.cpp"
data = path.read_bytes()
newline = b"\r\n" if b"\r\n" in data else b"\n"
old = newline.join([b"bool Main_Loop()", b"{", b""])
new = old + newline.join([b"#ifdef THOR_ANDROID",b"    extern void Thor_Mission(bool);",b"    Thor_Mission(GameActive);",b"#endif",b""])
if new not in data:
    if data.count(old) != 1: raise RuntimeError("Main loop changed upstream; review the Thor hook")
    path.write_bytes(data.replace(old,new,1))
