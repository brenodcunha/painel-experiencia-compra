# -*- coding: utf-8 -*-
"""Sobe o painel de experiencia de compra. Uso: python ligar.py

Antes de subir, confere o repositorio publico (atualizador.py): se ha versao nova, baixa e
troca os arquivos do pacote sozinho — nunca conta.json nem dados.json — e derruba o
servidor velho se ele estava no ar, para subir o novo. Sem internet, segue com a versao
que esta.

    python ligar.py --reiniciar    (uso interno: o servidor chama depois de se atualizar)
"""
import os, socket, subprocess, sys, time, urllib.request, webbrowser
BASE = os.path.dirname(os.path.abspath(__file__)); PORTA = 8796; URL = "http://localhost:%d" % PORTA
sys.path.insert(0, BASE)
REINICIAR = "--reiniciar" in sys.argv


def no_ar():
    s = socket.socket(); s.settimeout(0.6)
    try:
        s.connect(("127.0.0.1", PORTA)); return True
    except Exception:
        return False
    finally:
        s.close()


def espera(condicao, seg):
    for _ in range(int(seg * 2)):
        if condicao():
            return True
        time.sleep(0.5)
    return condicao()


def atualiza():
    """Versao nova no repositorio -> troca os arquivos e derruba o servidor velho."""
    try:
        import atualizador
        v = atualizador.verificar(forcar=True)
        if not v.get("disponivel"):
            return
        print("versao nova do painel (%s -> %s): atualizando..." % (v.get("atual"), v.get("versao")))
        ok, msg = atualizador.atualizar()
        print(" ", msg)
        if ok and no_ar():                    # o servidor no ar tem a versao velha na memoria
            try:
                urllib.request.urlopen(urllib.request.Request(URL + "/api/reiniciar", method="POST"), timeout=5)
            except Exception:
                pass
            espera(lambda: not no_ar(), 20)
    except Exception as e:                    # sem internet, sem repositorio: segue como esta
        print("sem atualizacao automatica agora:", e)


def sobe():
    print("subindo...")
    log = open(os.path.join(BASE, "servidor.log"), "a", encoding="utf-8")
    # solto do terminal: fechar a janela do ligar.py nao derruba o painel
    flags = ({"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)}
             if os.name == "nt" else {"start_new_session": True})
    subprocess.Popen([sys.executable, os.path.join(BASE, "servidor.py")], stdout=log, stderr=log, cwd=BASE, **flags)
    if not espera(no_ar, 40):
        print("nao subiu - veja servidor.log"); sys.exit(1)
    print("no ar em", URL)


if REINICIAR:
    espera(lambda: not no_ar(), 30)           # o servidor velho esta saindo
else:
    atualiza()
if no_ar():
    print("ja esta no ar em", URL)
else:
    sobe()
if not REINICIAR and not os.environ.get("PAINEL_SEM_NAVEGADOR"):
    webbrowser.open(URL)
