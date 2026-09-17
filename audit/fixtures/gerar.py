# -*- coding: utf-8 -*-
"""Gera as fixtures: contas sinteticas no formato do dados.json (versao 4).

    python audit/fixtures/gerar.py

Cada furo encontrado numa conta real vira uma fixture aqui, para sempre. As
fixtures sao conferidas por regras.checar no `empacotar.py` — o pacote nao sai
se alguma falhar. `_quebrado.json` e o teste negativo: TEM de falhar; se um dia
passar, e o verificador que quebrou.
"""
import io, json, os, random, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, '..', '..'))
import regras
from regras import VERSAO, PESO

VOL = {}     # categoria -> (vendas365, reclamacoes365, pai); definido por fixture


def item(mlb, cat, status='active', nota=100, cor='green', v60=0, v365=0, v180=None, r60=0, r365=0, r180=None,
         freeze=False, calculo='novo', ml=None, dias_sem_venda=30, idade=400, motivo=None, cancelamentos=0, cancelamentos60=0):
    vcat, rcat, _ = VOL[cat]
    v180 = v365 if v180 is None else v180
    r180 = r365 if r180 is None else r180
    if calculo == 'antigo':
        ramo, jan, recl, base = 'ANTIGO', regras.JANELA_ANTIGA, r180, v180
    else:
        ramo, jan = regras.base(v60, v365, vcat)
        if ramo == 'ITEM':
            recl, base = (r60, v60) if jan == regras.JANELA_RAPIDA else (r365, v365)
        elif ramo == 'HERDA':
            recl, base = rcat, vcat
        else:
            recl, base = 0, 0
    ruim = regras.punitiva(nota, cor) and not freeze
    ativo = status == 'active'
    sem_nota = calculo == 'novo' and ramo in ('ITEM', 'HERDA') and nota in (None, -1)
    pune, dormente = ruim and ativo, ruim and not ativo
    if motivo is None:
        motivo = [] if nota in (None, -1) else (
            ['Como não temos informações suficientes, calculamos com base nas suas vendas de produtos na mesma categoria.']
            if ramo == 'HERDA' else ['Você ofereceu uma excelente experiência de compra.'])
    return dict(id=mlb, titulo='Produto ' + mlb[-4:], thumb=None, link=None, categoria=cat, cat_nome='Categoria ' + cat,
                status=status, preco=99.0, estoque=0 if status != 'active' else 5,
                v60=v60, v180=v180, v365=v365, v60_cat=0, v365_cat=vcat, r60=r60, r180=r180, r365=r365,
                reclamacoes_proprias=r365, cancelamentos=cancelamentos, cancelamentos60=cancelamentos60,
                ramo=ramo, janela=jan, reclamacoes=recl, base_vendas=base,
                taxa=round(100.0 * recl / base, 8) if base else None, calculo=calculo,
                forma='template' if calculo == 'antigo' else 'prosa', ml=ml,
                nota=nota, cor=cor, rotulo=None, pune=pune, dormente=dormente, ruim=ruim, sem_nota=sem_nota,
                situacao=regras.situacao(freeze, pune, dormente, sem_nota, ativo), dias_sem_venda=dias_sem_venda, idade=idade, criado=None,
                sub_status=[] if ativo else ['out_of_stock'], pausa=None if ativo else 'sem_estoque',
                freeze=freeze, freeze_txt='Programa Decola' if freeze else '', consequencia='', up_id=None,
                motivo=motivo, recomendacoes=[], acao='', ml_herda=ramo == 'HERDA', grupos={}, grupos_cat={},
                pode_mover=v365 == 0)


def categoria(cid, itens, gemeas=(), cancelamentos=0):
    vendas365, reclamacoes, pai = VOL[cid]
    meus = [i for i in itens if i['categoria'] == cid]
    notas = {}
    for i in meus:
        notas[str(i['nota'])] = notas.get(str(i['nota']), 0) + 1
    return dict(id=cid, nome='Categoria ' + cid, caminho='Raiz > Familia ' + pai + ' > Categoria ' + cid,
                dominio='MLB-DOM', pai=pai, permite=True, mestre=None, espelhos=[], papel='solta',
                vendas365=vendas365, vendas60=0, acima_limiar=vendas365 >= regras.LIM_CAT,
                reclamacoes=reclamacoes, reclamacoes60=0, cancelamentos=cancelamentos,
                taxa=round(100.0 * reclamacoes / vendas365, 8) if vendas365 else None,
                n_anuncios=len(meus), grupos={}, notas=notas,
                gemeas=[dict(id=g[0], nome='Gemea ' + g[0], caminho='Raiz > Familia %s > Gemea %s' % (g[1], g[0]),
                             permite=True, papel='solta', mestre=None, pai=g[1], mesma_familia=(g[1] == pai),
                             vendas365=g[2], reclamacoes=0, taxa=0.0 if g[2] else None, n_anuncios=0,
                             acima_limiar=g[2] >= regras.LIM_CAT) for g in gemeas])


