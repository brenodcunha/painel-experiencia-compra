# Painel de Experiência de Compra — Mercado Livre

Mostra, anúncio por anúncio, **por que a sua nota de Experiência de Compra está onde
está** e para onde dá para mover um anúncio que está sendo punido. Tudo roda no seu
computador, lendo a sua conta com o **seu próprio aplicativo** do Mercado Livre.
Nada é enviado para lugar nenhum.

## O que você precisa
- Windows, Mac ou Linux com **Python 3.10 ou mais novo** (https://www.python.org).
  Nada mais: o painel não instala biblioteca nenhuma.
- Uma conta de vendedor no Mercado Livre **Brasil**.
- O celular da conta por perto (o Mercado Livre pode pedir um código por SMS ao
  mostrar a chave do aplicativo).

## Como abrir
1. Descompacte a pasta onde quiser.
2. Dê dois cliques em `ligar.py` — ou, num terminal, `python ligar.py`.
3. O navegador abre em `http://localhost:8796`. Se não abrir, digite esse endereço.

Para fechar, feche a janela do terminal.

## Como atualizar para uma versão nova
Quando receber um zip novo, **descompacte por cima da pasta antiga**, substituindo os
arquivos. Sua conexão (`conta.json`) e seus dados (`dados.json`) ficam onde estão —
o zip nunca traz esses dois. Na primeira abertura, se o formato dos dados mudou, o painel
**refaz a leitura da conta sozinho** — é assim que uma versão nova recalcula tudo. A versão aparece ao lado do nome da conta (`painel v1.1`): é ela que
você informa se pedir ajuda.

## Primeira vez: conectar a sua conta
Na tela inicial, clique em **Como criar seu aplicativo no DevCenter** no topo. São 10
telas, com a imagem de cada uma e os pontos que costumam travar. Leva uns 5 minutos.
Depois disso é só colar **App ID** e **Chave secreta** no passo `.01`, autorizar no
passo `.02` e pronto — o painel lê a conta na hora.

Você só faz isso **uma vez**. Depois o acesso se renova sozinho.

## Atualizar os dados
A primeira leitura acontece sozinha assim que você conecta. Depois, clique em
**Atualizar os anúncios da conta** quando quiser. Uma conta com 400 anúncios leva uns
30 segundos; com 1.000, uns 90.

Antes de mostrar qualquer número, o painel confere os próprios dados contra as regras.
Se algo não bate (uma leitura que não veio inteira, um valor que ele não conhece), ele
refaz a leitura sozinho; se ainda assim não passar, mostra **o que falhou** em vez dos
números — nunca um painel errado.

## O que o painel mostra
- **Perdendo exposição** — anúncios na faixa vermelha ou laranja (30, 50, 65), no ar
  (perdendo agora) ou fora do ar (a punição volta quando repor).
- **Sem nota ainda** — pela regra já teria nota, o Mercado Livre não calculou.
- **Categorias afetadas** — só as que estão punindo, e para onde dá para mover.
- Dentro de cada anúncio: a conta que o Mercado Livre faz (a regra oficial: 100 vendas
  no anúncio, 200 na categoria), o texto dele explicando a nota, **o que está
  segurando a nota** — reclamação do próprio anúncio (e se ela ainda pesa: uma
  reclamação pesa forte por 60 dias) ou a categoria — e as reclamações uma a uma.
- Se o anúncio não vende há tempo, o painel avisa: o Mercado Livre só refaz a nota
  quando ele vender.
- Vendas que **você** cancelou aparecem por anúncio e por categoria: o Mercado Livre conta esse
  cancelamento na nota (o do comprador e o de mediação, não). Medido em quatro contas, ele pesa
  junto com a reclamação — sozinho não derrubou nenhum anúncio.

O painel **não adivinha a nota**: o Mercado Livre compara você com os outros vendedores
da categoria, e esses números não existem na API. Ele lê a nota e explica o que a segura.
As regras completas estão em `REGRAS.md`.

## Segurança
- A credencial fica em `conta.json`, nesta pasta, só na sua máquina.
- O painel **só lê** a sua conta. Não publica, não pausa, não altera nada.
- Ao clicar em **Desconectar esta conta**, o arquivo é apagado por inteiro.
- **Antes de passar esta pasta para outra pessoa, desconecte.** Ou apague
  `conta.json` e `dados.json` — os dois são seus.

## Para quem for mexer no código
Leia `AGENTS.md` (qualquer IA de código lê esse arquivo sozinha ao abrir a pasta). A regra
mora em `regras.py` + `REGRAS.md`; os testes estão em `audit/`; `python empacotar.py` gera o
zip e recusa se uma regra falhar ou se houver dado de conta dentro.

## Se algo der errado
- *"Conectando…" não termina* — feche o terminal e abra de novo com `ligar.py`.
- *A chave não aparece no DevCenter* — clique no ícone de olho ao lado de
  "Chave secreta"; pode pedir SMS.
- *403 ao atualizar* — falta a permissão **Comunicações pré e pós-vendas** no
  aplicativo (é ela que libera as reclamações). Ajuste no DevCenter e autorize de novo.

## Licença
MIT — use, copie e modifique à vontade, sem garantia. O texto está em `LICENSE`.
