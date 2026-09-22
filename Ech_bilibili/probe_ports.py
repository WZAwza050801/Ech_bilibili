# -*- coding: utf-8 -*-
"""probe_ports.py — 探测本机常见代理端口是否可用"""
import socket

def tcp_open(host, port, t=2):
    try:
        s = socket.create_connection((host, port), timeout=t)
        s.close()
        return True
    except Exception:
        return False

ports = [12000, 2213, 7890, 7897, 10808, 10809, 1080, 8888, 2080, 20171]
alive = [p for p in ports if tcp_open("127.0.0.1", p)]
print("OPEN:", alive if alive else "none")

# 若有端口, 测一下 google 204
import urllib.request
for p in alive:
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": f"http://127.0.0.1:{p}", "https": f"http://127.0.0.1:{p}"}))
        r = opener.open("http://www.google.com/generate_204", timeout=8)
        print(p, "->", r.status)
    except Exception as e:
        print(p, "-> FAIL", str(e)[:60])
