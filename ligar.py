# -*- coding: utf-8 -*-
"""Sobe o painel de experiencia de compra. Uso: python ligar.py"""
import os, socket, subprocess, sys, time, webbrowser
BASE=os.path.dirname(os.path.abspath(__file__)); PORTA=8796; URL="http://localhost:%d"%PORTA
def no_ar():
    s=socket.socket(); s.settimeout(0.6)
    try: s.connect(("127.0.0.1",PORTA)); return True
    except Exception: return False
    finally: s.close()
if no_ar():
    print("ja esta no ar em",URL)
else:
    print("subindo...")
    log=open(os.path.join(BASE,"servidor.log"),"w",encoding="utf-8")
    subprocess.Popen([sys.executable,os.path.join(BASE,"servidor.py")],stdout=log,stderr=log,cwd=BASE)
    for _ in range(40):
        time.sleep(1)
        if no_ar(): break
    else:
        print("nao subiu - veja servidor.log"); sys.exit(1)
    print("no ar em",URL)
webbrowser.open(URL)
