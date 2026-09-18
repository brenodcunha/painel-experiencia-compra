# Auditoria final do projeto — 16/09/2026 (feita na v1.1; histórico)

> Este relatório descreve o estado auditado em 16/09/2026 (pacote v1.1, 21 arquivos, 8
> fixtures). As versões seguintes estão na seção 8, no fim. Os números de hoje quem dá é o
> próprio pacote: `python empacotar.py` recusa se qualquer regra, texto fixo ou dado de
> conta estiver errado.

Escopo: **tudo que é o projeto** — os 21 arquivos que vão no zip, o pacote descompactado como
um cliente recebe, a tela em 4 contas reais + 9 fixtures, as regras e o auto-conserto, e a
documentação contra o código. Ferramentas: `audit/verificar_regras.py`, `audit/placar.py`,
`empacotar.py`, Playwright na tela, scripts desta auditoria.

## 1. Código e textos do pacote (estático)
- Sintaxe: 7 `.py` compilam; JavaScript do `index.html` passa no `node --check`.
- Sobras de recurso removido ("robô", `atrasado`, `EXPLICA`, `ORDEM`, `defasada`): nenhuma no
  código; só menções históricas em comentário/REGRAS dizendo que não existe mais.
- Dado de conta em arquivo entregue: **nenhum** — nem MLB de anúncio, nem 16 dígitos, nem
  e-mail, nem apelido, nem nome de categoria/número de uma conta. Corrigido nesta auditoria: a
  docstring do `coletor.py` citava duas categorias e taxas da conta de referência; e o
  `empacotar.py` carregava os apelidos das contas de teste na própria varredura — agora lê de
  `audit/apelidos.txt`, que não vai no zip.
- Constantes da regra (100 / 200 / 60 / 180 / 365 / peso 60) estavam repetidas em textos da
  tela; agora vêm do `dados.json` (`regras`, gravado pelo coletor e pelo auto-conserto) — fonte
  única `regras.py`. Restam só em comentários.
- Servidor: escuta só em `127.0.0.1:8796`; POST com `Origin`/`Sec-Fetch-Site` de fora → 403;
  exceção em handler → JSON 500; `/guia/` só serve imagem da própria pasta; coleta em
  andamento recusa um segundo clique (corrigido: antes respondia "ok" com dado velho).
- `conta.py`: gravação atômica; desconectar(tudo) → `{}`; trocar de app apaga token; 4xx
  desconecta, rede fora avisa. Mensagem técnica ("Salve APP_ID e SECRET") trocada por texto
  para o vendedor.

## 2. O pacote como o cliente recebe (dinâmico)
Zip descompactado numa pasta limpa, servidor de desenvolvimento parado, `python ligar.py`:
- `ligar.py` (nunca testado antes) sobe o servidor, espera a porta e abre o navegador. ✔
- `/` → tela de conexão; `/api/conta` → `ligado false, tem_app false, pacote 1.1`;
  `/api/dados` → vazio; `/guia/01-login.png` → PNG 200; `/guia/../conta.json` e `/guia/x.py`
  → 404; rota inexistente → 404.
- `POST /api/app` vazio → "faltou preencher…"; com `Origin` de outro site → **403**;
  `/api/coletar` desconectado → "conecte a sua conta primeiro"; `/api/codigo` com lixo →
  erro amigável, sem travar; app falso salvo → `tem_app true` + URL de autorização;
  `/api/sair {tudo}` → `conta.json = {}` e desconectado.
- Arquivos que o pacote cria na pasta do cliente: `conta.json`, `servidor.log`, `__pycache__`.

## 3. A tela — 4 contas reais + fixtures (Playwright)
Contas: 954, 729, 961 e 409 anúncios (até 23.330 pedidos/ano). Fixtures: vazia, cálculo
antigo, atalho 60d + sem nota + Decola, família, 3.000 anúncios, quebrada.
- Zero erro de JavaScript em todos.
- Card "Perdendo exposição" = chips preto + vinho em **todos** (83=83, 33=33, 55=55, 20=20,
  887=887 na de 3.000).
- Legenda de Situação: **6 linhas sempre**, com contagem (zero incluído).
- Cada Situação presente abre um detalhe com frase própria (nenhum "SEM FRASE").
- Busca filtra; "+ N mais" existe quando há mais de 7 reclamações e abre; aba Categorias
  renderiza (e mostra estado vazio na conta sem categoria punindo).
