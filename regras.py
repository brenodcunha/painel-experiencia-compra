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
VERSAO = 7              # formato do dados.json; a tela recusa versao diferente (e coleta de novo sozinha)
PACOTE = "1.7"          # versao do pacote entregue aos vendedores (aparece na tela)
DATA_REGRAS = "18/09/2026"   # quando estas regras foram conferidas pela ultima vez
LIM_ITEM = 100          # vendas do ANUNCIO -> usa so ele
LIM_CAT = 200           # vendas da CATEGORIA no ano -> herda dela; abaixo, cinza
JANELA = 365            # janela padrao (o "ultimo ano" do fluxograma)
JANELA_RAPIDA = 60      # 100+ vendas em 60 dias -> o anuncio e julgado so por esses 60
JANELA_ANTIGA = 180     # anuncios que o ML ainda nao migrou para o calculo novo
PESO = 60               # dias em que a reclamacao do proprio anuncio pesa forte
NOTAS_VISTAS = (-1, 30, 50, 65, 75, 100)
CORES_VISTAS = (None, "gray", "red", "orange", "green")   # gray = cinza (medido)

# DESFECHO da reclamacao (`resolution.benefited` da API, que a busca ja traz): quem ficou
# com o dinheiro. Medido em 18/09/2026 em 4 contas (audit/passo0_medicoes.md): so a que o
# COMPRADOR ganhou pesa na Experiencia de Compra. Quando o vendedor esta entre os
# beneficiados — ele ganhou (`no_bpp`) ou o ML cobriu do proprio bolso (`coverage_decision`,
# `warehouse_decision`) — a nota se comporta como se ela nao existisse: 19 anuncios so com
# essas (e que venderam depois), todos em 100; pares na mesma categoria com o mesmo numero
# de reclamacoes do comprador e uma dessas a mais: 6 piores x 5 melhores em 207 (vendedor
# ganhou), 0 x 2 em 61 (ML cobriu) — contra 172 piores x 8 quando a "a mais" e do comprador.
# Ela continua na lista (o vendedor ve que existiu), com selo, fora de todos os contadores.
DESFECHOS = ("comprador", "vendedor", "ml_cobriu", "sem_beneficiado", "aberta")
NAO_PESA = ("vendedor", "ml_cobriu")


def desfecho(status, beneficiados):
    """`status` + `resolution.benefited` da API -> um de DESFECHOS."""
    if status != "closed":
        return "aberta"
    b = set(beneficiados or ())
    if "respondent" in b:
        return "ml_cobriu" if "complainant" in b else "vendedor"
    if "complainant" in b:
        return "comprador"
    return "sem_beneficiado"


def conta_desfecho(d):
    """A reclamacao de PRODUTO entra na conta? Nao se o vendedor ganhou ou o ML cobriu."""
    return d not in NAO_PESA

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

