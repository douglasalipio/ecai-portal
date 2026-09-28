#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Confere o site gerado antes de publicar.

O comparador olha para tras (o novo bate com o antigo?). Este olha para o
resultado em si e pega o que nenhum schema alcanca, porque tambem vale para
texto escrito direto no componente:

  1. placeholder ⟨assim⟩ sobrando em qualquer pagina
  2. link interno apontando para arquivo que nao existe
  3. src/poster de imagem ou video sem arquivo no disco
  4. og:image / twitter:image apontando para arquivo que nao foi publicado —
     eles so aparecem em <meta>, entao nenhum <img> os denuncia
  5. imagem sem o atributo alt (alt="" e valido: marca a decorativa)

Uso:  python3 ferramentas/verificar.py [pasta]      (padrao: dist)
"""

import glob
import os
import re
import sys
from html.parser import HTMLParser

PLACEHOLDER = re.compile(r"⟨[^⟩]*⟩")
EXTERNO = re.compile(r"^(https?:|mailto:|tel:|data:|#|//)")


class Coletor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []     # href internos
        self.arquivos = []  # src/poster internos
        self.sem_alt = []   # src de <img> sem o atributo alt
        self.sociais = []   # og:image e twitter:image

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "a" and d.get("href") and not EXTERNO.match(d["href"]):
            self.links.append(d["href"].split("#")[0])
        # a imagem de compartilhamento vive so em <meta>, com URL absoluta
        if tag == "meta":
            chave = d.get("property") or d.get("name") or ""
            if chave in ("og:image", "twitter:image") and d.get("content"):
                self.sociais.append(d["content"])

        for campo in ("src", "poster"):
            v = d.get(campo)
            if v and not EXTERNO.match(v):
                self.arquivos.append(v)
        # alt="" e a marcacao certa para imagem decorativa — o brasao do rodape
        # fica ao lado do nome escrito, e uma leitura repetida so atrapalha.
        # So acusa quando o atributo nao existe.
        if tag == "img" and "alt" not in d:
            self.sem_alt.append(d.get("src", "(sem src)"))

    handle_startendtag = handle_starttag


def main():
    pasta = sys.argv[1] if len(sys.argv) > 1 else "dist"
    if not os.path.isdir(pasta):
        sys.exit("nao achei a pasta %s" % pasta)

    paginas = sorted(glob.glob(os.path.join(pasta, "*.html")))
    if not paginas:
        sys.exit("nenhum .html em %s" % pasta)

    problemas = []
    avisos = []

    for caminho in paginas:
        nome = os.path.basename(caminho)
        with open(caminho, encoding="utf-8") as f:
            html = f.read()

        for ph in sorted(set(PLACEHOLDER.findall(html))):
            avisos.append("%s: placeholder %s no ar" % (nome, ph))

        c = Coletor()
        c.feed(html)

        for alvo in sorted(set(c.links)):
            if alvo and not os.path.exists(os.path.join(pasta, alvo)):
                problemas.append("%s: link para %s, que nao existe" % (nome, alvo))

        for alvo in sorted(set(c.arquivos)):
            if not os.path.exists(os.path.join(pasta, alvo)):
                problemas.append("%s: arquivo %s nao foi publicado" % (nome, alvo))

        for url in sorted(set(c.sociais)):
            # sao absolutas (https://ecai.net.br/brasao.jpg): interessa o caminho
            rel = url.split("://", 1)[-1].split("/", 1)[-1] if "://" in url else url
            if not os.path.exists(os.path.join(pasta, rel)):
                problemas.append("%s: imagem de compartilhamento %s nao foi publicada"
                                 % (nome, rel))

        for src in sorted(set(c.sem_alt)):
            avisos.append("%s: <img src=\"%s\"> sem atributo alt" % (nome, src))

    print("%d paginas conferidas em %s/" % (len(paginas), pasta))

    if avisos:
        print("\n%d aviso(s):" % len(avisos))
        for a in avisos:
            print("   ⚠  %s" % a)

    if problemas:
        print("\n%d problema(s):" % len(problemas))
        for p in problemas:
            print("   ✗  %s" % p)
        return 1

    print("\nnenhum link quebrado, nenhum arquivo faltando.")
    # Em modo estrito o aviso tambem barra: e como npm run deploy roda.
    if avisos and os.environ.get("ESTRITO") == "1":
        print("ESTRITO=1: os avisos acima barram a publicacao.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
