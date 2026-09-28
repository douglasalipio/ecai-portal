#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extrai as tarjas de zebra do site antigo e escreve src/styles/zebra.css.

A faixa listrada que separa as secoes vinha do export de design como um SVG
de ~3,5 KB embutido em data-URI dentro do atributo style — ate quatro vezes
na mesma pagina, repetido nas nove paginas. Este script recolhe as variantes
que realmente aparecem e emite uma classe CSS para cada uma, para o SVG
trafegar uma vez e ficar em cache.

Os bytes do SVG sao copiados como estao: o desenho nao muda.

Uso:  python3 ferramentas/extrair-zebra.py [pasta]     (padrao: _referencia)
"""

import glob
import os
import re
import sys
import urllib.parse
from collections import Counter

SAIDA = os.path.join("src", "styles", "zebra.css")
URI = re.compile(r"url\('(data:image/svg\+xml,[^']+)'\)")

CABECALHO = """/* Zebra — o padrao listrado que o site usa como tarja e como fundo.
 *
 * Gerado por ferramentas/extrair-zebra.py a partir do HTML do site antigo.
 * Nao edite a mao: rode o script de novo.
 *
 * Use sempre duas classes: uma de GEOMETRIA e uma de COR.
 *
 *   .zebra          tarja horizontal        300px 100%, repeat-x
 *   .zebra-campo    fundo ladrilhado        300px 300px, repeat
 *   .zebra-risco    risco esticado          100% 100%, repeat-x
 *
 *   .zebra-verde .zebra-branca .zebra-preta .zebra-branca-07 ...
 *
 * Exemplo:  <div class="zebra zebra-branca"></div>
 *           <div class="zebra-campo zebra-branca-10"></div>
 *
 * A cor tambem sai como --zebra-<nome>, para quando so o valor serve.
 *
 * O nome e <cor>[-<opacidade>]; a opacidade so aparece quando nao e 1.
 */
"""

BASE = """/* geometria */
.zebra       { background-repeat: repeat-x; background-size: 300px 100%; }
.zebra-campo { background-repeat: repeat;   background-size: 300px 300px; }
.zebra-risco { background-repeat: repeat-x; background-size: 100% 100%; }

/* cor */"""

CORES = {"#3f9b46": "verde", "#ffffff": "branca", "#0b0b0b": "preta"}


def nomear(cor, opacidade):
    base = CORES.get(cor, cor.lstrip("#"))
    if float(opacidade) >= 1:
        return base
    # 0.10 -> 10, 0.07 -> 07
    return "%s-%02d" % (base, round(float(opacidade) * 100))


def main():
    pasta = sys.argv[1] if len(sys.argv) > 1 else "_referencia"
    if not os.path.isdir(pasta):
        sys.exit("nao achei a pasta %s" % pasta)

    variantes, quantas = {}, Counter()
    for arquivo in sorted(glob.glob(os.path.join(pasta, "*.html"))):
        with open(arquivo, encoding="utf-8") as f:
            for uri in URI.findall(f.read()):
                svg = urllib.parse.unquote(uri.split(",", 1)[1])
                cor = re.search(r"fill='(#[0-9a-fA-F]{6})'", svg)
                opa = re.search(r"fill-opacity='([\d.]+)'", svg)
                if not cor:
                    continue
                chave = nomear(cor.group(1).lower(), opa.group(1) if opa else "1")
                variantes[chave] = uri
                quantas[chave] += 1

    if not variantes:
        sys.exit("nenhuma tarja encontrada em %s" % pasta)

    vars_ = ["  --zebra-%s: url('%s');" % (n, variantes[n]) for n in sorted(variantes)]
    classes = [".zebra-%s { background-image: var(--zebra-%s); }" % (n, n)
               for n in sorted(variantes)]

    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    with open(SAIDA, "w", encoding="utf-8") as f:
        f.write(CABECALHO + "\n:root {\n" + "\n\n".join(vars_) + "\n}\n\n"
                + BASE + "\n\n" + "\n".join(classes) + "\n")

    print("%d variantes -> %s (%.1f KB)" % (len(variantes), SAIDA,
                                            os.path.getsize(SAIDA) / 1024))
    for n in sorted(variantes):
        print("   .zebra-%-12s %dx no site antigo" % (n, quantas[n]))


if __name__ == "__main__":
    main()
