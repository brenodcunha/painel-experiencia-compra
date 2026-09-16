# -*- coding: utf-8 -*-
"""Credencial do Mercado Livre — uma conta, o app do proprio vendedor.

O vendedor cria o app dele em developers.mercadolivre.com.br e cola aqui
APP_ID, SECRET e a URL de redirecionamento que ele cadastrou. O painel nunca
usa app de terceiro: o token fica so na maquina dele, em conta.json.

FLUXO (colar o codigo):
    1. salvar_app(app_id, secret, redirect)   grava as credenciais
    2. url_autorizacao()                      o vendedor abre e autoriza no ML
    3. o ML manda o navegador para  <redirect>?code=TG-xxxx
    4. trocar_codigo("TG-xxxx")               vira access_token + refresh_token

Depois disso token() renova sozinho quando vence — o refresh_token do ML dura
6 meses e cada renovacao devolve um novo.
"""
import re
import json, os, threading, time, urllib.parse, urllib.request, urllib.error

BASE = os.path.dirname(os.path.abspath(__file__))
CRED = os.path.join(BASE, "conta.json")
API = "https://api.mercadolibre.com"
AUTH = "https://auth.mercadolivre.com.br/authorization"
_TRAVA = threading.Lock()     # servidor e coletor renovam token em threads diferentes


def _ler():
    if not os.path.exists(CRED):
        return {}
    try:
        return json.load(open(CRED, encoding="utf-8"))
    except Exception:
        return {}


def _gravar(d):
    # ⚠️ atomico: escreve num temporario e troca. Este arquivo guarda o
    # refresh_token — um travamento no meio da escrita deixava JSON pela
    # metade, _ler() devolvia {} e o vendedor perdia a conexao (e o SMS).
    tmp = CRED + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, CRED)
    try:                      # a credencial e so do dono
        os.chmod(CRED, 0o600)
    except Exception:
        pass


