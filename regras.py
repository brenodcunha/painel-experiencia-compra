# -*- coding: utf-8 -*-
"""Regras do painel: constantes, classificacao e conferencia. Sem rede, sem estado.

FONTE UNICA. O coletor classifica cada anuncio com as funcoes daqui; a tela so
desenha o que veio no dados.json; e `checar()` confere o dados.json inteiro
depois de cada coleta (e antes de empacotar). Regra que falha vira aviso
vermelho na tela do vendedor — nada some em silencio.

A regra e a oficial do Mercado Livre (mercadolivre.com.br/ajuda/31968) e foi
conferida em duas contas contra o texto que o proprio ML escreve em cada
anuncio; os numeros estao em audit/passo0_medicoes.md e audit/placar.py.
"""
VERSAO = 5              # formato do dados.json; a tela recusa versao diferente (e coleta de novo sozinha)
PACOTE = "1.2"          # versao do pacote entregue aos vendedores (aparece na tela)
DATA_REGRAS = "17/09/2026"   # quando estas regras foram conferidas pela ultima vez
LIM_ITEM = 100          # vendas do ANUNCIO -> usa so ele
LIM_CAT = 200           # vendas da CATEGORIA no ano -> herda dela; abaixo, cinza
JANELA = 365            # janela padrao (o "ultimo ano" do fluxograma)
JANELA_RAPIDA = 60      # 100+ vendas em 60 dias -> o anuncio e julgado so por esses 60
JANELA_ANTIGA = 180     # anuncios que o ML ainda nao migrou para o calculo novo
PESO = 60               # dias em que a reclamacao do proprio anuncio pesa forte
NOTAS_VISTAS = (-1, 30, 50, 65, 75, 100)
CORES_VISTAS = (None, "gray", "red", "orange", "green")   # gray = cinza (medido)

# Os casos da coluna Situacao. A legenda e ESTA lista, sempre inteira, com a
# contagem ao lado — o painel fica identico em qualquer conta.
CASOS = (
    ("forte",   "perdendo exposição",                  "no ar, e a nota tira visita"),
    ("punido",  "sem estoque · volta punido ao repor", "parado; a punição volta quando repor"),
    ("semnota", "sem nota ainda",                      "a regra já daria nota, o ML não calculou — cinza não pune"),
    ("pausa",   "sem estoque · volta ok",              "parado, sem punição"),
    ("decola",  "Decola",                              "punição anulada enquanto o programa durar"),
    ("",        "ok",                                  "no ar, sem punição"),
)
_CLASSES = {c[0] for c in CASOS}


def punitiva(nota, cor):
    """Pune quem esta na faixa vermelha (Ruim) ou laranja (Media). O numero e detalhe."""
    return (cor in ("red", "orange")) or (nota in (30, 50, 65))


def base(v60, v365, vcat):
    """Fluxograma oficial -> (ramo, janela). ITEM = so o anuncio; HERDA = anuncio +
    categoria; SEM = cinza esperado."""
    if v60 >= LIM_ITEM:
        return "ITEM", JANELA_RAPIDA
    if v365 >= LIM_ITEM:
        return "ITEM", JANELA
    if vcat >= LIM_CAT:
        return "HERDA", JANELA
    return "SEM", 0


def situacao(freeze, pune, dormente, sem_nota, ativo):
    if freeze:
        return ["decola", "Decola"]
    if pune:
        return ["forte", "perdendo exposição"]
    if dormente:
        return ["punido", "sem estoque · volta punido ao repor"]
    if sem_nota:
        return ["semnota", "sem nota ainda"]
    if not ativo:
        return ["pausa", "sem estoque · volta ok"]
    return ["", "ok"]


