# -*- coding: utf-8 -*-
"""Coletor da Experiencia de Compra do Mercado Livre.

A REGRA e a oficial, publicada pelo ML em mercadolivre.com.br/ajuda/31968
("novo calculo"), conferida em duas contas (1.370 anuncios) em 16/09/2026:

    anuncio com 100+ vendas em 60 dias   -> so o anuncio, janela de 60 dias
    senao, anuncio com 100+ no ano       -> so o anuncio, janela de 365 dias
    senao, categoria com 200+ no ano     -> anuncio + categoria (herda)
    senao                                -> sem experiencia (cinza)

    nota = voce comparado aos OUTROS VENDEDORES da categoria:
           Mediana (50-74) = 2x abaixo da media deles; Ruim (<=30) = 3x abaixo.
    A media dos concorrentes NAO existe em nenhuma rota da API (11 testadas).
    Logo este coletor calcula a SUA taxa e le a nota que o ML publicou; nao preve.

Medido contra o texto que o proprio ML escreve em cada anuncio (audit/placar.py):
    base anuncio/categoria x texto do ML     89% e 100% nas duas contas
    cinza pela regra 100/200                 88% e 93%
    reclamacao PROPRIA derruba so o anuncio  98% dos pares na mesma categoria
    reclamacao pesa forte por ~60 dias       35% em 100 com reclamacao recente x 95% sem
O que sobra de diferenca e nota PARADA: o ML so recalcula quando o anuncio vende.

CALCULO ANTIGO: o ML avisa que "em alguns anuncios ainda nao aplicamos o novo
calculo". Esses vem em OUTRA forma na API (sem `reasoning`, com `subtitles` e
`metrics_details`) e dizem "nos ultimos 180 dias". O coletor marca
`calculo = "antigo"` e conta 180 dias para eles.

A "categoria" que o ML agrupa parece ser a FAMILIA (o pai da categoria do
anuncio): a regra do cinza acerta mais por pai (91%/95%) que por folha
(88%/93%), e a ordenacao das notas pela taxa nao inverte nenhum par por pai.
Por isso a gemea da mesma familia NAO e oferecida como destino.

QUE RECLAMACAO CONTA  (auditado em 14/09/2026, 753 reclamacoes)
--------------------
REGRA ESTRUTURAL, sem lista de nomes:

    conta = reason.flow termina em "_delivered"   (o produto chegou)
            E reason.name != "repentant_buyer"    (nao e arrependimento)

Ou seja: so problema com o PRODUTO ENTREGUE. Nao conta entrega, atraso,
cancelamento nem desistencia. Se o ML criar um motivo novo, a regra segue
valendo — por isso ela olha `flow`, nao uma lista chumbada.

MEDIDO — anuncios cujas reclamacoes sao SO de um flow, e a nota que tem:
    post_purchase_delivered    58 anuncios -> 29% punidos
    mediations_undelivered     13 anuncios ->  0%
    cancel_sale                 8 anuncios ->  0%
    fulfillment_undelivered     1 anuncio  ->  0%
    (nenhuma reclamacao)      133 anuncios ->  0%
    so repentant_buyer         24 anuncios ->  4%

TESTE LIMPO — anuncios com nota 75 ou 100, ja recalculados:
    zero reclamacao de produto           188 em 100,  1 em 75  ->  1% punido
    zero de produto mas tem outras        55 em 100,  1 em 75  ->  2% punido
    1+ reclamacao de produto              45 em 100, 25 em 75  -> 36% punido
Quem so tem reclamacao de entrega/arrependimento se comporta igual a quem
nao tem reclamacao nenhuma.

AUC (chance de um anuncio em 75 ter mais reclamacoes que um em 100 da mesma
categoria; 0,50 = filtro inutil):
    taxa de reclamacao de PRODUTO      0,889   <-- usado
    contagem de PRODUTO                0,867
    todas as reclamacoes               0,851
    so os 4 motivos da reputacao       0,648
Controlando pelo numero de reclamacoes de produto, "nao entregue" cai para
0,408 — nao acrescenta sinal nenhum.

⚠️ NAO use o campo `detail` para classificar: ele e a PRIMEIRA resposta do
comprador, nao o motivo. `not_working_item`, `broken_item`, `missing_item` e
`empty_box` todos tem detail "Chegou bem". Use `name` e `flow`.

⚠️ `/claims/{id}/affects-reputation` e OUTRA METRICA — a reputacao do vendedor
(Mercado Lider), nao a experiencia de compra:
    reputacao: janela 60d, so type=mediations + stage=dispute + resource=order,
               e so 4 motivos (broken_item, different_than_published,
               different_color_or_size, different_item_other). Bate exatamente
               com /users/me -> seller_reputation.metrics.claims.value
    experiencia: janela 365d, conta `not_working_item` (dezenas no funil da
               reputacao, ZERO afetam ela) — e justamente o motivo que domina
               a categoria com as piores notas de experiencia da conta de
               referencia.

VALIDACAO (14/09/2026, conta de referencia; refeita em 4 contas em 16/09/2026)
----------------------
Ramo ITEM: as taxas de 365d ordenam as notas (as duas maiores -> 65 e 30, as
quatro menores -> 75). Ramo HERDA: a categoria de maior taxa da conta da as
piores notas (30), a de menor taxa da 100. O ramo calculado bate com o que o
proprio ML escreve no campo `reasoning` nas celulas em que esse texto e
consistente (ver audit/placar.py e REGRAS.md 1.1).

VENDAS = PEDIDOS, nao unidades. Cancelados contam. Vendas de anuncio ja
encerrado tambem contam pra categoria. Decidido reconstruindo o volume
historico e comparando com a nota publicada: pedidos 95,5% x unidades 92,3%,
e no confronto direto 6 x 1.
"""
import datetime as dt, json, os, re, sys, time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from ml import g, ensure_auth
import regras
from regras import VERSAO, LIM_ITEM, LIM_CAT, JANELA, JANELA_RAPIDA, JANELA_ANTIGA, PESO

