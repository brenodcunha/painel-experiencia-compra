# -*- coding: utf-8 -*-
"""Monta o pacote de distribuicao e PROVA que nao leva nada seu.

    python empacotar.py

Gera painel_experiencia_v<versao>.zip nesta pasta com uma LISTA FECHADA de
arquivos (allowlist — o que nao esta na lista nao entra, mesmo que exista), e
depois abre o zip e varre cada arquivo de texto procurando token, chave,
user_id, App ID, e-mail, telefone ou identificador de conta. Se achar
qualquer coisa, apaga o zip e sai com erro. Nunca entrega um pacote sujo.
"""
import glob, io, json, os, re, sys, zipfile

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import regras
VERSAO = regras.PACOTE      # fonte unica: a tela mostra a mesma versao

# ---- o que VAI (e so isto) ----
LEVA = [
    "index.html", "servidor.py", "coletor.py", "conta.py", "ml.py", "regras.py", "ligar.py",
    "LEIAME.md", "README.md", "REGRAS.md", "AGENTS.md", "CLAUDE.md", ".gitignore", "LICENSE", "empacotar.py",
    # kit de testes LIMPO (projeto publico: quem mexer prova que nao quebrou a regra)
    "audit/verificar_regras.py", "audit/verificar_textos.py", "audit/placar.py", "audit/fixtures/gerar.py",
    "audit/AUDITORIA_FINAL.md", "audit/ajuda_ml_31968_experiencia_de_compra.txt",
    "guia/01-login.png", "guia/02-minhas-aplicacoes.png", "guia/03-informacoes-basicas.png",
    "guia/04-redirect-e-fluxos.png", "guia/05-permissoes.png", "guia/06-permissoes-fim.png",
    "guia/07-escopos-preview.png", "guia/08-validacao-2fa.png", "guia/09-app-id-e-chave.png",
    "guia/10-autorizar.png", "guia/logo-exemplo.png",
]
# ---- o que NUNCA vai, mesmo se alguem editar a lista acima por engano ----
# audit/ vai so em parte: NUNCA os dados das contas (dados_*.json), as medicoes do
# passo 0 (tem MLBs), os apelidos, backups e sobras
PROIBIDO = re.compile(r"(^|/)(conta\.json|dados\.json|dados_[^/]*\.json|.*\.bak|.*\.log|.*\.tmp|__pycache__|"
                      r"\.playwright-mcp|passo0|passo0_medicoes\.md|apelidos\.txt|_painel\.js)(/|$)")

# ---- assinaturas de dado de conta (qualquer uma dentro do zip = falha) ----
VAZAMENTO = {
    "token de acesso":       r"APP_USR-\d+",
    "codigo de autorizacao": r"TG-[0-9a-f]{20,}",
    "refresh token":         r"TG-\d{16}",
    "chave secreta":         r"\b(?=[A-Za-z0-9]{32}\b)(?=[A-Za-z0-9]*[a-z])(?=[A-Za-z0-9]*[A-Z])(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{32}\b",
    "e-mail":                r"\b[\w.+-]+@[\w-]+\.[\w.]+\b",
    "user_id / app_id (16 digitos)": r"(?<!\d)\d{16}(?!\d)",
}
# apelidos das contas usadas nos testes ficam em audit/apelidos.txt (um por linha) —
# fora do pacote, para o proprio empacotar.py nao carregar nome de conta nenhum
_ap = os.path.join(BASE, "audit", "apelidos.txt")
if os.path.isfile(_ap):
    _nomes = [l.strip() for l in io.open(_ap, encoding="utf-8") if l.strip()]
    if _nomes:
        VAZAMENTO["apelido de conta"] = "|".join(r"\b" + re.escape(n) + r"\b" for n in _nomes)
# exemplos didaticos que o guia usa de proposito e nao sao dado real
EXEMPLOS_OK = {"1234567890123456", "voce@email.com"}


def _texto(nome):
    return nome.lower().endswith((".html", ".py", ".md", ".txt", ".json", ".js", ".css"))


def _regras_ok():
    """Antes de empacotar, as regras tem de passar em TODAS as fixtures (cada furo
    achado numa conta real virou uma) e no dados.json desta maquina, se existir.
    E a fixture quebrada de proposito TEM de falhar — senao o verificador e que
    quebrou. Pacote com regra falhando nao sai."""
    import regras
    ruim = False
    for arq in sorted(glob.glob(os.path.join(BASE, "audit", "fixtures", "*.json"))) + \
            [p for p in [os.path.join(BASE, "dados.json")] if os.path.isfile(p)]:
        try:
            falhas, _ = regras.checar(json.load(io.open(arq, encoding="utf-8")))
        except Exception as e:
            falhas = ["quebrou: %s" % e]
        nome = os.path.relpath(arq, BASE)
        deve_falhar = os.path.basename(arq).startswith("_")
        if bool(falhas) != deve_falhar:
            ruim = True
            print("   regra %s em %s: %s" % ("FALHOU" if falhas else "NAO FALHOU (e devia)", nome, "; ".join(falhas[:3])))
        else:
            print("   ok   %s%s" % (nome, " (falha esperada)" if deve_falhar else ""))
    return not ruim


def main():
    faltando = [a for a in LEVA if not os.path.isfile(os.path.join(BASE, a))]
    if faltando:
        print("FALTA arquivo da lista:", ", ".join(faltando)); return 2
    print("conferindo as regras:")
    if not _regras_ok():
        print("PACOTE RECUSADO — regra falhando"); return 3
    # textos fixos da tela: um so, em regras.ROTULOS (nada escrito na mao no index.html)
    import importlib
    vt = importlib.import_module("audit.verificar_textos") if os.path.isdir(os.path.join(BASE, "audit")) else None
    if vt and vt.main() != 0:
        print("PACOTE RECUSADO — texto fixo fora do lugar"); return 4
    for a in LEVA:
        if PROIBIDO.search(a.replace(os.sep, "/")):
            print("arquivo proibido na lista:", a); return 2

    # as fixtures sinteticas vao geradas (deterministicas, sem dado real)
    fixtures = sorted(glob.glob(os.path.join(BASE, "audit", "fixtures", "*.json")))
    saida = os.path.join(BASE, "painel_experiencia_v%s.zip" % VERSAO)
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
        for a in LEVA:
            z.write(os.path.join(BASE, a), "painel_experiencia/" + a)
        for f in fixtures:
            z.write(f, "painel_experiencia/audit/fixtures/" + os.path.basename(f))

    # ---- prova: abre o zip e varre ----
    achados = []
    with zipfile.ZipFile(saida) as z:
        nomes = z.namelist()
        for n in nomes:
            if PROIBIDO.search(n):
                achados.append((n, "arquivo proibido dentro do zip", ""))
            if not _texto(n):
                continue
            t = z.read(n).decode("utf-8", "replace")
            for rot, rx in VAZAMENTO.items():
                for m in re.findall(rx, t):
                    if m in EXEMPLOS_OK:
                        continue
                    achados.append((n, rot, m[:40]))
    if achados:
        os.remove(saida)
        print("PACOTE RECUSADO — encontrei dado de conta:")
        for n, rot, m in achados[:20]:
            print("   %-32s %-30s %s" % (n, rot, m))
        return 1
    tam = os.path.getsize(saida) / 1024
    print("ok: %s (%.0f KB, %d arquivos, nenhum dado de conta)" % (os.path.basename(saida), tam, len(nomes)))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