- 3.000 anúncios renderizam em ~5 s.
- Fixture quebrada → **tela de bloqueio**, sem card, com os dois motivos.
- Celular (400 px): página sem rolagem horizontal; cards em 1 coluna; tabela rola dentro da
  caixa; detalhe em 1 coluna; bloqueio idem.
- Corrigido nesta auditoria: concordância "As 1 reclamação … passaram".

## 4. Regras e auto-conserto
- `regras.checar`: todas OK nas 4 contas e nas 8 fixtures; `_quebrado.json` falha (como deve).
- `regras.reaplicar`: reproduz o coletor **exatamente** nas 4 contas (0 itens, 0 categorias
  diferentes) e é idempotente (2× = 1×); veredito ok em todas.
- Placar (4 contas): 100+ vendas & nota 100 → texto do anúncio **100%**; <100 vendas & nota
  <100 → texto da categoria **93–100%**; reclamação própria não deixa melhor que o irmão (ambos
  vendendo) **96–100%**; cinza pela regra **88–93%**. Célula "100+ vendas & nota <100" fica só
  como informação: o texto da IA do ML não é consistente nela.
- Trava e reparo testados ao vivo: `dados.json` corrompido → recoleta automática → cards;
  sem `dados.json` → primeira leitura automática → cards.

## 5. Documentação × código
35 promessas do `REGRAS.md`/`LEIAME.md` conferidas por inspeção do código: 35 verdadeiras
(a única "falha" foi o regex da própria checagem — o guia tem 10 passos e 10 prints, todos
presentes em `guia/`).

## 6. O que fica registrado como limite (não é bug)
- O painel lê a nota; não a prevê (média dos concorrentes não está na API; cancelamento,
  atraso e opinião também pesam e não aparecem).
- Anúncio parado carrega nota velha até vender — dito na tela.
- O texto gerado por IA do ML contradiz a regra oficial dele em parte dos anúncios com muitas
  vendas e nota abaixo de 100; o painel mostra o texto e não o usa como regra.

## 7. Resultado (16/09, v1.1)
Pacote `painel_experiencia_v1.1.zip` (21 arquivos) gerado com regras passando em todas as
fixtures e no dado real, sem dado de conta dentro. Pronto para distribuir.

## 8. O que mudou depois (17/09/2026)
- **v1.2** — cancelamentos feitos pelo vendedor contados e mostrados (por anúncio, categoria e
  conta); medido em 4 contas: o ML conta só o do vendedor; pesa junto com a reclamação, nunca
  sozinho. Formato 5 → recoleta sozinho.
- **v1.3** — cada reclamação abre a venda no ML (`vendas/{pedido}/detalhe`) e mostra o produto;
  10 motivos traduzidos, motivo novo vira texto legível. Formato 6.
- **v1.4** — o link avisa qual conta precisa estar logada no navegador; dados de outro
  `user_id` nunca aparecem (trocar de conta recoleta sozinho).
- **v1.5** — 58 textos fixos da tela em `regras.ROTULOS`; `audit/verificar_textos.py` no
  portão do empacotador; varredura de apelido sem limite de palavra. 9 fixtures (+ a quebrada),
  42 arquivos no pacote.
- **v1.6** — reclamação de produto fechada a favor do vendedor ou coberta pelo ML fica na lista com
  selo e sai da conta (medido em 4 contas: não pesa na nota; `audit/passo0_medicoes.md`). Formato 7 →
  recoleta sozinho. `checar` cruza `r365`/`r60` de cada anúncio com a lista. O servidor recarrega
  `regras.py` junto com o coletor a cada coleta. 10 fixtures (+ a quebrada).
- **v1.7** — atualização automática (`atualizador.py`): `ligar.py` e o servidor (a cada 6 h) conferem o
  repositório público; versão nova é baixada, conferida (versão, lista fechada, compila) e trocada
  arquivo a arquivo, nunca `conta.json`/`dados.json`; o servidor se reinicia sozinho. Testado com um
  repositório falso local (`PAINEL_ORIGEM`). `VERSAO_DADOS` no `index.html` conferido pelo empacotador.