# OS TEXTOS FIXOS DA TELA. A tela nao escreve nenhum destes na mao: le daqui (via
# dados.json / api/conta). Mudou uma palavra, mudou aqui — e no REGRAS.md 5, que o
# empacotador confere letra por letra (audit/verificar_textos.py).
ROTULOS = {
    "btn_atualizar": "Atualizar os anúncios da conta",
    "btn_guia": "Como criar seu aplicativo no DevCenter",
    "btn_sair": "Desconectar esta conta",
    "card_perdendo": "Perdendo exposição",
    "card_semnota": "Sem nota ainda",
    "card_taxa": "Taxa geral",
    "card_categorias": "Categorias afetadas",
    "leg_taxa": "Taxa", "leg_nota": "Nota", "leg_situacao": "Situação",
    "col_anuncio": "Anúncio", "col_nota": "Nota", "col_base": "Base",
    "col_vendas": "Vendas 365d", "col_60": "60d",
    "col_recl": "Reclam. na base", "col_taxa": "Taxa da base", "col_situacao": "Situação",
    "base_anuncio": "o anúncio", "base_categoria": "a categoria",
    "base_antigo": "cálculo antigo", "base_nenhuma": "nenhuma",
    "det_conta": "A conta", "det_cai": "Como cai sozinha",
    "det_porque": "Por que essa nota", "det_recomenda": "O ML recomenda",
    "det_reclamacoes": "Reclamações",
    "det_reclamacoes_base": "reclamações na base",
    "det_reclamacoes_anuncio": "reclamações deste anúncio no ano",
    "selo_favor": "fechada a seu favor · não conta",
    "selo_ml_cobriu": "o Mercado Livre cobriu · não conta",
    "lnk_ml": "Abrir no Mercado Livre ↗", "lnk_venda": "abrir a venda ↗",
    "cat_col_categoria": "Categoria", "cat_col_vendas": "Vendas 365d", "cat_col_recl": "Reclam.",
    "cat_col_taxa": "Taxa", "cat_col_anuncios": "Anúncios",
    "cat_col_notas": "Notas que está dando", "cat_col_mover": "Para onde dá para mover",
    "selo_zerado": "contador zerado", "selo_baixo": "contador baixo", "selo_boa": "nota boa comprovada",
    "tag_da_nota": "dá a nota", "tag_abaixo": "abaixo de",
    "tag_espelho_de": "espelho de", "tag_tem_espelho": "tem espelho",
    "tag_espelho_desta": "espelho desta", "tag_mestre_desta": "a mestre desta",
    "vazio_cat": "Nenhuma categoria sua está punindo",
    "vazio_filtro": "Nada encontrado com esse filtro.",
    "vazio_conta": "Esta conta não tem nenhum anúncio.",
    "vazio_dados": "Sem dados ainda.",
    "bloqueio_titulo": "O painel não passou na própria conferência",
    "btn_denovo": "Coletar de novo",
    "con_titulo": "Conecte a sua conta do Mercado Livre",
    "con_p1": "Cole os dados do seu aplicativo",
    "con_p2": "Autorize e copie o código",
    "btn_salvar": "Salvar e gerar o link",
    "btn_conectar": "Conectar",
}


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
    if d.get("rotulos") != ROTULOS:
        falhas.append("rotulos da tela diferentes da regra")
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
    por_item = {}
    lst = d.get("reclamacoes") or []
    for r in lst:
        if r["grupo"] != "PRODUTO":
            falhas.append("reclamacao %s na lista de produto com grupo %s" % (r["id"], r["grupo"]))
        if r.get("desfecho") not in DESFECHOS:
            falhas.append("reclamacao %s: desfecho desconhecido %s" % (r["id"], r.get("desfecho")))
        elif r.get("conta") != conta_desfecho(r["desfecho"]):
            falhas.append("reclamacao %s: conta=%s com desfecho %s" % (r["id"], r.get("conta"), r["desfecho"]))
        if r.get("pesa") != bool(r.get("conta") and r["dias"] <= PESO):
            falhas.append("reclamacao %s: pesa inconsistente" % r["id"])
        if r.get("item"):
            por_item.setdefault(r["item"], []).append(r)
    if d.get("total_conta") != sum(1 for r in lst if r.get("conta")):
        falhas.append("total_conta != reclamacoes que contam na lista")
    if d.get("total_nao_conta") != sum(1 for r in lst if not r.get("conta")):
        falhas.append("total_nao_conta != reclamacoes fora da conta na lista")
    # a lista tem TODAS as de produto; nos contadores do anuncio so pode haver as que CONTAM
    for i in it:
        rs = por_item.get(i["id"])
        if not rs:
            continue
        c365 = sum(1 for r in rs if r.get("conta"))
        c60 = sum(1 for r in rs if r.get("conta") and r["dias"] <= JANELA_RAPIDA)
        if i.get("r365") != c365 or i.get("r60") != c60:
            falhas.append("%s r365/r60 = %s/%s, a lista tem %d/%d que contam" % (i["id"], i.get("r365"), i.get("r60"), c365, c60))
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
    d["rotulos"] = dict(ROTULOS)
    d["regras"] = dict(LIM_ITEM=LIM_ITEM, LIM_CAT=LIM_CAT, JANELA=JANELA,
                       JANELA_RAPIDA=JANELA_RAPIDA, JANELA_ANTIGA=JANELA_ANTIGA, PESO=PESO)
    lst = d.get("reclamacoes") or []
    for r in lst:
        if r.get("desfecho") in DESFECHOS:
            r["conta"] = conta_desfecho(r["desfecho"])
        r["pesa"] = bool(r.get("conta") and r["dias"] <= PESO)
    d["total_conta"] = sum(1 for r in lst if r.get("conta"))
    d["total_nao_conta"] = sum(1 for r in lst if not r.get("conta"))
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
