#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compara duas pastas de HTML gerado e aponta o que mudou de verdade.

Existe para tornar a migracao para Astro verificavel: o site de hoje vira a
referencia congelada em _referencia/, e cada pagina migrada e conferida contra
ela. Nao compara bytes — formatacao, ordem de atributos e espaco em branco
mudam de gerador para gerador sem que nada quebre. Compara o que o visitante
percebe:

  texto      todo o texto visivel, com espacos normalizados
  titulos    a sequencia de h1..h6, que e o esqueleto da pagina
  links      href + rotulo, na ordem
  imagens    src + alt, na ordem

Uso:  python3 ferramentas/comparar.py _referencia dist
      python3 ferramentas/comparar.py _referencia dist index.html
"""

import os
import re
import sys
from html.parser import HTMLParser

# nomes com hash de conteudo mudam a cada build sem que nada de fato mude
HASH = re.compile(r"\.[0-9a-f]{8}\.(css|js)$")
IGNORAR_TEXTO = {"script", "style", "template"}
TITULOS = {"h1", "h2", "h3", "h4", "h5", "h6"}


def normalizar(url):
    return HASH.sub(r".HASH.\1", (url or "").strip())


def espacos(texto):
    return re.sub(r"\s+", " ", texto).strip()


class Extrator(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.texto = []
        self.titulos = []
        self.links = []
        self.imagens = []
        self._pilha = []
        self._coletando = []   # (tipo, destino, pedacos) para links e titulos

    # -- estado ------------------------------------------------------------
    def _mudo(self):
        return any(t in IGNORAR_TEXTO for t in self._pilha)

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        self._pilha.append(tag)

        if tag == "img":
            self.imagens.append((normalizar(d.get("src")), espacos(d.get("alt") or "")))
        elif tag == "a":
            self._coletando.append(["link", normalizar(d.get("href")), []])
        elif tag in TITULOS:
            self._coletando.append(["titulo", tag, []])

    def handle_startendtag(self, tag, attrs):
        if tag == "img":
            d = dict(attrs)
            self.imagens.append((normalizar(d.get("src")), espacos(d.get("alt") or "")))

    def handle_endtag(self, tag):
        # fecha o coletor mais recente do mesmo tipo
        alvo = "link" if tag == "a" else ("titulo" if tag in TITULOS else None)
        if alvo:
            for i in range(len(self._coletando) - 1, -1, -1):
                if self._coletando[i][0] == alvo:
                    _, chave, pedacos = self._coletando.pop(i)
                    rotulo = espacos("".join(pedacos))
                    (self.links if alvo == "link" else self.titulos).append((chave, rotulo))
                    break
        if tag in self._pilha:
            # desempilha ate o tag correspondente (HTML gerado pode omitir fechamentos)
            while self._pilha and self._pilha.pop() != tag:
                pass

    def handle_data(self, data):
        if self._mudo():
            return
        self.texto.append(data)
        for c in self._coletando:
            c[2].append(data)

    # -- resultado ---------------------------------------------------------
    def resultado(self):
        return {
            "texto": espacos("".join(self.texto)),
            "titulos": self.titulos,
            "links": self.links,
            "imagens": self.imagens,
        }


def extrair(caminho):
    with open(caminho, encoding="utf-8") as f:
        e = Extrator()
        e.feed(f.read())
        return e.resultado()


def diferenca_lista(antes, depois, limite=8):
    """So o que entrou e o que saiu, preservando repeticoes."""
    restante = list(depois)
    sumiram = []
    for item in antes:
        if item in restante:
            restante.remove(item)
        else:
            sumiram.append(item)
    return sumiram[:limite], restante[:limite]


def diferenca_texto(antes, depois):
    """Primeiro ponto onde os dois textos divergem, com o contexto ao redor."""
    if antes == depois:
        return None
    i = 0
    while i < min(len(antes), len(depois)) and antes[i] == depois[i]:
        i += 1
    ini = max(0, i - 60)
    return (i, antes[ini:i + 90], depois[ini:i + 90])


def comparar(ref, novo, nome):
    a, b = extrair(ref), extrair(novo)
    problemas = []

    for campo, rotulo in (("titulos", "titulos"), ("links", "links"), ("imagens", "imagens")):
        sumiram, surgiram = diferenca_lista(a[campo], b[campo])
        if sumiram or surgiram:
            linhas = []
            for x in sumiram:
                linhas.append("      - %s" % (x,))
            for x in surgiram:
                linhas.append("      + %s" % (x,))
            problemas.append("   %s (%d fora, %d novos)\n%s"
                             % (rotulo, len(sumiram), len(surgiram), "\n".join(linhas)))

    d = diferenca_texto(a["texto"], b["texto"])
    if d:
        pos, ta, tb = d
        problemas.append("   texto diverge na posicao %d\n      - ...%s...\n      + ...%s..."
                         % (pos, ta, tb))

    if problemas:
        print("\n%s" % nome)
        for p in problemas:
            print(p)
    return not problemas


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__.strip())
    ref, novo = sys.argv[1], sys.argv[2]
    so = sys.argv[3] if len(sys.argv) > 3 else None

    paginas = sorted(f for f in os.listdir(ref) if f.endswith(".html"))
    if so:
        paginas = [p for p in paginas if p == so]
        if not paginas:
            sys.exit("nao achei %s em %s" % (so, ref))

    ok = faltando = 0
    for p in paginas:
        destino = os.path.join(novo, p)
        if not os.path.exists(destino):
            print("\n%s\n   AUSENTE em %s" % (p, novo))
            faltando += 1
            continue
        if comparar(os.path.join(ref, p), destino, p):
            ok += 1

    total = len(paginas)
    print("\n%d/%d iguais, %d com diferenca, %d ausentes"
          % (ok, total, total - ok - faltando, faltando))
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
