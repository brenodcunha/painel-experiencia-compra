# -*- coding: utf-8 -*-
"""Placar: o que o painel diz x o que o proprio ML escreve em cada anuncio.

    python audit/placar.py dados.json            # depois da coleta (qualquer conta)
    python audit/placar.py audit/passo0/p0_HEUREKAS.json   # linhas do passo 0

Roda ANTES e DEPOIS de qualquer mudanca de modelo. Se cair abaixo do piso medido em
16/09/2026 em 4 contas (base 95%/89%, reclamacao propria 95% entre anuncios que vendem, cinza 88%), nao entrega.
"""
import io, json, re, sys, collections

HERDA = re.compile(r'informa..es suficientes|com base nas (suas|tuas) vendas', re.I)
PUNE = (30, 50, 65)


def linhas(arq):
    d = json.load(io.open(arq, encoding='utf-8'))
    if isinstance(d, list):                       # p0_*.json (passo 0)
        for x in d:
            if x.get('forma') != 'prosa':
                continue
            yield dict(id=x['id'], nota=x['nota'], texto=x['texto'], freeze=x['freeze'], status=x['status'],
                       v60=x['v60'], v365=x['v365'], r365=x['r365'], c365=x['c365'], cat=x['cat'], dias_sem_venda=None)
    else:                                         # dados.json do painel
        for i in d['itens']:
            if i.get('calculo') == 'antigo':
                continue
            yield dict(id=i['id'], nota=i['nota'], texto=' '.join(i.get('motivo') or []), freeze=i['freeze'], status=i['status'],
                       v60=i.get('v60', 0), v365=i['v365'], r365=i.get('reclamacoes_proprias', i.get('r365', 0)),
                       c365=i.get('v365_cat', 0), cat=i['categoria'], dias_sem_venda=i.get('dias_sem_venda'))


def main(arq):
    L = list(linhas(arq))
    com_nota = [x for x in L if x['nota'] not in (None, -1) and not x['freeze'] and x['texto']]
    # 1. base x texto do ML — so nas celulas em que o texto do ML e consistente (medido em
    # 3 contas, 16/09/2026): (a) 100+ vendas com nota 100 -> o ML fala do anuncio;
    # (b) menos de 100 vendas com nota abaixo de 100 -> o ML fala da categoria.
    # Na celula "100+ vendas com nota abaixo de 100" a IA do ML escreve "categoria" em
    # parte dos casos mesmo com 800 vendas e 33 reclamacoes proprias — nao e regra, e
    # texto; fica so como informacao, sem piso.
    ml = lambda x: 'categoria' if HERDA.search(x['texto']) else 'anuncio'
    la = [x for x in com_nota if x['v365'] >= 100 and x['nota'] == 100]
    lb = [x for x in com_nota if x['v365'] < 100 and x['nota'] != 100]
    lc = [x for x in com_nota if x['v365'] >= 100 and x['nota'] != 100]
    ok_a = sum(1 for x in la if ml(x) == 'anuncio'); ok_b = sum(1 for x in lb if ml(x) == 'categoria')
    info_c = sum(1 for x in lc if ml(x) == 'categoria')
    # 2. reclamacao propria derruba: pares na mesma categoria (A com, B sem, ambos com venda)
    por = collections.defaultdict(list)
    for x in L:
        if x['nota'] not in (None, -1) and not x['freeze'] and x['status'] in ('active', 'paused'):
            por[x['cat']].append(x)
    # so pares em que os DOIS venderam nos ultimos 60 dias: o ML so recalcula ao vender, e
    # o vizinho parado carrega nota velha (medido na 4a conta: 88% com todos os pares,
    # 96% so entre anuncios que vendem). Todos os pares ficam como informacao.
    fresco = lambda x: x['dias_sem_venda'] is not None and x['dias_sem_venda'] <= 60
    pior = tot = pior_todos = tot_todos = 0
    for g in por.values():
        com = [x for x in g if x['r365'] > 0]; sem = [x for x in g if x['r365'] == 0 and x['v365'] > 0]
        for a in com:
            for b in sem:
                tot_todos += 1; pior_todos += a['nota'] <= b['nota']
                if fresco(a) and fresco(b):
                    tot += 1; pior += a['nota'] <= b['nota']
    # 3. cinza: categoria < 200 e anuncio < 100 -> sem nota
    at = [x for x in L if x['status'] in ('active', 'paused')]
    cz = sum(1 for x in at if ((x['v365'] >= 100 or x['c365'] >= 200) == (x['nota'] not in (None, -1))))
    print('== %s: %d anuncios no calculo novo' % (arq, len(L)))
    print('   100+ vendas e nota 100 -> ML fala do anuncio . %3d de %3d  (%.0f%%)  piso 95%%' % (ok_a, len(la), 100.0 * ok_a / len(la) if la else 100))
    print('   <100 vendas e nota <100 -> ML fala da categ. . %3d de %3d  (%.0f%%)  piso 89%%' % (ok_b, len(lb), 100.0 * ok_b / len(lb) if lb else 100))
    print('   (info) 100+ vendas e nota <100: ML escreve "categoria" em %d de %d — texto da IA, sem piso' % (info_c, len(lc)))
    print('   reclamacao propria nao deixa melhor que irmao (ambos vendendo) %4d de %4d (%.0f%%)  piso 95%%' % (pior, tot, 100.0 * pior / tot if tot else 100))
    print('   (info) idem contando anuncios parados: %d de %d (%.0f%%)' % (pior_todos, tot_todos, 100.0 * pior_todos / tot_todos if tot_todos else 100))
    print('   cinza pela regra 100/200 ..................... %3d de %3d  (%.0f%%)  piso 88%%' % (cz, len(at), 100.0 * cz / len(at) if at else 0))
    falhas = [(ok_a < 0.95 * len(la)), (ok_b < 0.89 * len(lb)), (pior < 0.95 * tot), (cz < 0.88 * len(at))]
    print('   ' + ('ABAIXO DO PISO' if any(falhas) else 'ok, dentro do medido'))
    return 1 if any(falhas) else 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(max(main(a) for a in sys.argv[1:]))
