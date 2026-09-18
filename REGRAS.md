# REGRAS DO PAINEL — comportamento fixado

Este documento é o contrato. O painel tem que se comportar **exatamente assim** em
qualquer conta. Se algo na tela contradiz uma regra daqui, é bug — não é "a conta
é diferente". A regra da métrica é a **oficial do Mercado Livre**
(https://www.mercadolivre.com.br/ajuda/31968) e foi **conferida** contra o texto que o
próprio ML escreve em cada anúncio, em quatro contas (409 a 961 anúncios), em 16/09/2026.
As medições estão em `audit/passo0_medicoes.md`; o placar em `audit/placar.py`.

A regra mora num lugar só: `regras.py`. O coletor classifica com ela, a tela só
desenha o que veio, e `regras.checar()` confere o resultado **em toda coleta, em
qualquer conta** — regra que falha vira aviso vermelho na tela (seção 8).

---

## 1. A métrica (o que o Mercado Livre faz — texto oficial)

```
anúncio com 100+ vendas em 60 dias  → só o anúncio, janela de 60 dias   (ramo ITEM, janela 60)
senão, anúncio com 100+ no ano      → só o anúncio, janela de 365 dias  (ramo ITEM, janela 365)
senão, categoria com 200+ no ano    → anúncio + categoria                (ramo HERDA)
senão                               → sem experiência de compra, cinza   (ramo SEM)

nota = você comparado aos OUTROS VENDEDORES da categoria:
       Boa 75–100 · Mediana 50–74 (2× abaixo da média deles) · Ruim ≤30 (3× abaixo)
```

| constante | valor | onde |
|---|---|---|
| `LIM_ITEM` | 100 vendas | `regras.py` |
| `LIM_CAT` | 200 vendas / ano | `regras.py` |
| `JANELA` / `JANELA_RAPIDA` / `JANELA_ANTIGA` | 365 / 60 / 180 dias | `regras.py` |
| `PESO` | 60 dias (reclamação própria pesa forte) | `regras.py` |

**O painel lê a nota, não a prevê.** A média dos concorrentes não existe na API
(11 rotas testadas), e a nota ainda soma atraso, cancelamento, opiniões e mensagens.
Valores vistos: `-1` (cinza) · `30` · `50` · `65` · `75` · `100`. **A regra é a faixa,
não o número:** `color` vermelha (`Ruim`) ou laranja (`Média`) **pune**; verde e cinza
não. Valor ou cor que o painel não conhece vira **aviso**, nunca silêncio.

### 1.1 O que foi medido além do texto oficial
| fato | medida (quatro contas) |
|---|---|
| 100+ vendas com nota 100 → o ML fala do anúncio | 100% nas 4 contas |
| menos de 100 vendas com nota abaixo de 100 → o ML fala da categoria | 93% · 97% · 100% · 100% |
| ⚠ 100+ vendas com nota abaixo de 100: o texto da IA do ML diz "categoria" em parte dos casos (12 de 20 · 7 de 16 · 0 de 6) mesmo com 800 vendas e 33 reclamações próprias — é texto, não regra; não entra no placar | medido em 3 contas |
| cinza pela regra 100/200 | 88% · 91% · 93% · 93% (a "categoria" do ML parece ser a **família**, o pai: 91% e 95% nas duas primeiras) |
| **reclamação do próprio anúncio derruba só ele** (irmão sem reclamação fica melhor ou igual) | 96–100% dos pares entre anúncios que **venderam nos últimos 60 dias**; contando vizinhos parados cai a 88–99% — é a nota parada do vizinho que quebra a comparação, não a regra |
| reclamação pesa forte por **~60 dias** e depois vai perdendo peso | com reclamação recente 35% em 100 · sem, 95% |
| **reclamação que o vendedor ganhou ou que o ML cobriu não pesa** (`resolution.benefited` inclui `respondent`) | 19 anúncios só com essas (e que venderam depois): 19 em 100 · pares na mesma categoria com o mesmo nº de reclamações do comprador e uma dessas a mais: 6 piores × 5 melhores em 207 (vendedor ganhou), 0 × 2 em 61 (ML cobriu) — contra 172 × 8 quando a "a mais" é do comprador (18/09/2026) |
| **nota parada**: o ML só recalcula quando o anúncio vende | 0 de 51 com venda depois da data do cálculo |
| **cálculo antigo** (180 dias) ainda em alguns anúncios | o ML avisa no artigo; a API devolve outra forma |

O que sobra de diferença entre a regra e o ML é nota parada (anúncio sem venda) ou
problema que a API não mostra (cancelamento, atraso, opinião).

### 1.2 O que é "venda"
- **Venda = pedido**, não unidade. Pedido cancelado **conta** (só-pagos não muda nada).
- Pedido com dois anúncios diferentes = uma venda para **cada** anúncio, e uma venda
  para cada categoria envolvida.
- Vendas de anúncio já **encerrado** contam para a categoria.
- A categoria de um pedido é a categoria **atual** do anúncio; se o anúncio não existe
  mais, é a categoria congelada no pedido.

### 1.3 O que é "reclamação que conta"
Regra **estrutural** (não é lista de nomes — se o ML criar motivo novo, a regra segue):

```
conta  ⇔  reason.flow termina em "_delivered"   (o produto chegou)
       E  reason.name ≠ "repentant_buyer"        (não é arrependimento)
       E  "respondent" ∉ resolution.benefited     (o vendedor não ganhou, nem o ML cobriu)
```

| grupo | o que é | conta? |
|---|---|---|
| PRODUTO | chegou e tem problema (não funciona, quebrado, faltou peça, diferente…) | **sim** |
| ARREPENDIMENTO | chegou bem, o comprador desistiu | não |
| ENTREGA | não chegou, atrasou, foi cancelado | não |

Desfecho (`status` + `resolution.benefited`, que a busca já traz — `regras.desfecho`):

| desfecho | `benefited` | conta? | na tela |
|---|---|---|---|
| comprador | `[complainant]` | **sim** | pesa agora / pesa pouco |
| vendedor | `[respondent]` (quase sempre `no_bpp`) | **não** | `fechada a seu favor · não conta` |
| ml_cobriu | `[complainant, respondent]` (`coverage_decision`, `warehouse_decision`) | **não** | `o Mercado Livre cobriu · não conta` |
| sem_beneficiado | vazio (`timeout`, `return_expired`, acordo…) | sim | — |
| aberta | `status ≠ closed` | sim | — |

Medido em 4 contas (18/09/2026, `audit/passo0_medicoes.md`): as duas que não contam não movem a
nota; a do comprador move. `affects-reputation` não serve: 1.048 das 1.107 que o comprador ganhou
vêm `not_affected` e derrubam a nota mesmo assim. A reclamação que não conta **fica na lista**
(`conta = false`, com selo) e **fora de todos os contadores** (`r60/r180/r365`, categoria, taxa,
`total_conta`); `total_nao_conta` guarda quantas. `checar` confere que `r365`/`r60` de cada anúncio
batem com as que contam na lista. A cada coleta o desfecho é relido: o que fechar a favor do
vendedor sai da conta sozinho.

- **Nunca** classificar pelo campo `detail`. `/claims/{id}/affects-reputation` é outra
  métrica (reputação do vendedor). Reclamação cujo pedido saiu da janela fica fora
  (`reclamacoes_sem_pedido`), sem aviso.
- Cada reclamação carrega `pesa` = **conta e** tem até 60 dias (pesa forte no próprio anúncio).

### 1.4 Cancelamento — conta só o que **você** cancela, e é mostrado, não punido
- A busca de pedidos traz quem pediu o cancelamento (`cancel_detail.requested_by`: `seller`,
  `buyer`, `meli`). O ML conta como "cancelamento" **só o do vendedor** (medido: nos anúncios em
  que ele publica a contagem, escreveu 0 onde só havia comprador ou mediação).
- É entrada oficial da nota, e o ML cita no texto (*"cancelaste mais pedidos que a média"* → 92%
  punidos, 4 contas). Mas é raro (129 de 5.166 cancelamentos no ano, 4 contas) e **nunca derrubou
  um anúncio sozinho** (1 punido em 12 sem reclamação; 187 pares iguais na mesma categoria; toda
  categoria punida já tinha reclamação ≥ 6,6%).
- Por isso o painel **conta e mostra** — `cancelamentos` / `cancelamentos60` por anúncio,
  `cancelamentos` por categoria, `cancelamentos_vendedor` e `cancelamentos_conta` (por quem pediu)
  na conta — e cita na frase do detalhe, **sem** mudar a faixa de punição.

### 1.5 As duas formas da API e o que o painel faz
| a API devolve | significa | o painel |
|---|---|---|
| `reasoning` (texto em prosa, gerado por IA) | **cálculo novo** | regra da seção 1 |
| sem `reasoning`, com `subtitles` + `metrics_details` ("nos últimos 180 dias…") | **cálculo antigo**, anúncio não migrado | `calculo = antigo`, ramo `ANTIGO`, contadores de **180 dias**, mostra os números que o ML escreveu |
| nenhuma das duas | desconhecida | conta e avisa |
| `reputation.value` como texto | converte | número |
| `freeze` preenchido (Programa Decola) | punição anulada | `ruim = false`, chip Decola |
| pausado por `out_of_stock` / pelo vendedor | `pausa` | os dois viram "sem estoque" na Situação |
| nota `-1`/ausente com ramo ITEM ou HERDA (cálculo novo) | a regra daria nota, o ML não calculou | `sem_nota` |

---

## 2. A coleta (`coletor.py`) — limites da API e como são contornados

| rota | limite medido | tratamento |
|---|---|---|
| `/users/{id}/items/search` | `offset ≥ 1000` → HTTP 400 | `search_type=scan` + `scroll_id`; se falhar, modo comum até 1.000 **e avisa** |
| `/orders/search` | `offset ≥ 10.000` → recusa | o ano é **fatiado por data**; janela com mais de 9.950 pedidos é partida ao meio até caber |
| `/post-purchase/v1/claims/search` | aceita offset acima de 4.000 | lê tudo; freio de 20.000 por status, **com aviso** |
| `/items?ids=` | 20 por chamada | lotes de 20 |
| `/categories/{id}` | — | nome, caminho, domínio, `listing_allowed`, espelhos e **pai** (família) |
| qualquer rota | 429 / 5xx / rede | `ml.req` repete até 5× com espera crescente |
| 401 no meio | token venceu | renova **uma** vez e repete |

Contadores por anúncio e por categoria em **60, 180 e 365 dias**; última venda de cada
anúncio (`dias_sem_venda`). Gravação **atômica** (`.tmp` + `os.replace`).
**Versão do formato:** `dados.json` carrega `versao: 7`; a tela (`VERSAO_DADOS` no `index.html`, conferido
pelo empacotador contra `regras.VERSAO`) recusa outra **e coleta de novo
sozinha** (é assim que uma versão nova do painel recalcula a conta de quem já usava).
**Avisos:** tudo que não foi lido inteiro, tudo que o painel não conhece, e toda regra
que falhou na conferência interna vai em `avisos[]` e aparece na linha de status.

---

## 3. O painel (`index.html`) — o que cada parte mostra

### 3.1 Cards (topo) — são também o filtro da tabela
| card | conta |
|---|---|
| Perdendo exposição | `pune` (no ar, faixa vermelha/laranja) + `dormente` (fora do ar, idem) |
| Sem nota ainda | `sem_nota` |
| Taxa geral | reclamações que contam ÷ vendas da conta, 365 d |
| Categorias afetadas | categorias dando nota punitiva em pelo menos um anúncio seu |

Não existe mais "Esperando o robô": medido, dois anúncios da mesma categoria com notas
diferentes quase sempre diferem porque um tem reclamação **própria** — não é atraso.

### 3.2 Cor da taxa (bolinha) — relativa à **própria conta**
```
MEDIA = taxa geral da conta
verde    taxa ≤ MEDIA · amarelo  MEDIA < taxa < 2×MEDIA · vermelho taxa ≥ 2×MEDIA (e > 0) · cinza sem taxa
```
Nunca é escala absoluta (a nota depende da média dos concorrentes, que não existe na API).

### 3.3 Situação — os 6 casos, sempre todos, com a contagem
A Situação **vem pronta do coletor** (`regras.situacao`); a tela não classifica. A legenda
é a lista fixa `regras.CASOS`, inteira, com quantos anúncios do recorte estão em cada
caso — **idêntica em qualquer conta**; zero continua sendo verdade.

| chip | cor | quando |
|---|---|---|
| perdendo exposição | preto `#0b1220` | no ar, faixa vermelha/laranja |
| sem estoque · volta punido ao repor | vinho `#720022` | fora do ar, faixa vermelha/laranja |
| sem nota ainda | magenta `#a4007e` | a regra daria nota, o ML não calculou |
| sem estoque · volta ok | petróleo `#115e59` | fora do ar, sem punição |
| Decola | bronze `#854a00` | punição anulada pelo programa |
| ok | cinza `#64748b` | no ar, sem punição |

O chip é o mesmo em todas as abas; a aba só filtra. As cores de Situação **nunca** são
as da Taxa. Cor nova só entra medindo ΔE em OKLCH e ≥ 4,5:1 com o texto branco.

### 3.4 Detalhe do anúncio
- `.01 A conta`: reclamações ÷ vendas da **base** (anúncio 60 d, anúncio 365 d,
  categoria, cálculo antigo 180 d ou nenhuma); quantas reclamações são **deste anúncio**
  no ano, quantas **ainda pesam** (≤ 60 dias) e quantas **não contam** (fechadas a seu favor /
  cobertas pelo ML); quantas vendas dele **você cancelou** no ano
  (e nos últimos 60 dias); quando parado, o tempo sem vender —
  **honesto com a idade** (`idade` = dias desde `date_created`): `não vende há N dias` ·
  `nunca vendeu desde que foi criado, há N dias` (anúncio com menos de um ano) ·
  `não vende há mais de um ano` (só se o anúncio tem mais de um ano);
  no cálculo antigo, os números que o ML escreveu.
- `.02 Por que essa nota`: o texto do próprio ML + **uma frase** dizendo o que segura a
  nota: reclamação própria que ainda pesa (e em quantos dias deixa de pesar) · reclamação
  própria já leve · categoria puxando (com o contador dela) · cancelamentos seus, se houver ·
  fechadas a seu favor / cobertas pelo ML, se houver (não contam) · e, se não vende,
  *"o Mercado Livre só refaz a nota quando ele vender"*.
- `.03 Reclamações`: as da base; sem base, as do próprio anúncio. As que contam primeiro, cada
  uma com `pesa agora` / `pesa pouco` e em quantos dias sai da janela; as que não contam depois,
  com o selo `fechada a seu favor · não conta` ou `o Mercado Livre cobriu · não conta`; todas com
  o link **abrir a venda ↗**
  (`mercadolivre.com.br/vendas/{pedido}/detalhe` — a página "Detalhe da venda", onde estão a
  reclamação, o produto e o comprador; testado logado). O link abre na conta logada **no
  navegador**: se for outra, o ML mostra erro — por isso a lista avisa qual conta é preciso estar e, quando é de outro anúncio da
  categoria, o nome do produto com link para o anúncio. 7 visíveis, "+ N mais".

### 3.5 Aba Categorias
- Lista **só** categorias que já punem. Conta sem nenhuma: estado vazio explicando.
- **Para onde dá para mover** = categorias do **mesmo domínio** e de **outra família**
  (pai diferente). Gêmea da mesma família não entra: medido, herda a mesma nota.
- A coluna *Reclam.* mostra também `N cancel. seus` na categoria (ver 1.4).
- Selos do destino (regra oficial dos 200): `contador zerado` · `contador baixo · N de 200`
  · `nota boa comprovada` (≥ 200 vendas suas lá e só 75/100). `listing_allowed = false`
  nunca aparece.

---

## 4. Conexão (`conta.py`, `servidor.py`)

- Cada vendedor usa **o próprio aplicativo** do DevCenter. Credencial em `conta.json`,
  só nesta máquina. Permissões (medido, 10/10 rotas): Usuários (imposta pelo ML) ·
  Publicação e sincronização · Métricas do negócio · Venda e envios de um produto ·
  **Comunicações pré e pós-vendas** (libera as reclamações). Todas em Leitura.
- Token vale 6 h; renova sozinho com o `refresh_token` (rotaciona; o novo é gravado).
- **Desconectar apaga tudo** (`conta.json` → `{}`). Trocar de app apaga o token antigo.
- **Dados de outra conta nunca aparecem:** se o `dados.json` salvo é de outro `user_id`, o
  painel trata como "sem dados" e lê a conta certa sozinho (trocar de conta ou passar a pasta
  adiante não mostra os anúncios do dono anterior).
- `estado()`: ML respondeu **4xx** → desconectado. ML **não respondeu** → continua
  conectado e avisa.
- Servidor escuta **só** em `127.0.0.1:8796`. `POST` com `Origin` de outro site → **403**.
  Exceção em handler vira JSON `{"erro": ...}` com HTTP 500.
- Redirect: `https://httpbin.org/get` — só o pouso do código; nunca vê chave nem token.

---

### 4.1 Atualização automática do painel (`atualizador.py`)
- **Fonte:** o repositório público fixado em `atualizador.REPO` (ramo `RAMO`). Versão = `PACOTE` do
  `regras.py` — a do repositório (arquivo cru) contra a desta pasta. Só HTTPS; nunca outro endereço.
- **Quando:** `ligar.py` confere antes de subir; o servidor confere a cada 6 h (`INTERVALO`) e entrega
  o resultado em `/api/conta → atualizacao` sem esperar a rede; a tela, ao ver `disponivel`, pede
  `POST /api/atualizar_painel`, espera o servidor voltar e recarrega (uma tentativa por versão, por aba).
- **O que troca:** só os arquivos da lista fechada `LEVA` do `empacotar.py` que veio no zip (lida por
  `ast`, sem executar) + `audit/fixtures/*.json`. **Nunca** `conta.json`, `dados.json`, `*.bak`, logs,
  `__pycache__` — a lista os recusa mesmo que o zip os traga. Caminho absoluto ou `..` → recusa.
- **Antes de tocar em qualquer arquivo:** o zip traz a versão anunciada; todos os arquivos da lista
  estão lá; todo `.py` compila. Qualquer falha → nada muda, e a tela diz o motivo na linha de status.
- **Troca:** arquivo por arquivo, atômica (`.tmp` + `os.replace`). Depois o servidor **se encerra** e
  `ligar.py --reiniciar` sobe o novo (a versão velha fica na memória do processo antigo). Com o
  `ligar.py` trocando os arquivos e o servidor no ar, ele pede `POST /api/reiniciar` e sobe o novo.
- **Sem internet / repositório fora:** silêncio; o painel segue na versão que está.
- **Confiança:** quem controla o repositório controla o que roda nos painéis. Só publicar o que passou
  pelo `empacotar.py`; conta do GitHub com 2FA. Painéis anteriores à 1.7 não têm o atualizador:
  precisam de um último download à mão.

## 5. Texto e nomes — o que não pode mudar
- Nada na tela cita conta, anúncio, categoria ou número de uma conta específica.
- **Rótulos fixos — moram em `regras.ROTULOS`, a tela só desenha o que vem de lá** (chip da
  Situação em `regras.CASOS`). `audit/verificar_textos.py` recusa o pacote se um deles for escrito
  na mão no `index.html` ou sumir desta lista. Mudou uma palavra: muda em `regras.py` **e** aqui.
  - Botões: `Atualizar os anúncios da conta` · `Como criar seu aplicativo no DevCenter` · `Desconectar esta conta` · `Salvar e gerar o link` · `Conectar` · `Coletar de novo`
  - Cards: `Perdendo exposição` · `Sem nota ainda` · `Taxa geral` · `Categorias afetadas`
  - Legenda: `Taxa` · `Nota` · `Situação`
  - Colunas da tabela: `Anúncio` · `Nota` · `Base` · `Vendas 365d` · `60d` · `Reclam. na base` · `Taxa da base` · `Situação`
  - Base: `o anúncio` · `a categoria` · `cálculo antigo` · `nenhuma`
  - Detalhe: `A conta` · `Como cai sozinha` · `Por que essa nota` · `O ML recomenda` · `Reclamações` · `reclamações na base` · `reclamações deste anúncio no ano` · `Abrir no Mercado Livre ↗` · `abrir a venda ↗` · `fechada a seu favor · não conta` · `o Mercado Livre cobriu · não conta`
  - Aba Categorias: `Categoria` · `Vendas 365d` · `Reclam.` · `Taxa` · `Anúncios` · `Notas que está dando` · `Para onde dá para mover` · `contador zerado` · `contador baixo` · `nota boa comprovada` · `dá a nota` · `abaixo de` · `espelho de` · `tem espelho` · `espelho desta` · `a mestre desta` · `Nenhuma categoria sua está punindo`
  - Estados vazios e bloqueio: `Nada encontrado com esse filtro.` · `Esta conta não tem nenhum anúncio.` · `Sem dados ainda.` · `O painel não passou na própria conferência`
  - Conexão: `Conecte a sua conta do Mercado Livre` · `Cole os dados do seu aplicativo` · `Autorize e copie o código`
- Botão que vira "Conectando…"/"Salvando…" **sempre** volta: `try/catch` + teto de 45 s.
- Erro de coleta e aviso ficam na linha de status em vermelho até a próxima coleta.

## 6. O que o painel NÃO faz (de propósito)
- Não escreve nada na conta (só `GET`; o único `POST` é o login OAuth).
- Não prevê nota. Não move anúncio de categoria — só mostra para onde daria.
- Não recebe webhook. Só Mercado Livre **Brasil**.
- Da internet só baixa o próprio painel, do repositório fixado em `atualizador.REPO` (4.1). Nunca outro código.

## 7. Como conferir uma conta nova em 2 minutos
1. Linha de status **sem ⚠**. Se houver, ler: é limite da API, coisa desconhecida ou
   regra que falhou — nunca confiar nos números antes de entender.
2. Card `Perdendo exposição` = chips preto + vinho (a legenda mostra as contagens).
3. Legenda de Situação tem os **6** casos, com número, em qualquer conta.
4. Abrir um anúncio punido: a frase do `.02` cita reclamação própria **ou** a categoria,
   nunca "robô"; o `.03` marca `pesa agora` só nas de até 60 dias.
5. `python audit/placar.py dados.json` dentro do piso (95% / 89% / 95% / 88% — medido em
   quatro contas, de 409 a 961 anúncios).
6. Desconectar → tela do zero, campos vazios, guia no topo, `conta.json` = `{}`.

## 8. Como uma conta nova se confere sozinha
- **Toda coleta** termina com `regras.checar(dados)`: ramo/janela, base, taxa, faixa de
  punição, `sem_nota`, Situação, cards = soma dos chips, categorias, gêmeas, reclamações.
  O veredito vai em `dados.json → conferencia {ok, falhas, desconhecidos}`.
- **Auto-conserto antes de mostrar.** Ao servir `/api/dados`, o servidor **reaplica a
  regra** (`regras.reaplicar`: ramo, base, taxa, faixa, `sem_nota`, Situação, categorias,
  gêmeas, peso das reclamações — tudo recalculado dos contadores crus) e fecha o veredito
  (`regras.veredito`). Classificação velha ou inconsistente se conserta sozinha.
- **Só mostra os cards se tudo passou.** A tela lê o veredito **e repete o essencial por
  conta própria** (versão, casos, Situação de cada anúncio, taxa, cards = chips). Se algo
  reprovou — regra, valor desconhecido **ou leitura incompleta da API** — ela **coleta de
  novo sozinha, uma vez**; se ainda reprovar, tela de bloqueio com a lista do que falhou e
  o botão *Coletar de novo*. Sem dados ou formato velho: a primeira coleta também é
  automática. Nenhum número aparece sem passar por isso.
- **Nada some em silêncio**: forma de resposta, nota ou cor desconhecidas viram aviso
  com contagem.
- **Cada furo vira fixture** em `audit/fixtures/` (gerada por `gerar.py`): punido sem
  base, cálculo antigo, nota 50, conta sem Decola, atalho dos 60 dias, gêmea da mesma
  família, cancelamentos do vendedor, conta de 3.000, reclamação fechada a seu favor / coberta
  pelo ML (na lista, fora da conta). `_quebrado.json` **tem** de falhar.
- `python empacotar.py` roda as regras em todas as fixtures e no `dados.json` da máquina
  **antes** de montar o zip. Regra falhando ou dado de conta dentro → **não sai pacote**.
- `python audit/verificar_regras.py <arquivo>` e `python audit/placar.py <arquivo>` rodam
  as mesmas conferências por fora, em qualquer conta.