def checar(d):
    """Confere um dados.json contra as regras. Devolve (falhas, notas): falha e
    bug; nota e coisa que o painel nao conhece e mostra como aviso."""
    falhas, notas = [], []
    it, cats = d.get("itens") or [], d.get("categorias") or []
    cat = {c["id"]: c for c in cats}
    if d.get("versao") != VERSAO:
        falhas.append("versao do dados.json = %s (esperado %s)" % (d.get("versao"), VERSAO))
        return falhas, notas
    if [list(c) for c in CASOS] != d.get("casos"):
        falhas.append("lista de casos da Situacao diferente da regra")
    conta = {"forte": 0, "punido": 0, "semnota": 0, "decola": 0}
    for i in it:
        c = cat.get(i["categoria"]) or {}
        vc = c.get("vendas365", 0)
        antigo = i.get("calculo") == "antigo"
        ramo, jan = ("ANTIGO", JANELA_ANTIGA) if antigo else base(i.get("v60", 0), i["v365"], vc)
        if (i["ramo"], i["janela"]) != (ramo, jan):
            falhas.append("%s ramo/janela %s/%s, esperado %s/%s" % (i["id"], i["ramo"], i["janela"], ramo, jan))
        esperado = {"ITEM": (i.get("v60", 0) if jan == JANELA_RAPIDA else i["v365"]),
                    "HERDA": vc, "ANTIGO": i.get("v180", 0), "SEM": 0}[ramo]
        if i["base_vendas"] != esperado:
            falhas.append("%s base_vendas %s, esperado %s" % (i["id"], i["base_vendas"], esperado))
        if ramo == "HERDA" and i["reclamacoes"] != c.get("reclamacoes"):
            falhas.append("%s HERDA com reclamacoes %s != categoria %s" % (i["id"], i["reclamacoes"], c.get("reclamacoes")))
        if ramo == "SEM" and i["taxa"] is not None:
            falhas.append("%s SEM com taxa" % i["id"])
        if i["base_vendas"] and abs((i["taxa"] or 0) - 100.0 * i["reclamacoes"] / i["base_vendas"]) > 1e-6:
            falhas.append("%s taxa nao bate" % i["id"])
        ruim = punitiva(i["nota"], i["cor"]) and not i["freeze"]
        ativo = i["status"] == "active"
        if bool(i["ruim"]) != ruim or i["pune"] != (ruim and ativo) or i["dormente"] != (ruim and not ativo):
            falhas.append("%s ruim/pune/dormente inconsistente (nota %s cor %s)" % (i["id"], i["nota"], i["cor"]))
        sem_nota = (not antigo) and ramo in ("ITEM", "HERDA") and i["nota"] in (None, -1)
        if bool(i["sem_nota"]) != sem_nota:
            falhas.append("%s sem_nota=%s, esperado %s" % (i["id"], i["sem_nota"], sem_nota))
        s = situacao(i["freeze"], i["pune"], i["dormente"], i["sem_nota"], ativo)
        if i.get("situacao") != s or s[0] not in _CLASSES:
            falhas.append("%s situacao %s, esperado %s" % (i["id"], i.get("situacao"), s))
        if s[0] in conta:
            conta[s[0]] += 1
        if i["nota"] is not None and i["nota"] not in NOTAS_VISTAS:
            notas.append("%s nota fora da escala: %s" % (i["id"], i["nota"]))
        if i["cor"] not in CORES_VISTAS:
            notas.append("%s cor desconhecida: %s" % (i["id"], i["cor"]))
        if i["nota"] not in (None, -1) and not (i.get("motivo") or []):
            notas.append("%s com nota e sem texto do ML" % i["id"])
        if i.get("idade") is None:      # sem idade a tela nao pode dizer "ha mais de um ano"
            notas.append("%s sem data de criacao" % i["id"])
        # cancelamentos feitos pelo VENDEDOR (o ML conta so esses): contadores sao inteiros e coerentes
        c365, c60 = i.get("cancelamentos", 0), i.get("cancelamentos60", 0)
        if not (isinstance(c365, int) and isinstance(c60, int) and 0 <= c60 <= c365):
            falhas.append("%s cancelamentos inconsistentes (%s / %s)" % (i["id"], c60, c365))
    # cards = soma dos chips, de verdade
    pune = sum(1 for i in it if i["pune"]); dorm = sum(1 for i in it if i["dormente"])
    if pune + dorm != conta["forte"] + conta["punido"]:
        falhas.append("card perdendo %d != chips preto+vinho %d" % (pune + dorm, conta["forte"] + conta["punido"]))
    if sum(1 for i in it if i["sem_nota"]) != conta["semnota"]:
        falhas.append("card sem nota != chips magenta")
    if sum(1 for i in it if i["freeze"]) != conta["decola"]:
        falhas.append("Decola != chips bronze")
    for c in cats:
        if c["vendas365"] and abs((c["taxa"] or 0) - 100.0 * c["reclamacoes"] / c["vendas365"]) > 1e-6:
            falhas.append("categoria %s taxa nao bate" % c["id"])
        if c["acima_limiar"] != (c["vendas365"] >= LIM_CAT):
            falhas.append("categoria %s acima_limiar errado" % c["id"])
        if c["n_anuncios"] != sum(1 for i in it if i["categoria"] == c["id"]):
            falhas.append("categoria %s n_anuncios errado" % c["id"])
        if not (isinstance(c.get("cancelamentos", 0), int) and c.get("cancelamentos", 0) >= 0):
            falhas.append("categoria %s cancelamentos invalido" % c["id"])
        for g in c.get("gemeas") or []:
            if g.get("permite") is False:
                falhas.append("categoria %s oferece gemea %s com listing_allowed=false" % (c["id"], g["id"]))
            if g["id"] == c["id"]:
                falhas.append("categoria %s oferece a si mesma" % c["id"])
            if bool(g.get("mesma_familia")) != bool(c.get("pai") and g.get("pai") == c.get("pai")):
                falhas.append("categoria %s gemea %s: mesma_familia inconsistente" % (c["id"], g["id"]))
    for r in d.get("reclamacoes") or []:
        if r["grupo"] != "PRODUTO":
            falhas.append("reclamacao %s na lista das que contam com grupo %s" % (r["id"], r["grupo"]))
        if r.get("pesa") != (r["dias"] <= PESO):
            falhas.append("reclamacao %s: pesa inconsistente" % r["id"])
    if d.get("total_conta") != len(d.get("reclamacoes") or []):
        falhas.append("total_conta != lista de reclamacoes")
    return falhas, notas