def _post_form(path, campos):
    corpo = urllib.parse.urlencode(campos).encode()
    r = urllib.request.Request(API + path, data=corpo, method="POST", headers={
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(r, timeout=30) as x:
            return x.status, json.loads(x.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as e:
        t = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(t)
        except Exception:
            return e.code, {"message": t[:300]}
    except Exception as e:
        return -1, {"message": str(e)}


def salvar_app(app_id, secret, redirect):
    d = _ler()
    novo_id = str(app_id).strip()
    if d.get("app_id") and d["app_id"] != novo_id:
        # token de um app nao serve para outro: sem isto o painel dizia
        # "conectado" e a renovacao falhava com invalid_client
        for k in ("access_token", "refresh_token", "vence"):
            d.pop(k, None)
    d.update({"app_id": novo_id, "secret": str(secret).strip(),
              "redirect": str(redirect).strip()})
    _gravar(d)
    return d


def url_autorizacao():
    d = _ler()
    if not d.get("app_id") or not d.get("redirect"):
        return None
    return "%s?%s" % (AUTH, urllib.parse.urlencode({
        "response_type": "code", "client_id": d["app_id"], "redirect_uri": d["redirect"]}))


def trocar_codigo(code):
    """Troca o code por tokens. Aceita a URL inteira colada, nao so o codigo."""
    d = _ler()
    if not d.get("app_id"):
        return False, "Preencha e salve o passo .01 (App ID e chave secreta) antes de colar o código."
    ASPAS = "\"' \t\r\n"
    code = (code or "").strip(ASPAS)
    if "code=" in code:                       # colou a URL inteira
        q = urllib.parse.urlparse(code).query or code.split("?", 1)[-1]
        code = (urllib.parse.parse_qs(q).get("code") or [code])[0]
    else:
        # colou so o pedaco do httpbin, que aparece entre aspas no JSON
        m = re.search(r"TG-[A-Za-z0-9._-]+", code)
        if m:
            code = m.group(0)
    code = code.strip(ASPAS)
    st, r = _post_form("/oauth/token", {
        "grant_type": "authorization_code", "client_id": d["app_id"],
        "client_secret": d["secret"], "code": code, "redirect_uri": d["redirect"]})
    if st != 200 or not r.get("access_token"):
        return False, r.get("message") or r.get("error_description") or json.dumps(r)[:200]
    d.update({"access_token": r["access_token"], "refresh_token": r.get("refresh_token"),
              "user_id": r.get("user_id"), "vence": time.time() + (r.get("expires_in") or 21600) - 120})
    _gravar(d)
    ok, quem = _quem()
    return (True, quem) if ok else (False, quem)


def _renovar():
    with _TRAVA:
        return _renovar_sem_trava()


def _renovar_sem_trava():
    d = _ler()
    if not d.get("refresh_token"):
        return False
    st, r = _post_form("/oauth/token", {
        "grant_type": "refresh_token", "client_id": d["app_id"],
        "client_secret": d["secret"], "refresh_token": d["refresh_token"]})
    if st != 200 or not r.get("access_token"):
        return False
    d.update({"access_token": r["access_token"],
              "refresh_token": r.get("refresh_token") or d["refresh_token"],
              "vence": time.time() + (r.get("expires_in") or 21600) - 120})
    _gravar(d)
    return True


def token():
    d = _ler()
    if not d.get("access_token"):
        return None
    if d.get("vence") and time.time() > d["vence"]:
        _renovar()
        d = _ler()
    return d.get("access_token")


def _quem():
    t = token()
    if not t:
        return False, "sem token"
    r = urllib.request.Request(API + "/users/me", headers={
        "Accept": "application/json", "Authorization": "Bearer " + t})
    try:
        with urllib.request.urlopen(r, timeout=20) as x:
            me = json.loads(x.read().decode("utf-8", "replace"))
        rep = me.get("seller_reputation") or {}
        d = _ler()
        d.update({"user_id": me.get("id"), "nick": me.get("nickname"),
                  "nome": (" ".join(x for x in (me.get("first_name"), me.get("last_name")) if x)).strip(),
                  "foto": (me.get("thumbnail") or {}).get("picture_url"),
                  "perfil": me.get("permalink"),
                  "nivel": rep.get("level_id"),            # 5_green, 4_light_green, ...
                  "medalha": rep.get("power_seller_status")})  # gold, platinum, silver
        _gravar(d)
        return True, me.get("nickname")
    except urllib.error.HTTPError as e:
        if e.code == 401 and _renovar():
            return _quem()
        return False, "HTTP %s" % e.code
    except Exception as e:
        return False, str(e)


def estado():
    d = _ler()
    tem_app = bool(d.get("app_id") and d.get("secret") and d.get("redirect"))
    ligado = bool(d.get("access_token"))
    nick = d.get("nick")
    aviso = None
    if ligado:
        ok, q = _quem()
        if ok:
            nick = q
        elif re.match(r"HTTP 4\d\d", q or ""):
            # o ML respondeu e recusou: token revogado, app apagado... e
            # desconexao de verdade
            ligado, nick = False, None
        else:
            # o ML nao respondeu (rede, timeout, 5xx): continua conectado com o
            # que esta salvo. Antes isto mandava o vendedor para a tela de
            # login sempre que a internet oscilava.
            aviso = "sem resposta do Mercado Livre agora (%s)" % q
    d = _ler()
    return {"tem_app": tem_app, "ligado": ligado, "nick": nick, "aviso": aviso,
            "app_id": d.get("app_id"), "redirect": d.get("redirect"),
            "user_id": d.get("user_id"), "nome": d.get("nome"),
            "foto": d.get("foto"), "perfil": d.get("perfil"),
            "nivel": d.get("nivel"), "medalha": d.get("medalha"),
            "url": url_autorizacao() if tem_app else None}


def desconectar(tudo=False):
    d = _ler()
    for k in ("access_token", "refresh_token", "vence", "nick", "user_id",
              "nome", "foto", "perfil", "nivel", "medalha"):
        d.pop(k, None)
    if tudo:
        d = {}
    _gravar(d)
    return estado()