CACHE = os.path.join(BASE, "dados.json")
ARREPENDIMENTO = "repentant_buyer"   # chegou bem, mas nao quero mais


def _grupo(nome, flow):
    """Classifica a reclamacao. So PRODUTO entra na conta da experiencia."""
    if not (flow or "").endswith("_delivered"):
        return "ENTREGA"          # nao chegou, atrasou, foi cancelado
    if nome == ARREPENDIMENTO:
        return "ARREPENDIMENTO"   # chegou bem, o comprador desistiu
    return "PRODUTO"              # chegou e tem problema — este pune
HOJE = dt.date.today()      # reatribuido no inicio de cada coleta


def _dias(s):
    return (HOJE - dt.date(*map(int, s[:10].split("-")))).days


TETO_API = 9950             # /orders/search recusa offset >= 10.000


def _iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%S.000-03:00")


def _janelas(uid, ini, fim, avisos):
    """Divide [ini, fim] em janelas que a API entrega inteiras (< 10.000 pedidos).

    /orders/search recusa offset >= 10.000. Um vendedor grande passa disso num
    ano — e antes o coletor cortava em 9.950 em silencio, subestimando as
    vendas de todas as categorias e errando o ramo de cada anuncio. Como a
    rota aceita `order.date_created.to`, a saida e fatiar por data: cada
    janela que ainda passa do teto e partida ao meio, ate caber.
    """
    base = "/orders/search?seller=%s&order.date_created.from=%s&order.date_created.to=%s&limit=1"
    st, r = g(base % (uid, _iso(ini), _iso(fim)))
    if st != 200:
        avisos.append("pedidos: a API nao respondeu para %s a %s (HTTP %s)" % (ini.date(), fim.date(), st))
        return []
    tot = (r.get("paging") or {}).get("total") or 0
    if tot <= TETO_API or (fim - ini) < dt.timedelta(hours=6):
        if tot > TETO_API:
            avisos.append("pedidos: %d em menos de 6h em %s — a API so entrega %d" % (tot, ini.date(), TETO_API))
        return [(ini, fim, min(tot, TETO_API))] if tot else []
    meio = ini + (fim - ini) / 2
    return _janelas(uid, ini, meio, avisos) + _janelas(uid, meio + dt.timedelta(seconds=1), fim, avisos)


