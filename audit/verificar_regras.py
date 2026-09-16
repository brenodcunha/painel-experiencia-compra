# -*- coding: utf-8 -*-
"""Confere um dados.json (ou fixture) contra regras.checar. Falha = bug.

    python audit/verificar_regras.py dados.json audit/fixtures/*.json

E a mesma conferencia que o coletor roda sozinho no fim de cada coleta; aqui ela
roda por fora, em qualquer arquivo, e devolve codigo de saida != 0 se falhar.
"""
import io, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import regras


def main(arq):
    d = json.load(io.open(arq, encoding='utf-8'))
    falhas, notas = regras.checar(d)
    print('== %s: %s | %d anuncios | %d categorias' % (
        arq, (d.get('conta') or {}).get('nick'), len(d.get('itens') or []), len(d.get('categorias') or [])))
    for n in notas[:8]:
        print('   nota  ', n)
    if len(notas) > 8:
        print('   ... +%d notas' % (len(notas) - 8))
    if falhas:
        print('   FALHAS: %d' % len(falhas))
        for f in falhas[:25]:
            print('     x', f)
        return 1
    print('   todas as regras OK')
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(max(main(a) for a in sys.argv[1:]))
