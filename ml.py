# -*- coding: utf-8 -*-
"""Chamadas a API do Mercado Livre usando a credencial do proprio vendedor.

O token vem de conta.py (arquivo conta.json nesta pasta). Nao depende de
nenhum outro projeto: quem instalar o painel usa o app dele.
"""
import json, os, sys, time, urllib.request, urllib.error

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import conta

API = "https://api.mercadolibre.com"
TENTATIVAS = 5      # 429, 5xx e queda de rede: espera e tenta de novo


def _parse(txt):
    try:
        return json.loads(txt) if txt else {}
    except Exception:
        return {"_raw": txt[:500]}


def req(path, method="GET", data=None, _renovou=False):
    """GET/POST na API com o token do vendedor.

    Devolve (status, json). Nunca levanta excecao: rede fora do ar vira
    (-1, {"erro": ...}). 429 e 5xx sao repetidos com espera crescente — sem
    isso um lote grande (2.000 notas em paralelo) perdia respostas em silencio
    e o painel mostrava "sem nota" para anuncio que tem nota. O 401 renova o
    token UMA vez; se continuar 401, devolve 401 (antes podia recursar sem fim).
    """
    t = conta.token()
    if not t:
        return 401, {"erro": "conta nao conectada"}
    h = {"Accept": "application/json", "Authorization": "Bearer " + t}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        h["Content-Type"] = "application/json"
    ultimo = (-1, {"erro": "sem resposta"})
    for k in range(TENTATIVAS):
        r = urllib.request.Request(API + path, data=body, method=method, headers=h)
        try:
            with urllib.request.urlopen(r, timeout=60) as x:
                return x.status, _parse(x.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            txt = e.read().decode("utf-8", "replace")
            if e.code == 401 and not _renovou and conta._renovar():   # token venceu no meio
                return req(path, method, data, _renovou=True)
            if e.code == 429 or e.code >= 500:
                try:
                    espera = float(e.headers.get("Retry-After") or 0)
                except ValueError:
                    espera = 0
                time.sleep(min(espera or 1.5 * (k + 1), 20))
                ultimo = (e.code, _parse(txt))
                continue
            return e.code, _parse(txt)
        except Exception as e:                       # rede, DNS, timeout
            ultimo = (-1, {"erro": str(e)})
            time.sleep(1.5 * (k + 1))
    return ultimo


def g(p):
    return req(p)


def ensure_auth():
    st, _ = req("/users/me")
    if st == 200:
        return True
    if conta._renovar():
        st, _ = req("/users/me")
    return st == 200
