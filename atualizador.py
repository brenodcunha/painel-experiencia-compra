# -*- coding: utf-8 -*-
"""Atualizacao automatica do painel a partir do repositorio publico.

O que faz: compara o `PACOTE` do regras.py desta pasta com o do repositorio (um GET no
arquivo cru). Se o repositorio esta na frente, baixa o zip do ramo, CONFERE antes de tocar
em qualquer coisa (a versao e a esperada, os arquivos da lista fechada do empacotar.py
estao la, todo .py compila, nenhum caminho proibido) e so entao troca os arquivos — um
por um, atomico, SO os da lista LEVA (+ as fixtures). conta.json, dados.json, backups e
logs NUNCA sao tocados: a lista os recusa mesmo que o zip os traga.

Quem chama: ligar.py (antes de subir o servidor) e o servidor (confere a cada 6 h; a tela
pede a troca em /api/atualizar_painel). Depois da troca o servidor se reinicia sozinho
(ligar.py --reiniciar).

Confianca: quem controla o repositorio controla o que roda nos paineis — proteja a conta
(2FA). So HTTPS, so o repositorio fixado em REPO. Sem internet: silencio, o painel segue
como esta. Nada disto fala com o Mercado Livre.
"""
import ast, io, os, re, time, zipfile, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = "https://github.com/brenodcunha/painel-experiencia-compra"   # o repositorio publico do painel
RAMO = "main"
TIMEOUT = 8                 # segundos por pedido; sem internet, desiste rapido e cala
INTERVALO = 6 * 3600        # o servidor confere no maximo a cada 6 h
_cache = {"quando": 0.0, "resp": None}
# o que a troca NUNCA escreve, venha o que vier no zip
_PROIBIDO = re.compile(r"(^|/)(conta\.json|dados\.json|dados_[^/]*\.json|.*\.bak|.*\.log|.*\.tmp|__pycache__)(/|$)")


def _origem():
    """(url do regras.py cru, url do zip do ramo) — ou (None, None) se nao esta configurado."""
    t = os.environ.get("PAINEL_ORIGEM")          # so para teste local: uma pasta servida por http
    if t:
        return t.rstrip("/") + "/regras.py", t.rstrip("/") + "/arquivo.zip"
    m = re.match(r"https://github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", REPO)
    if not m or "USUARIO" in REPO:
        return None, None
    u, r = m.groups()
    return ("https://raw.githubusercontent.com/%s/%s/%s/regras.py" % (u, r, RAMO),
            "https://codeload.github.com/%s/%s/zip/refs/heads/%s" % (u, r, RAMO))


def configurado():
    return _origem()[0] is not None


def _versao(txt):
    m = re.search(r'^PACOTE\s*=\s*"([0-9]+(?:\.[0-9]+)*)"', txt, re.M)
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def _txt(v):
    return ".".join(map(str, v)) if v else None


def _local():
    return _versao(io.open(os.path.join(BASE, "regras.py"), encoding="utf-8").read())


def _get(url):
    r = urllib.request.Request(url, headers={"User-Agent": "painel-experiencia", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(r, timeout=TIMEOUT) as x:
        return x.read()


def _vazio():
    return {"disponivel": False, "atual": _txt(_local()), "versao": None, "erro": None, "configurado": configurado()}


def ultimo():
    """O que a ultima conferencia achou, SEM ir a rede (para /api/conta nunca esperar)."""
    return _cache["resp"] or _vazio()


def verificar(forcar=False):
    """Confere o repositorio. Devolve {disponivel, atual, versao, erro, configurado}. Nunca levanta."""
    agora = time.time()
    if not forcar and _cache["resp"] and agora - _cache["quando"] < INTERVALO:
        return _cache["resp"]
    resp = _vazio()
    url, _ = _origem()
    if url:
        try:
            remota = _versao(_get(url).decode("utf-8", "replace"))
            local = _local()
            resp["versao"] = _txt(remota)
            if remota and local and remota > local:
                resp["disponivel"] = True
            elif not remota:
                resp["erro"] = "o regras.py do repositorio nao tem PACOTE"
        except Exception as e:
            resp["erro"] = str(e)[:120]
    _cache.update(quando=agora, resp=resp)
    return resp


def _leva(txt_empacotar):
    """Le a lista LEVA do empacotar.py que veio no zip SEM executar nada (so a arvore sintatica)."""
    try:
        arvore = ast.parse(txt_empacotar)
    except SyntaxError:
        return []
    for n in ast.walk(arvore):
        if (isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "LEVA" for t in n.targets)
                and isinstance(n.value, ast.List)):
            return [x.value for x in n.value.elts if isinstance(x, ast.Constant) and isinstance(x.value, str)]
    return []


def atualizar():
    """Baixa, confere e troca. Devolve (ok, mensagem). Se qualquer conferencia falha, nao toca em nada."""
    url, zurl = _origem()
    if not url:
        return False, "repositorio nao configurado (atualizador.REPO)"
    v = verificar(forcar=True)
    if not v["disponivel"]:
        return False, v["erro"] or "ja esta na versao mais nova (%s)" % v["atual"]
    try:
        z = zipfile.ZipFile(io.BytesIO(_get(zurl)))
    except Exception as e:
        return False, "nao consegui baixar o zip: %s" % str(e)[:120]
    nomes = [n for n in z.namelist() if not n.endswith("/")]
    # o zip do GitHub vem com uma pasta no topo (repositorio-ramo/): tira
    tops = {n.split("/", 1)[0] for n in nomes}
    raiz = (tops.pop() + "/") if len(tops) == 1 and all("/" in n for n in nomes) else ""

    def le(rel):
        try:
            return z.read(raiz + rel)
        except KeyError:
            return None
    emp = le("empacotar.py")
    leva = _leva(emp.decode("utf-8", "replace")) if emp else []
    if not leva:
        from empacotar import LEVA as leva            # a lista local, se a do zip nao der para ler
    leva = list(dict.fromkeys(list(leva) + [n[len(raiz):] for n in nomes
                                             if n.startswith(raiz + "audit/fixtures/") and n.endswith(".json")]))
    # ---- conferencias, ANTES de tocar em qualquer arquivo ----
    novo = le("regras.py")
    if novo is None or _txt(_versao(novo.decode("utf-8", "replace"))) != v["versao"]:
        return False, "o zip nao traz a versao %s" % v["versao"]
    for a in leva:
        if a.startswith(("/", "\\")) or ".." in a.replace("\\", "/").split("/") or _PROIBIDO.search(a):
            return False, "o zip tenta trocar um arquivo proibido: %s" % a
    faltam = [a for a in leva if le(a) is None and not a.startswith("audit/fixtures/")]
    if faltam:
        return False, "faltam arquivos no zip: %s" % ", ".join(faltam[:5])
    for a in leva:
        corpo = le(a)
        if a.endswith(".py") and corpo is not None:
            try:
                compile(corpo, a, "exec")
            except SyntaxError as e:
                return False, "%s do zip nao compila: %s" % (a, e)
    # ---- troca: um por um, atomico ----
    for a in leva:
        corpo = le(a)
        if corpo is None:
            continue
        alvo = os.path.join(BASE, *a.split("/"))
        os.makedirs(os.path.dirname(alvo), exist_ok=True)
        tmp = alvo + ".tmp"
        with open(tmp, "wb") as f:
            f.write(corpo)
        os.replace(tmp, alvo)
    _cache["resp"] = None
    return True, "painel atualizado de %s para %s" % (v["atual"], v["versao"])
