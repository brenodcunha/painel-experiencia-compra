# -*- coding: utf-8 -*-
"""Painel de Experiencia de Compra — localhost:8796

Mostra a conta que o ML faz: vendas e reclamacoes de PRODUTO em 365 dias,
a sua taxa, a nota publicada e se ela esta punindo.

NAO preve nota: a media dos concorrentes nao existe em nenhuma rota da API.
A regra completa e as medicoes estao na docstring do coletor.py.
"""
import importlib, json, os, sys, threading, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import coletor, conta, regras

PORTA = 8796
_estado = {"msg": "", "rodando": False, "erro": None}
ORIGENS = {"http://localhost:%d" % 8796, "http://127.0.0.1:%d" % 8796}
_lock = threading.Lock()


def _prog(s):
    _estado["msg"] = s
    print("  ..." + s, flush=True)


def _coletar():
    with _lock:
        if _estado["rodando"]:
            return
        _estado["rodando"] = True
    _estado["erro"] = None
    try:
        # ⚠️ recarrega o coletor do disco antes de rodar. Sem isto o servidor
        # guarda na memoria a versao que existia quando ele subiu: em 14/09/2026
        # um servidor no ar havia 2 dias regravou o dados.json no formato velho
        # quando o botao "atualizar" foi clicado, e o painel quebrou.
        importlib.reload(coletor)
        coletor.coleta(_prog)
    except Exception as e:
        _estado["erro"] = "%s: %s" % (type(e).__name__, e)
        _prog("erro: %s" % e)
    finally:
        _estado["rodando"] = False


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype="application/json"):
        if ctype == "application/json":
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ⚠️ Qualquer excecao dentro de um handler fazia o BaseHTTPServer fechar o
    # socket SEM resposta — o navegador ficava em "Conectando..." para sempre.
    # Agora vira um JSON de erro que a tela mostra.
    def do_GET(self):
        try:
            self._get()
        except Exception as e:
            self._send(500, {"erro": "%s: %s" % (type(e).__name__, e)})

    def do_POST(self):
        # ⚠️ CSRF contra o localhost: qualquer site aberto no navegador do
        # vendedor consegue disparar um POST para 127.0.0.1:8796 (foi assim,
        # de dentro do DevCenter, que eu mesmo mandei a chave para ca). Um site
        # malicioso poderia desconectar a conta ou trocar o app por outro.
        # Navegador sempre manda Origin em POST cross-site; script local nao.
        origem = self.headers.get("Origin")
        if origem and origem not in ORIGENS:
            return self._send(403, {"erro": "origem nao permitida"})
        sfs = self.headers.get("Sec-Fetch-Site")
        if sfs and sfs not in ("same-origin", "none"):
            return self._send(403, {"erro": "origem nao permitida"})
        try:
            self._post()
        except Exception as e:
            self._send(500, {"erro": "%s: %s" % (type(e).__name__, e)})

    def _get(self):
        p = urllib.parse.urlparse(self.path).path
        if p in ("/", "/index.html"):
            return self._send(200, open(os.path.join(BASE, "index.html"), "rb").read(),
                              "text/html; charset=utf-8")
        if p == "/api/conta":
            return self._send(200, dict(conta.estado(), pacote=regras.PACOTE))
        if p == "/api/dados":
            d = coletor.carrega()
            # ⚠️ dados de OUTRA conta: trocar de conta (ou passar a pasta adiante) deixava
            # o painel mostrando os anuncios do dono anterior com o nome da conta nova.
            # Tratar como "sem dados" faz a tela ler a conta certa sozinha.
            if d and not d.get("vazio"):
                quem = (conta.estado() or {}).get("user_id")
                if quem and (d.get("conta") or {}).get("id") not in (None, quem):
                    d = None
            if d and d.get("versao") == regras.VERSAO:
                # AUTO-CONSERTO antes de mostrar: a classificacao e refeita pela regra
                # a partir dos contadores crus, e o veredito e fechado de novo. So o
                # que nao esta nos dados (leitura incompleta, valor desconhecido) fica
                # de fora — e ai a tela bloqueia.
                try:
                    regras.reaplicar(d)
                    regras.veredito(d)
                except Exception as e:
                    d.setdefault("conferencia", {})
                    d["conferencia"].update(ok=False, falhas=["auto-conserto quebrou: %s" % e])
            return self._send(200, d if d else {"vazio": True})
        if p == "/api/progresso":
            return self._send(200, _estado)
        if p.startswith("/guia/"):
            # so imagens do guia, e so de dentro da pasta guia (sem ../)
            nome = os.path.basename(p)
            alvo = os.path.join(BASE, "guia", nome)
            if (nome.lower().endswith((".png", ".jpg", ".webp"))
                    and os.path.isfile(alvo)
                    and os.path.dirname(os.path.abspath(alvo)) == os.path.join(BASE, "guia")):
                tipo = "image/png" if nome.lower().endswith(".png") else (
                       "image/webp" if nome.lower().endswith(".webp") else "image/jpeg")
                return self._send(200, open(alvo, "rb").read(), tipo)
        return self._send(404, {"erro": "rota"})

    def _corpo(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        except Exception:
            return {}

    def _post(self):
        p = urllib.parse.urlparse(self.path).path
        if p == "/api/coletar":
            if not conta.estado()["ligado"]:
                return self._send(200, {"erro": "conecte a sua conta primeiro"})
            if _estado["rodando"]:
                # ⚠️ segunda aba clicando junto: antes voltava "ok" na hora e a tela
                # mostrava o dado velho como se fosse novo
                return self._send(200, {"erro": "uma atualização já está em andamento — aguarde ela terminar"})
            _coletar()
            # o erro da coleta ia para o log e a tela apagava a mensagem:
            # falha silenciosa. Agora volta na resposta.
            return self._send(200, {"ok": not _estado["erro"], "erro": _estado["erro"]})
        if p == "/api/app":
            d = self._corpo()
            falta = [k for k in ("app_id", "secret", "redirect") if not (d.get(k) or "").strip()]
            if falta:
                return self._send(200, {"erro": "faltou preencher: " + ", ".join(falta)})
            conta.salvar_app(d["app_id"], d["secret"], d["redirect"])
            return self._send(200, conta.estado())
        if p == "/api/codigo":
            ok, msg = conta.trocar_codigo(self._corpo().get("codigo") or "")
            e = conta.estado()
            e["erro"] = None if ok else msg
            return self._send(200, e)
        if p == "/api/sair":
            return self._send(200, conta.desconectar(bool(self._corpo().get("tudo"))))
        return self._send(404, {"erro": "rota"})


if __name__ == "__main__":
    print("\n  http://localhost:%d\n" % PORTA, flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORTA), H).serve_forever()