def reaplicar(d):
    """AUTO-CONSERTO. Recalcula tudo que deriva das regras a partir dos contadores
    crus que ja estao no dados.json (vendas por janela, reclamacoes, nota, cor,
    estoque, categoria). Se a classificacao veio velha ou inconsistente, aqui ela
    volta a ser a da regra — antes de qualquer card aparecer. Nao conserta o que
    nao esta nos dados (leitura incompleta, valor desconhecido): isso bloqueia."""
    if d.get("versao") != VERSAO:
        return False
    cats = {c["id"]: c for c in d.get("categorias") or []}
    for i in d.get("itens") or []:
        c = cats.get(i["categoria"]) or {}
        vc = c.get("vendas365", 0)
        antigo = i.get("calculo") == "antigo"
        if antigo:
            ramo, jan, recl, base_ = "ANTIGO", JANELA_ANTIGA, i.get("r180", 0), i.get("v180", 0)
        else:
            ramo, jan = base(i.get("v60", 0), i["v365"], vc)
            if ramo == "ITEM":
                recl, base_ = (i.get("r60", 0), i.get("v60", 0)) if jan == JANELA_RAPIDA else (i.get("r365", 0), i["v365"])
            elif ramo == "HERDA":
                recl, base_ = c.get("reclamacoes", 0), vc
            else:
                recl, base_ = 0, 0
        frz = bool(i.get("freeze"))
        ativo = i["status"] == "active"
        ruim = punitiva(i.get("nota"), i.get("cor")) and not frz
        sem_nota = (not antigo) and ramo in ("ITEM", "HERDA") and i.get("nota") in (None, -1)
        i.update(ramo=ramo, janela=jan, reclamacoes=recl, base_vendas=base_,
                 taxa=(100.0 * recl / base_) if base_ else None,
                 ruim=ruim, pune=ruim and ativo, dormente=ruim and not ativo, sem_nota=sem_nota,
                 situacao=situacao(frz, ruim and ativo, ruim and not ativo, sem_nota, ativo))
    for c in cats.values():
        meus = [i for i in d["itens"] if i["categoria"] == c["id"]]
        notas = {}
        for i in meus:
            k = "null" if i.get("nota") is None else str(i["nota"])
            notas[k] = notas.get(k, 0) + 1
        c.update(acima_limiar=c["vendas365"] >= LIM_CAT,
                 taxa=(100.0 * c["reclamacoes"] / c["vendas365"]) if c["vendas365"] else None,
                 n_anuncios=len(meus), notas=notas)
        for g in c.get("gemeas") or []:
            g["mesma_familia"] = bool(c.get("pai") and g.get("pai") == c.get("pai"))
    d["casos"] = [list(x) for x in CASOS]
    d["regras"] = dict(LIM_ITEM=LIM_ITEM, LIM_CAT=LIM_CAT, JANELA=JANELA,
                       JANELA_RAPIDA=JANELA_RAPIDA, JANELA_ANTIGA=JANELA_ANTIGA, PESO=PESO)
    for r in d.get("reclamacoes") or []:
        r["pesa"] = r["dias"] <= PESO
    return True


def veredito(d):
    """Fecha o veredito que a tela le: ok so se nenhuma regra falhou, nada e
    desconhecido e a leitura da API foi completa."""
    falhas, _ = checar(d)
    v = dict(d.get("conferencia") or {})
    v["falhas"] = falhas[:50]
    v.setdefault("desconhecidos", [])
    v.setdefault("leitura", [])
    v["ok"] = not falhas and not v["desconhecidos"] and not v["leitura"]
    d["conferencia"] = v
    return v
