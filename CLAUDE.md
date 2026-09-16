# Para quem (ou qual IA) abrir esta pasta

Este é o **Painel de Experiência de Compra** do Mercado Livre: Python puro (3.10+, sem
biblioteca externa) + um `index.html`. Lê a conta do vendedor com o **app dele** no DevCenter
e explica, anúncio por anúncio, por que a nota está onde está.

## Ligar
```
python ligar.py
```
Sobe o servidor em **http://localhost:8796** e abre o navegador. Se já estiver no ar, só
abre o navegador. Ao entrar nesta pasta, faça isso e informe o endereço.

## O que NUNCA fazer
- Não enviar, commitar, copiar ou mostrar `conta.json` (credencial do vendedor) nem
  `dados.json` (dados da conta dele). Os dois ficam só nesta máquina e já estão no `.gitignore`.
- Não escrever nada na conta do Mercado Livre: o painel só lê (o único POST é o login OAuth).

## Onde está a regra
- `regras.py` — a regra da métrica (fonte única). O coletor classifica com ela; a tela só
  desenha o que veio; `regras.checar` confere o resultado em toda coleta.
- `REGRAS.md` — o contrato em português: o que cada parte da tela tem de mostrar, e por quê.
- `LEIAME.md` — para o vendedor.

## Se for mudar alguma coisa
1. Mexa em `regras.py` (e atualize `REGRAS.md`).
2. Crie uma fixture do caso novo em `audit/fixtures/gerar.py` e gere: `python audit/fixtures/gerar.py`.
3. Confira: `python audit/verificar_regras.py audit/fixtures/0*.json dados.json`
   e `python audit/placar.py dados.json` (tem de ficar dentro do piso).
4. Gere o pacote: `python empacotar.py` — ele **recusa** o zip se uma regra falhar ou se houver
   dado de conta dentro.

A tela também se confere sozinha antes de desenhar: regra quebrada não mostra card nenhum,
mostra o que falhou. Então uma mudança errada aparece na hora.

## Licença
MIT (`LICENSE`). Contribuições entram sob a mesma licença.
