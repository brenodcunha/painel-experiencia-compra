# -*- coding: utf-8 -*-
"""Os textos fixos da tela sao UM so, em regras.ROTULOS. Este teste garante que:
  1. nenhum rotulo esta escrito na mao no index.html (tem de vir de T('chave'));
  2. o REGRAS.md 5 lista cada rotulo letra por letra;
  3. toda chave que a tela pede existe em ROTULOS (senao apareceria "[chave]").
Roda no empacotar.py: falhou, nao sai pacote.

    python audit/verificar_textos.py
"""
import io, os, re, sys
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, BASE)
import regras

# rotulos que nunca aparecem em frase corrida: qualquer copia literal na tela e escrita a mao
ESTRITOS = ("btn_atualizar", "btn_guia", "btn_sair", "card_perdendo", "card_semnota", "card_taxa",
            "card_categorias", "col_recl", "col_taxa", "col_vendas", "det_porque", "det_cai",
            "det_recomenda", "det_reclamacoes_base", "det_reclamacoes_anuncio", "lnk_ml", "lnk_venda",
            "cat_col_notas", "cat_col_mover", "selo_zerado", "selo_boa", "tag_espelho_desta", "tag_mestre_desta", "vazio_cat", "vazio_filtro",
            "vazio_conta", "bloqueio_titulo", "con_titulo", "con_p1", "con_p2")


def main():
    falhas = []
    html = io.open(os.path.join(BASE, 'index.html'), encoding='utf-8').read()
    regs = io.open(os.path.join(BASE, 'REGRAS.md'), encoding='utf-8').read()
    # 1. rotulo escrito na mao na tela
    for k in ESTRITOS:
        v = regras.ROTULOS[k]
        n = html.count(v)
        if n:
            falhas.append('index.html escreve na mao "%s" (%d vez/es) — use T(\'%s\')' % (v, n, k))
    # 2. REGRAS.md lista cada rotulo
    for k, v in regras.ROTULOS.items():
        if ('`%s`' % v) not in regs:
            falhas.append('REGRAS.md nao lista o rotulo `%s` (%s)' % (v, k))
    # 3. chave pedida pela tela existe
    for k in sorted(set(re.findall(r"T\('([a-z0-9_]+)'\)", html))):
        if k not in regras.ROTULOS:
            falhas.append("index.html pede T('%s') e a chave nao existe em regras.ROTULOS" % k)
    if falhas:
        print('TEXTOS: %d falha(s)' % len(falhas))
        for f in falhas:
            print('   x', f)
        return 1
    print('TEXTOS ok: %d rotulos fixos, nenhum escrito na mao, todos no REGRAS.md' % len(regras.ROTULOS))
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