def reclamacao(cid, item_id, cat, dias):
    return dict(id=cid, data='2026-01-01', dias=dias, pesa=dias <= PESO, grupo='PRODUTO', motivo='PDD9999', pedido='2000000000001',
                nome='not_working_item', motivo_txt='', sai60=60 - dias, sai365=365 - dias,
                item=item_id, categoria=cat, cat_nome='Categoria ' + cat, titulo='Produto')


def conta(nick, itens, cats, recl=()):
    recl = list(recl)
    return dict(conta=dict(id=1, nick=nick), quando='16/09/2026 00:00', versao=VERSAO,
                casos=[list(c) for c in regras.CASOS], rotulos=dict(regras.ROTULOS), peso_reclamacao=PESO,
                pacote=regras.PACOTE, regras_data=regras.DATA_REGRAS,
                regras=dict(LIM_ITEM=regras.LIM_ITEM, LIM_CAT=regras.LIM_CAT, JANELA=regras.JANELA,
                            JANELA_RAPIDA=regras.JANELA_RAPIDA, JANELA_ANTIGA=regras.JANELA_ANTIGA, PESO=regras.PESO),
                conferencia={'ok': True, 'falhas': [], 'desconhecidos': [], 'leitura': []},
                calculo_antigo=sum(1 for i in itens if i['calculo'] == 'antigo'),
                total_claims=len(recl), total_conta=len(recl), total_arrependimento=0, por_grupo={'PRODUTO': len(recl)},
                metricas_ml={}, vendas60=0, vendas365=sum(c['vendas365'] for c in cats), entra_na_conta=[],
                cancelamentos_conta={'seller': sum(i['cancelamentos'] for i in itens)}, cancelamentos_vendedor=sum(i['cancelamentos'] for i in itens),
                itens=itens, categorias=cats, reclamacoes=recl, reclamacoes_sem_pedido=0, avisos=[], segundos=1.0)


def grava(nome, d):
    with io.open(os.path.join(AQUI, nome), 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False)
    print('  ', nome, len(d['itens']), 'anuncios')


