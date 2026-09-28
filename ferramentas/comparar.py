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
  classes    quantas vezes cada classe global aparece
  zebra      a sequencia de tarjas listradas, com cor e geometria

O canal de zebra existe porque o padrao listrado aparece em seis variantes
(verde, branca, preta, e brancas a 7%, 8% e 10%) e em tres geometrias. No
site antigo isso vinha em data-URI dentro do style=; aqui sao classes. Trocar
uma pela outra nao muda texto nem contagem de classe — so a cor na tela.

O canal de classes existe porque as tres primeiras nao veem layout. As regras
de desktop moram em src/styles/*.css e dependem de nomes exatos: perder um
hero-acoes, ou ganhar um .cartaz onde nao havia, muda a pagina inteira sem
mexer em uma virgula do texto. So entram as classes que essas folhas de fato
usam — as outras sao escolha de componente e variam de proposito.

Uso:  python3 ferramentas/comparar.py _referencia dist
      python3 ferramentas/comparar.py _referencia dist index.html
"""

import glob
import json
import os
import re
import sys
import urllib.parse
from html.parser import HTMLParser

ACEITAS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "diferencas-aceitas.json")

# nomes com hash de conteudo mudam a cada build sem que nada de fato mude
HASH = re.compile(r"\.[0-9a-f]{8}\.(css|js)$")
IGNORAR_TEXTO = {"script", "style", "template"}
TITULOS = {"h1", "h2", "h3", "h4", "h5", "h6"}

ESTILOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "src", "styles")
SELETOR_CLASSE = re.compile(r"\.(-?[_a-zA-Z][_a-zA-Z0-9-]*)")


def classes_globais():
    """Nomes de classe que as folhas globais usam — as que mudam layout."""
    nomes = set()
    if not os.path.isdir(ESTILOS):
        return nomes
    for arq in sorted(glob.glob(os.path.join(ESTILOS, "*.css"))):
        with open(arq, encoding="utf-8") as f:
            css = f.read()
        # so a parte de seletor, antes de cada bloco de declaracoes
        for trecho in re.findall(r"([^{}]+)\{", css):
            nomes.update(SELETOR_CLASSE.findall(trecho))
    return nomes


GLOBAIS = classes_globais()


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
        self.classes = []
        self._pilha = []
        self._coletando = []   # (tipo, destino, pedacos) para links e titulos

    # -- estado ------------------------------------------------------------
    def _mudo(self):
        return any(t in IGNORAR_TEXTO for t in self._pilha)

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        self._pilha.append(tag)

        for c in (d.get("class") or "").split():
            if c in GLOBAIS:
                self.classes.append(c)

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
        # Os nos de texto sao juntados com um espaco, nao concatenados: entre
        # <div>A</div><div>B</div> o build.py nao punha nada e o Astro poe uma
        # quebra de linha. Visualmente identico, e concatenar acusaria "AB" vs
        # "A B" como diferenca. Por no separador nos dois lados, empatam.
        return {
            "texto": " ".join(p for p in (espacos(t) for t in self.texto) if p),
            "titulos": self.titulos,
            "links": self.links,
            "imagens": self.imagens,
            "classes": sorted(self.classes),
        }


def extrair(caminho):
    with open(caminho, encoding="utf-8") as f:
        e = Extrator()
        e.feed(f.read())
        return e.resultado()


def diferenca_lista(antes, depois):
    """So o que entrou e o que saiu, preservando repeticoes."""
    restante = list(depois)
    sumiram = []
    for item in antes:
        if item in restante:
            restante.remove(item)
        else:
            sumiram.append(item)
    return sumiram, restante


def diferenca_texto(antes, depois):
    """Primeiro ponto onde os dois textos divergem, com o contexto ao redor."""
    if antes == depois:
        return None
    i = 0
    while i < min(len(antes), len(depois)) and antes[i] == depois[i]:
        i += 1
    ini = max(0, i - 60)
    return (i, antes[ini:i + 90], depois[ini:i + 90])


CORES_ZEBRA = {"#3f9b46": "verde", "#ffffff": "branca", "#0b0b0b": "preta"}
URI_ZEBRA = re.compile(r"url\('(data:image/svg\+xml,[^']+)'\)")
GEOMETRIA = {
    ("300px 100%", "repeat-x"): "tarja",
    ("300px 300px", "repeat"): "campo",
    ("100% 100%", "repeat-x"): "risco",
}


def nome_zebra(cor, opacidade):
    base = CORES_ZEBRA.get(cor.lower(), cor.lower())
    return base if float(opacidade) >= 1 else "%s-%02d" % (base, round(float(opacidade) * 100))


def zebras_de_referencia(html):
    """No site antigo a zebra vinha como data-URI no proprio style=."""
    achadas = []
    for m in re.finditer(r'style="([^"]*?)"', html):
        estilo = m.group(1)
        uri = URI_ZEBRA.search(estilo)
        if not uri:
            continue
        svg = urllib.parse.unquote(uri.group(1).split(",", 1)[1])
        cor = re.search(r"fill='(#[0-9a-fA-F]{6})'", svg)
        if not cor:
            continue
        opa = re.search(r"fill-opacity='([\d.]+)'", svg)
        size = re.search(r"background-size:([^;\"]+)", estilo)
        rep = re.search(r"background-repeat:([^;\"]+)", estilo)
        geo = GEOMETRIA.get((size.group(1).strip() if size else "",
                             rep.group(1).strip() if rep else ""), "?")
        achadas.append((nome_zebra(cor.group(1), opa.group(1) if opa else "1"), geo))
    return achadas


GEO_CLASSE = {"zebra": "tarja", "zebra-campo": "campo", "zebra-risco": "risco"}


def zebras_de_build(html):
    """No site novo sao duas classes: uma de geometria, uma de cor."""
    achadas = []
    for m in re.finditer(r'class="([^"]*)"', html):
        classes = m.group(1).split()
        geo = next((GEO_CLASSE[c] for c in classes if c in GEO_CLASSE), None)
        cor = next((c[len("zebra-"):] for c in classes
                    if c.startswith("zebra-") and c not in GEO_CLASSE), None)
        if geo and cor:
            achadas.append((cor, geo))
    return achadas


def carregar_aceitas():
    """Desvios conscientes, para o relatorio so mostrar o que ninguem decidiu."""
    if not os.path.exists(ACEITAS):
        return []
    with open(ACEITAS, encoding="utf-8") as f:
        return json.load(f).get("aceitas", [])


def filtrar(itens, aceitas, pagina, tipo, lado):
    """Tira do relatorio o que ja foi decidido.

    Para links/imagens/titulos, cada entrada aceita vale por uma ocorrencia —
    assim um link a mais que o previsto continua aparecendo. Para classes,
    vale por todas: uma classe nova aparece tantas vezes quantas secoes a
    usam, e listar cada uma seria ruido.
    """
    sobrando = list(itens)
    for a in aceitas:
        if a.get("tipo") != tipo or a.get("lado") != lado:
            continue
        if a.get("pagina") not in ("*", pagina):
            continue
        if tipo == "classes":
            alvo = a["item"]
            sobrando = [c for c in sobrando if c != alvo]
        else:
            alvo = tuple(a["item"])
            if alvo in sobrando:
                sobrando.remove(alvo)
    return sobrando


def comparar(ref, novo, nome, aceitas=()):
    a, b = extrair(ref), extrair(novo)
    problemas = []

    with open(ref, encoding="utf-8") as f:
        za = zebras_de_referencia(f.read())
    with open(novo, encoding="utf-8") as f:
        zb = zebras_de_build(f.read())
    if za != zb:
        problemas.append("   zebra: a sequencia nao bate\n      - %s\n      + %s"
                         % (za, zb))

    for campo, rotulo in (("titulos", "titulos"), ("links", "links"),
                          ("imagens", "imagens"), ("classes", "classes globais")):
        sumiram, surgiram = diferenca_lista(a[campo], b[campo])
        sumiram = filtrar(sumiram, aceitas, nome, campo, "fora")
        surgiram = filtrar(surgiram, aceitas, nome, campo, "novo")
        if sumiram or surgiram:
            linhas = []
            for x in sumiram[:8]:
                linhas.append("      - %s" % (x,))
            for x in surgiram[:8]:
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

    aceitas = carregar_aceitas()
    ok = faltando = 0
    for p in paginas:
        destino = os.path.join(novo, p)
        if not os.path.exists(destino):
            print("\n%s\n   AUSENTE em %s" % (p, novo))
            faltando += 1
            continue
        if comparar(os.path.join(ref, p), destino, p, aceitas):
            ok += 1

    total = len(paginas)
    print("\n%d/%d iguais, %d com diferenca, %d ausentes"
          % (ok, total, total - ok - faltando, faltando))
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