def _pedidos(uid, prog, avisos):
    """Baixa 365 dias de pedidos, em PARALELO. Devolve {id_pedido: {...}}.

    Cada pedido guarda TODOS os seus itens: `itens` = [(item_id, categoria)].
    Um pedido com dois anuncios diferentes e uma venda para cada um — so o
    primeiro item era contado antes. Unidades continuam nao contando (a regra
    medida e VENDAS = PEDIDOS).
    """
    agora = dt.datetime.now()
    jans = _janelas(uid, agora - dt.timedelta(days=JANELA), agora, avisos)
    tot = sum(t for _, _, t in jans)
    if not tot:
        return {}
    base = "/orders/search?seller=%s&order.date_created.from=%s&order.date_created.to=%s&sort=date_desc&limit=50&offset=%d"
    tarefas = [(ini, fim, off) for ini, fim, t in jans for off in range(0, t, 50)]
    prog("pedidos: 0/%d" % tot)
    feito = [0]

    def pega(t):
        ini, fim, off = t
        st, r = g(base % (uid, _iso(ini), _iso(fim), off))
        if st != 200:
            avisos.append("pedidos: pagina %d de %s falhou (HTTP %s)" % (off, ini.date(), st))
            return []
        feito[0] += 1
        if feito[0] % 30 == 0:
            prog("pedidos: %d/%d" % (min(feito[0] * 50, tot), tot))
        return r.get("results") or []

    ords = {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        for res in ex.map(pega, tarefas):
            for o in res:
                itens, vistos = [], set()
                for oi in (o.get("order_items") or []):
                    it = oi.get("item") or {}
                    if it.get("id") and it["id"] not in vistos:
                        vistos.add(it["id"])
                        itens.append((it["id"], it.get("category_id")))
                prim = itens[0] if itens else (None, None)
                ords[str(o["id"])] = {"i": prim[0], "c": prim[1], "itens": itens,
                                      "d": o["date_created"][:10], "s": o.get("status"),
                                      "sh": str((o.get("shipping") or {}).get("id") or "")}
    return ords


def _reclamacoes(uid, ords, prog, avisos):
    """Baixa as reclamacoes de 365d e liga cada uma ao pedido/anuncio."""
    base = ("/post-purchase/v1/claims/search?players.user_id=%s&players.role=respondent"
            "&status=%s&sort=date_desc&limit=50&offset=%d")
    tarefas = []
    for stt in ("opened", "closed"):
        st, r = g(base % (uid, stt, 0))
        if st != 200:
            avisos.append("reclamacoes %s: a API nao respondeu (HTTP %s)" % (stt, st))
            continue
        # a API aceita offset alem de 4.000 (testado); o teto aqui e so um
        # freio de seguranca, e se bater ele avisa em vez de calar
        tot = (r.get("paging") or {}).get("total") or 0
        if tot > 20000:
            avisos.append("reclamacoes %s: %d, lendo so 20.000" % (stt, tot))
            tot = 20000
        tarefas += [(stt, o) for o in range(0, tot, 50)]

    def pega(t):
        stt, off = t
        st, r = g(base % (uid, stt, off))
        if st != 200:
            avisos.append("reclamacoes %s: pagina %d falhou (HTTP %s)" % (stt, off, st))
            return []
        return r.get("data") or []
    cl = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for d in ex.map(pega, tarefas):
            for c in d:
                cl[c["id"]] = c
    prog("ligando %d reclamacoes aos anuncios..." % len(cl))

    # a maioria resolve de graca: claim.resource_id ja e o pedido, ou e o envio
    por_envio = {v["sh"]: k for k, v in ords.items() if v["sh"]}
    falta = []
    for c in cl.values():
        rid = str(c.get("resource_id"))
        c["_ped"] = rid if (c.get("resource") == "order" and rid in ords) else por_envio.get(rid)
        if not c["_ped"]:
            falta.append(c)

    def _envio(c):
        st, s = g("/shipments/%s" % c.get("resource_id"))
        return c["id"], (str(s.get("order_id")) if st == 200 else None)
    if falta:
        with ThreadPoolExecutor(max_workers=6) as ex:
            for cid, p in ex.map(_envio, falta):
                if p:
                    cl[cid]["_ped"] = p

    # catalogo de motivos: `name` classifica, `detail` NAO
    codes = sorted({c.get("reason_id") for c in cl.values() if c.get("reason_id")})

    def _motivo(k):
        st, r = g("/post-purchase/v1/claims/reasons/%s" % k)
        return k, (r if st == 200 else {})
    RZ = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for k, r in ex.map(_motivo, codes):
            RZ[k] = r
    for c in cl.values():
        r = RZ.get(c.get("reason_id")) or {}
        c["_nome"] = r.get("name") or ""
        c["_txt"] = r.get("detail") or c.get("reason_id") or ""
        c["_flow"] = r.get("flow") or ""
        c["_grupo"] = _grupo(c["_nome"], c["_flow"])
        c["_conta"] = c["_grupo"] == "PRODUTO"
    return cl, RZ


def coleta(prog=lambda s: None):
    t0 = time.time()
    marcos = []

    def _marco(nome):
        marcos.append((nome, time.time() - t0))
        prog("%s (%.0fs)" % (nome, time.time() - t0))

    global HOJE
    HOJE = dt.date.today()
    avisos = []
    if not ensure_auth():
        raise RuntimeError("a conta nao esta conectada ou o token venceu — reconecte")
    st, me = g("/users/me")
    if st != 200 or not me.get("id"):
        raise RuntimeError("nao consegui ler a conta no Mercado Livre (HTTP %s)" % st)
    uid, nick = me["id"], me.get("nickname")

    prog("listando anuncios...")
    # ⚠️ /users/{id}/items/search recusa offset >= 1.000 (HTTP 400, medido).
    # Conta com mais de mil anuncios ficava pela metade, em silencio. O modo
    # `search_type=scan` devolve um scroll_id e percorre tudo.
    ids, scroll = [], None
    while True:
        q = "/users/%s/items/search?search_type=scan&limit=100" % uid
        if scroll:
            q += "&scroll_id=" + scroll
        st, r = g(q)
        if st != 200:
            if not ids:                        # scan indisponivel: cai no modo comum
                off = 0
                while True:
                    st, r = g("/users/%s/items/search?limit=100&offset=%d" % (uid, off))
                    if st != 200:
                        break
                    res = r.get("results") or []
                    ids += res
                    off += 100
                    if off >= (r.get("paging", {}).get("total") or 0) or not res or off >= 1000:
                        break
                if off >= 1000:
                    avisos.append("anuncios: a listagem parou em 1.000 (limite da API sem scan)")
            break
        res = r.get("results") or []
        if not res:
            break
        ids += res
        scroll = r.get("scroll_id") or scroll
        if not r.get("scroll_id"):
            break
    ids = list(dict.fromkeys(ids))            # dedup preservando ordem
    def _lote(k):
        st, r = g("/items?ids=%s&attributes=id,title,category_id,status,sub_status,"
                  "sold_quantity,available_quantity,price,thumbnail,permalink,date_created"
                  % ",".join(ids[k:k + 20]))
        return [e["body"] for e in (r if isinstance(r, list) else []) if e.get("code") == 200]
    meta = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for corpos in ex.map(_lote, range(0, len(ids), 20)):
            for b in corpos:
                meta[b["id"]] = b
    prog("anuncios: %d" % len(meta))

    _marco("anuncios prontos")

    def nota(i):
        st, r = g("/reputation/items/%s/purchase_experience/integrators?locale=pt_BR" % i)
        if st != 200:
            return i, None
        rep = r.get("reputation") or {}

        def sub(bl):
            return [x.get("text", "") for x in ((r.get(bl) or {}).get("subtitles") or [])]
        # DUAS formas de resposta (medido em 16/09/2026): "prosa" traz `reasoning`
        # (texto gerado por IA — calculo novo); "template" nao traz `reasoning`,
        # escreve no topo com placeholders {0}<b>{1} e diz "nos ultimos 180 dias"
        # (calculo antigo, que o ML ainda aplica em alguns anuncios). Uma terceira
        # forma, que o painel nao conhece, vira aviso — nunca silencio.
        forma = "prosa" if "reasoning" in r else ("template" if "subtitles" in r else "outra")
        motivo = sub("reasoning")
        if not motivo:
            motivo = [re.sub(r"\{\d+\}", "", x.get("text") or "")
                      for x in (r.get("subtitles") or []) if x.get("text")]
        # ⚠️ `value` volta int quase sempre, mas em alguns anuncios vem string.
        v = rep.get("value")
        if isinstance(v, str):
            try:
                v = int(v)
            except ValueError:
                v = None
        # Programa Decola: a nota continua ruim, mas a PUNICAO e anulada.
        # ⚠️ os contadores deste loop NAO podem se chamar `v`: os placeholders
        # do freeze sao ["<b>", "</b>"], e a variavel da nota era sobrescrita.
        frz_txt = (r.get("freeze") or {}).get("text") or ""
        for idx, ph in enumerate((r.get("freeze") or {}).get("placeholders") or []):
            frz_txt = frz_txt.replace("{%d}" % idx, ph)
        frz = bool(frz_txt)
        cor = rep.get("color")
        estranho = []
        if forma == "outra":
            estranho.append("resposta em formato desconhecido")
        if v is not None and v not in regras.NOTAS_VISTAS:
            estranho.append("nota fora da escala (%s)" % v)
        if cor not in regras.CORES_VISTAS:
            estranho.append("cor desconhecida (%s)" % cor)
        # os numeros que o ML escreve na forma template ("fez N vendas e teve N problemas")
        ml = None
        if forma == "template":
            md = r.get("metrics_details") or {}
            dist = md.get("distribution") or {}
            probs = md.get("problems") or []
            txt = " ".join(motivo)
            mv = re.search(r"fez (\d+) venda", txt)
            mp = re.search(r"teve (\d+) problema", txt)
            ml = {"vendas": int(mv.group(1)) if mv else None,
                  "problemas": int(mp.group(1)) if mp else None,
                  "reclamacoes": sum(p.get("claims") or 0 for p in probs) if probs else None,
                  "cancelamentos": sum(p.get("cancellations") or 0 for p in probs) if probs else None,
                  "de": (dist.get("from") or "")[:10], "ate": (dist.get("to") or "")[:10]}
        return i, {"valor": v, "cor": cor, "texto": rep.get("text"),
                   "ruim": regras.punitiva(v, cor) and not frz, "freeze": frz, "freeze_txt": frz_txt,
                   # `consequence` so vem preenchido em anuncio ATIVO — nao e sinal de punicao
                   "consequencia": ((r.get("consequence") or {}).get("title") or {}).get("text") or "",
                   "up_id": r.get("up_id"),
                   "motivo": motivo,                       # o ML explica a nota
                   "recomendacoes": sub("recommendations"),  # gerado por IA, do produto
                   "acao": ((r.get("principal_actionable") or {}).get("text") or ""),
                   "entra": sub(""),
                   "forma": forma, "calculo": "antigo" if forma == "template" else "novo",
                   "ml": ml, "estranho": estranho,
                   # a frase abaixo denuncia que o ML usou a CATEGORIA
                   "ml_herda": any("informações suficientes" in t for t in motivo)}
    notas, entra = {}, []
    with ThreadPoolExecutor(max_workers=12) as ex:
        for i, n in ex.map(nota, list(meta)):
            notas[i] = n
            if n and n["entra"] and not entra:
                entra = n["entra"]

    prog("lendo pedidos...")
    ords = _pedidos(uid, prog, avisos)
    prog("lendo reclamacoes...")
    cl, _ = _reclamacoes(uid, ords, prog, avisos)

    # --- contagem ---
    vivos = set(meta)
    v60i, v180i, v365i = Counter(), Counter(), Counter()   # vendas por anuncio
    v60c, v180c, v365c = Counter(), Counter(), Counter()   # por categoria (inclui encerrados)
    ultima = {}                                            # ultima venda de cada anuncio
    for o in ords.values():
        d = _dias(o["d"])
        cats_do_pedido = set()
        for iid, icat in (o.get("itens") or [(o["i"], o["c"])]):
            if iid in vivos:
                v365i[iid] += 1
                if d <= 60:
                    v60i[iid] += 1
                if d <= JANELA_ANTIGA:
                    v180i[iid] += 1
                if o["d"] > ultima.get(iid, ""):
                    ultima[iid] = o["d"]
            cat = (meta.get(iid) or {}).get("category_id") or icat
            if cat:
                cats_do_pedido.add(cat)
        for cat in cats_do_pedido:           # um pedido = uma venda por categoria
            v365c[cat] += 1
            if d <= 60:
                v60c[cat] += 1
            if d <= JANELA_ANTIGA:
                v180c[cat] += 1

    # reclamacoes que CONTAM, nas tres janelas (60 = atalho do fluxograma, 180 =
    # calculo antigo, 365 = padrao)
    r60i, r180i, r365i = Counter(), Counter(), Counter()
    r60c, r180c, r365c = Counter(), Counter(), Counter()
    # detalhamento por grupo, pra qualquer vendedor ver onde esta o problema
    # dele — mesmo no grupo que nao pune a experiencia de compra
    gi = defaultdict(Counter)
    gc = defaultdict(Counter)
    validas = []
    sem_pedido = 0
    for c in cl.values():
        p = ords.get(c.get("_ped"))
        if not p:
            sem_pedido += 1
            continue
        _cat = (meta.get(p["i"]) or {}).get("category_id") or p["c"]
        if p["i"]:
            gi[p["i"]][c["_grupo"]] += 1
        if _cat:
            gc[_cat][c["_grupo"]] += 1
        if not c["_conta"]:
            continue
        d = _dias(c["date_created"])
        cat = (meta.get(p["i"]) or {}).get("category_id") or p["c"]
        if p["i"]:
            r365i[p["i"]] += 1
            if d <= 60:
                r60i[p["i"]] += 1
            if d <= JANELA_ANTIGA:
                r180i[p["i"]] += 1
        if cat:
            r365c[cat] += 1
            if d <= 60:
                r60c[cat] += 1
            if d <= JANELA_ANTIGA:
                r180c[cat] += 1
        validas.append((c, p, cat, d))

    # categorias: nome, caminho e DOMINIO, tudo de uma vez
    cats_ids = {m.get("category_id") for m in meta.values() if m.get("category_id")}
    cats_ids |= {v["c"] for v in ords.values() if v.get("c")}

    def _cat(c):
        st, x = g("/categories/%s" % c)
        if st != 200:
            return c, {"nome": c, "caminho": "", "dominio": None, "permite": None,
                       "mestre": None, "espelhos": [], "pai": None}
        cfg = x.get("settings") or {}
        raiz = [y.get("id") for y in (x.get("path_from_root") or [])]
        return c, {"nome": x.get("name"),
                   "caminho": " > ".join(y["name"] for y in (x.get("path_from_root") or [])),
                   # a FAMILIA: o nivel logo acima. Medido: e o pool mais provavel da nota.
                   "pai": raiz[-2] if len(raiz) >= 2 else None,
                   "dominio": cfg.get("catalog_domain"),
                   # ⚠️ o ML marca as gemeas ele mesmo, e isso vale mais que o
                   # dominio: `mirror_master_category` diz de quem a categoria e
                   # espelho, `mirror_slave_categories` diz quem sao os espelhos
                   # dela. `listing_allowed=false` e recusa dura (ex.: MLB1246,
                   # raiz de Beleza, nao aceita anuncio nenhum).
                   "permite": cfg.get("listing_allowed"),
                   "mestre": cfg.get("mirror_master_category"),
                   "espelhos": cfg.get("mirror_slave_categories") or []}
    catinfo = {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        for c, d in ex.map(_cat, sorted(cats_ids)):
            catinfo[c] = d
    cat_nome = {c: d["nome"] for c, d in catinfo.items()}

    def nome_cat(c):
        return cat_nome.get(c)

    # CATEGORIAS GEMEAS: /catalog_domains/{dom}/categories lista todas as
    # categorias que compartilham o mesmo dominio. Mesmo dominio = mesmo
    # esquema de atributos, so muda a arvore. E o contador de vendas de cada
    # uma e SEPARADO — por isso a gemea vazia cai no ramo "sem experiencia".
    # ⚠️ Carencia, nao cura: quando as vendas acumularem la, a nota volta.
    # ⚠️ Estar no mesmo dominio NAO garante que o ML aceita publicar, e NAO EXISTE
    #    checagem previa disso. Testado em 15/09/2026: POST /items/validate
    #    devolveu o MESMO erro de atributo para uma gemea legitima, para uma
    #    categoria absurda (Beleza, para uma macaneta) e para a MLB420116, que
    #    recusou de verdade na hora de publicar. O validate so confere se o corpo
    #    esta completo. O unico filtro previo confiavel e `listing_allowed`.
    doms = sorted({d["dominio"] for d in catinfo.values() if d["dominio"]})

    def _irmas(d):
        st, r = g("/catalog_domains/%s/categories" % d)
        return d, (r if st == 200 and isinstance(r, list) else [])
    por_dom = {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        for d, lst in ex.map(_irmas, doms):
            por_dom[d] = lst
    # nome e caminho das gemeas que ainda nao conheco
    novas = {x.get("id") for lst in por_dom.values() for x in lst
             if x.get("id") and x["id"] not in catinfo}
    if novas:
        with ThreadPoolExecutor(max_workers=10) as ex:
            for c, d in ex.map(_cat, sorted(novas)):
                catinfo[c] = d

    itens = []
    for i, m in meta.items():
        c = m.get("category_id")
        n = notas.get(i) or {}
        v60, v180, v365 = v60i.get(i, 0), v180i.get(i, 0), v365i.get(i, 0)
        calc = n.get("calculo") or "novo"
        if calc == "antigo":                 # o ML ainda nao migrou este anuncio: 180 dias
            ramo, jan = "ANTIGO", JANELA_ANTIGA
            recl, base = r180i.get(i, 0), v180
        else:
            ramo, jan = regras.base(v60, v365, v365c.get(c, 0))
            if ramo == "ITEM":
                recl, base = (r60i.get(i, 0), v60) if jan == JANELA_RAPIDA else (r365i.get(i, 0), v365)
            elif ramo == "HERDA":
                recl, base = r365c.get(c, 0), v365c.get(c, 0)
            else:
                recl, base = 0, 0
        taxa = (100.0 * recl / base) if base else None
        ruim = bool(n.get("ruim"))
        ativo = m.get("status") == "active"
        # ⚠️ "pausado" nao e uma coisa so. Medido: dos anuncios com nota punitiva
        # fora do ar, quase todos estavam `out_of_stock` — o ML pausou sozinho
        # quando o estoque zerou, e eles voltam punidos assim que repor.
        sub = m.get("sub_status") or []
        pausa = ("sem_estoque" if "out_of_stock" in sub
                 else "vendedor" if "paused_by_seller" in sub
                 else None if ativo else "outro")
        # a regra manda dar nota (o anuncio ou a categoria passou do limiar) mas o
        # ML ainda nao deu nenhuma. Nao e punicao: e nota que nao chegou.
        sem_nota = bool(calc == "novo" and ramo in ("ITEM", "HERDA") and n.get("valor") in (None, -1))
        pune, dormente = ruim and ativo, ruim and not ativo
        # nota PARADA: o ML so recalcula quando o anuncio vende (medido: 0 de 51
        # com venda depois da data do calculo). Sem venda, a nota nao se mexe.
        dias_sem_venda = _dias(ultima[i]) if i in ultima else None
        # idade do anuncio: sem ela, "nao vende ha mais de um ano" era chute num
        # anuncio de 3 meses (a janela de pedidos e de 365 dias, so isso)
        criado = (m.get("date_created") or "")[:10]
        idade = _dias(criado) if criado else None
        itens.append(dict(
            id=i, titulo=m.get("title"), thumb=m.get("thumbnail"), link=m.get("permalink"),
            categoria=c, cat_nome=nome_cat(c), status=m.get("status"),
            preco=m.get("price"), estoque=m.get("available_quantity"),
            v60=v60, v180=v180, v365=v365, v60_cat=v60c.get(c, 0), v365_cat=v365c.get(c, 0),
            r60=r60i.get(i, 0), r180=r180i.get(i, 0), r365=r365i.get(i, 0),
            reclamacoes_proprias=r365i.get(i, 0),
            ramo=ramo, janela=jan, reclamacoes=recl, base_vendas=base, taxa=taxa,
            calculo=calc, forma=n.get("forma"), ml=n.get("ml"),
            nota=n.get("valor"), cor=n.get("cor"), rotulo=n.get("texto"),
            pune=pune, dormente=dormente, ruim=ruim, sem_nota=sem_nota,
            situacao=regras.situacao(bool(n.get("freeze")), pune, dormente, sem_nota, ativo),
            dias_sem_venda=dias_sem_venda, idade=idade, criado=criado or None,
            sub_status=sub, pausa=pausa,
            freeze=bool(n.get("freeze")), freeze_txt=n.get("freeze_txt"),
            consequencia=n.get("consequencia"),
            up_id=n.get("up_id"), motivo=n.get("motivo") or [],
            recomendacoes=n.get("recomendacoes") or [], acao=n.get("acao"),
            ml_herda=n.get("ml_herda"),
            grupos=dict(gi.get(i, {})), grupos_cat=dict(gc.get(c, {})),
            pode_mover=v365 == 0,
        ))

    # (Nao existe mais "robo nao passou": medido em 16/09/2026, dois anuncios da
    # mesma categoria com notas diferentes quase sempre diferem porque um tem
    # reclamacao PROPRIA e o outro nao — 98% dos pares. A regra antiga apontava
    # o lado errado em 0 de 54 e 3 de 17 casos.)

    cats = []
    for c in sorted(v365c, key=lambda z: -v365c[z]):
        meus = [x for x in itens if x["categoria"] == c]
        ci = catinfo.get(c) or {}
        gem = []
        for x in (por_dom.get(ci.get("dominio")) or []):
            oid = x.get("id")
            if not oid or oid == c:
                continue
            oi = catinfo.get(oid) or {}
            # papel da gemea em relacao a MINHA categoria
            if oi.get("mestre") == c:
                papel = "espelho_meu"      # e o espelho da minha categoria
            elif ci.get("mestre") == oid:
                papel = "minha_mestre"     # a MINHA e que e espelho dela
            elif oi.get("mestre"):
                papel = "espelho_outra"
            elif oi.get("espelhos"):
                papel = "mestre"
            else:
                papel = "solta"
            gem.append(dict(id=oid, nome=x.get("name") or oi.get("nome"),
                            caminho=oi.get("caminho"),
                            permite=oi.get("permite"), papel=papel,
                            mestre=oi.get("mestre"), pai=oi.get("pai"),
                            # mesma familia = mesmo pool provavel da nota: nao escapa
                            mesma_familia=bool(ci.get("pai") and oi.get("pai") == ci.get("pai")),
                            vendas365=v365c.get(oid, 0),
                            reclamacoes=r365c.get(oid, 0),
                            taxa=(100.0 * r365c.get(oid, 0) / v365c[oid]) if v365c.get(oid) else None,
                            n_anuncios=sum(1 for y in itens if y["categoria"] == oid),
                            acima_limiar=v365c.get(oid, 0) >= LIM_CAT))
        # ordem: quem aceita anuncio e esta zerado primeiro
        gem = [x for x in gem if x.get("permite") is not False]
        # Classifica o DESTINO pelas duas perguntas que interessam:
        #   1. tem experiencia de compra ruim la?  -> nota 30 ou 65 em algum anuncio seu
        #   2. o ML vai remanejar o anuncio de la?  -> mesmo dominio, medido:
        #      em 365 dias, 1 unico remanejo em 369 anuncios, e ele TROCOU de
        #      dominio (MLB-FLOOR_LAMPS -> MLB-FLOOR_CEILING_AND_WALL_LIGHTS).
        #      Nenhum anuncio no dominio certo foi movido.
        # A ficha tecnica identica e consequencia do dominio, nao o criterio.
        # A classificacao final (livre / nota boa / descartada) acontece no
        # painel, onde a nota da categoria de destino ja esta montada.
        gem.sort(key=lambda z: (z["vendas365"] > 0, z["vendas365"]))
        cats.append(dict(
            dominio=ci.get("dominio"), caminho=ci.get("caminho"), gemeas=gem, pai=ci.get("pai"),
            permite=ci.get("permite"), mestre=ci.get("mestre"),
            espelhos=ci.get("espelhos") or [],
            papel=("espelho" if ci.get("mestre") else
                   "mestre" if ci.get("espelhos") else "solta"),
            id=c, nome=nome_cat(c), vendas365=v365c[c], vendas60=v60c.get(c, 0),
            acima_limiar=v365c[c] >= LIM_CAT,
            reclamacoes=r365c.get(c, 0), reclamacoes60=r60c.get(c, 0),
            taxa=(100.0 * r365c.get(c, 0) / v365c[c]) if v365c[c] else None,
            n_anuncios=len(meus), grupos=dict(gc.get(c, {})),
            notas=dict(sorted(Counter(x["nota"] for x in meus).items(),
                              key=lambda z: (z[0] is None, z[0] if isinstance(z[0], int) else 0))),
        ))

    lista = []
    for c, p, cat, d in sorted(validas, key=lambda z: z[0]["date_created"], reverse=True):
        lista.append(dict(id=c["id"], data=c["date_created"][:10], dias=d, pesa=d <= PESO, grupo=c["_grupo"],
                          motivo=c.get("reason_id"), nome=c["_nome"], motivo_txt=c["_txt"],
                          sai60=60 - d, sai365=365 - d,
                          item=p["i"], categoria=cat, cat_nome=nome_cat(cat),
                          titulo=(meta.get(p["i"]) or {}).get("title")))

    # metricas que o proprio ML publica (reputacao do vendedor, janela 60d).
    # E OUTRA METRICA — nao e a experiencia de compra — mas vem de graca e
    # mostra atraso de envio e cancelamento, que a experiencia tambem pesa.
    met = (me.get("seller_reputation") or {}).get("metrics") or {}

    por_grupo = Counter(c["_grupo"] for c in cl.values())
    arrep = por_grupo.get("ARREPENDIMENTO", 0)
    sem_nota_api = sum(1 for i in meta if notas.get(i) is None)
    if sem_nota_api:
        avisos.append("%d anuncios sem resposta da rota de nota — aparecem como cinza" % sem_nota_api)
    # nada some em silencio: o que o painel nao conhece vira aviso, com contagem
    estranhas = Counter(e for n in notas.values() if n for e in (n.get("estranho") or []))
    for k, q in sorted(estranhas.items()):
        avisos.append("%d anuncio(s) com %s" % (q, k))
    antigos = sum(1 for n in notas.values() if n and n.get("calculo") == "antigo")
    d = dict(conta=dict(id=uid, nick=nick),
             quando=dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
             versao=VERSAO, casos=[list(x) for x in regras.CASOS],
             pacote=regras.PACOTE, regras_data=regras.DATA_REGRAS,
             regras=dict(LIM_ITEM=LIM_ITEM, LIM_CAT=LIM_CAT, JANELA=JANELA,
                         JANELA_RAPIDA=JANELA_RAPIDA, JANELA_ANTIGA=JANELA_ANTIGA, PESO=PESO),
             peso_reclamacao=PESO, calculo_antigo=antigos,
             total_claims=len(cl), total_conta=len(validas), total_arrependimento=arrep,
             por_grupo=dict(por_grupo), metricas_ml=met,
             vendas60=sum(v60c.values()), vendas365=sum(v365c.values()),
             entra_na_conta=entra, itens=itens, categorias=cats, reclamacoes=lista,
             # reclamacoes cujo pedido ja saiu da janela de 365d: normal, nao e aviso
             reclamacoes_sem_pedido=sem_pedido,
             avisos=avisos, segundos=round(time.time() - t0, 1))
    # AUTO-AUDITORIA: toda coleta, em qualquer conta, confere o resultado contra
    # regras.checar. Regra que falha e bug — e aparece na tela, nao num log.
    try:
        falhas, _ = regras.checar(d)
    except Exception as e:                   # a conferencia nunca derruba a coleta
        falhas = ["a conferencia interna quebrou: %s" % e]
    if falhas:
        avisos.append("conferencia interna: %d regra(s) falharam — %s"
                      % (len(falhas), "; ".join(falhas[:3])))
    # veredito para a tela: sem "ok" aqui, ela NAO mostra card nenhum — so o que
    # falhou e o botao de coletar de novo. Errado nao se mostra.
    leitura = [a for a in avisos if not a.startswith("conferencia interna")]
    d["conferencia"] = {"ok": not falhas and not estranhas and not leitura, "falhas": falhas[:50],
                        "desconhecidos": ["%d anuncio(s) com %s" % (q, k) for k, q in sorted(estranhas.items())],
                        "leitura": leitura}
    # ⚠️ atomico: um travamento no meio deixava dados.json pela metade e o
    # painel abria em "sem dados" com a coleta anterior perdida
    tmp = CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, CACHE)
    prog("pronto em %.0fs" % (time.time() - t0))
    return d


def carrega():
    if os.path.exists(CACHE):
        try:
            return json.load(open(CACHE, encoding="utf-8"))
        except Exception:
            return None
    return None


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    d = coleta(lambda s: print("  ..." + s, flush=True))
    print("\n%s — %d anuncios | %d reclamacoes: %s"
          % (d["conta"]["nick"], len(d["itens"]), d["total_claims"], d["por_grupo"]))
    print("metricas do proprio ML (60d): %s" % d["metricas_ml"])