def main():
    global VOL
    # 01 conta vazia
    VOL = {}
    grava('01_vazia.json', conta('VAZIA', [], []))

    # 02 punido no ramo SEM (base 0) — furo achado na 2a conta testada: antes virava "robo"
    VOL = {'C1': (10, 1, 'P1')}
    it = [item('MLB1000000001', 'C1', nota=30, cor='red'),
          item('MLB1000000002', 'C1', status='paused', nota=65, cor='orange')]
    grava('02_punido_sem_base.json', conta('SEMBASE', it, [categoria('C1', it)]))

    # 03 calculo antigo (forma template, 180 dias) — com nota e cinza
    VOL = {'C2': (500, 10, 'P2')}
    it = [item('MLB1000000003', 'C2', calculo='antigo', v180=16, r180=2, v365=20, r365=2, nota=65, cor='orange',
               ml={'vendas': 16, 'problemas': 2, 'reclamacoes': 2, 'cancelamentos': 0, 'de': '2026-03-12', 'ate': '2026-09-08'},
               motivo=['Nos últimos 180 dias, você fez 16 vendas e teve 2 problemas.']),
          item('MLB1000000004', 'C2', calculo='antigo', v180=0, v365=3, nota=-1, cor=None, dias_sem_venda=200,
               motivo=['Ela ainda não foi calculada porque seu anúncio não teve vendas nos últimos 180 dias.']),
          item('MLB1000000005', 'C2', nota=100, cor='green', v365=40)]
    grava('03_calculo_antigo.json', conta('ANTIGO', it, [categoria('C2', it)],
                                          [reclamacao('R1', 'MLB1000000003', 'C2', 20), reclamacao('R2', 'MLB1000000003', 'C2', 100)]))

    # 04 nota 50 (faixa laranja) — pune como 65
    VOL = {'C3': (300, 20, 'P3')}
    it = [item('MLB1000000006', 'C3', status='paused', nota=50, cor='orange'),
          item('MLB1000000007', 'C3', nota=75, cor='green', v365=12)]
    grava('04_nota_50.json', conta('NOTA50', it, [categoria('C3', it)]))

    # 05 sem Decola, tudo punido numa categoria (legenda com zeros)
    VOL = {'C4': (400, 40, 'P4')}
    it = [item('MLB10000000%02d' % k, 'C4', nota=30 if k % 2 else 65, cor='red' if k % 2 else 'orange',
               status='active' if k < 13 else 'paused', v365=5) for k in range(10, 16)]
    grava('05_todos_punidos.json', conta('PUNIDOS', it, [categoria('C4', it)]))

    # 06 atalho dos 60 dias + sem nota ainda + Decola
    VOL = {'C5': (50, 0, 'P5'), 'C6': (250, 30, 'P6')}
    it = [item('MLB1000000020', 'C5', v60=120, v365=300, r60=3, r365=9, nota=75, cor='green'),
          item('MLB1000000021', 'C5', v60=10, v365=150, r365=1, nota=-1, cor=None),      # ITEM sem nota: "sem nota ainda"
          item('MLB1000000022', 'C6', v365=3, nota=30, cor='red', freeze=True),           # Decola
          item('MLB1000000023', 'C6', v365=0, nota=-1, cor=None, dias_sem_venda=None, idade=25)]  # HERDA cinza, novo: sem nota ainda
    grava('06_atalho60_semnota_decola.json', conta('ATALHO', it, [categoria('C5', it), categoria('C6', it)],
                                                   [reclamacao('R%d' % k, 'MLB1000000020', 'C5', 10 * k) for k in range(1, 10)]))

    # 07 gemeas: mesma familia (nao serve) e outra familia (serve)
    VOL = {'C7': (260, 30, 'PAI7')}
    it = [item('MLB1000000030', 'C7', nota=65, cor='orange', v365=8)]
    grava('07_familia.json', conta('FAMILIA', it, [categoria('C7', it, gemeas=(('G1', 'PAI7', 0), ('G2', 'PAI8', 0), ('G3', 'PAI8', 250)))]))

    # 08 gigante: 3.000 anuncios em 40 categorias (desempenho da tela)
    rnd = random.Random(7)
    VOL = {}
    for c in range(40):
        vc = rnd.choice([0, 50, 250, 1200])
        VOL['C%d' % (100 + c)] = (vc, vc // 30, 'PAI%d' % (c // 3))
    it, cats = [], []
    for c in range(40):
        cid = 'C%d' % (100 + c)
        for k in range(75):
            nota = rnd.choice([100, 100, 100, 75, 65, 30, -1])
            it.append(item('MLB2%09d' % (c * 75 + k), cid, status=rnd.choice(['active', 'active', 'paused']),
                           nota=nota, cor={100: 'green', 75: 'green', 65: 'orange', 30: 'red', -1: None}[nota],
                           v60=rnd.choice([0, 0, 5, 130]), v365=rnd.choice([0, 3, 40, 150]), r365=rnd.choice([0, 0, 1, 3])))
        cats.append(categoria(cid, it))
    grava('08_gigante_3000.json', conta('GIGANTE', it, cats))

    # 09 cancelamentos do vendedor: punido sem reclamacao propria, com 2 cancelamentos (a frase cita)
    VOL = {'C8': (300, 25, 'P8')}
    it = [item('MLB1000000050', 'C8', nota=65, cor='orange', v365=20, cancelamentos=2, cancelamentos60=1),
          item('MLB1000000051', 'C8', nota=100, cor='green', v365=30)]
    grava('09_cancelamentos.json', conta('CANCEL', it, [categoria('C8', it, cancelamentos=2)]))

    # _quebrado: TEM de falhar (situacao trocada de proposito)
    VOL = {'C9': (300, 30, 'P9')}
    it = [item('MLB1000000040', 'C9', nota=30, cor='red')]
    it[0]['situacao'] = ['', 'ok']
    q = conta('QUEBRADO', it, [categoria('C9', it)])
    q['conferencia'] = {'ok': False, 'falhas': ['MLB1000000040 situacao trocada de proposito'], 'desconhecidos': []}
    grava('_quebrado.json', q)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
