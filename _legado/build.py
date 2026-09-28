#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera o site estatico em dist/ a partir do arquivo de design (.dc.html) + conteudo.json.

O .dc.html original e um prototipo do canvas Claude Design: roda num runtime
proprietario (support.js), tem moldura de celular fixa em 392x848 e troca de
"tela" por estado JavaScript. Este script converte tudo em HTML/CSS puro:

  - remove a moldura de celular e o rotulo de prototipo
  - transforma cada <sc-if isX> em uma pagina real com URL propria
  - expande <sc-for> com os dados de conteudo.json
  - troca onClick de estado por <a href> de verdade
  - troca <image-slot> por <img> com lazy loading
  - converte style-hover (atributo do runtime) em CSS :hover real
  - layout fluido: largura total no celular, coluna centrada no desktop

Uso:  python3 build.py
"""

import hashlib
import json
import os
import re
import shutil
import sys
import urllib.parse

RAIZ = os.path.dirname(os.path.abspath(__file__))
ORIGEM = os.path.join(RAIZ, "Capoeira Mobile.dc.html")
CONTEUDO = os.path.join(RAIZ, "conteudo.json")
SAIDA = os.path.join(RAIZ, "dist")

LARGURA_MAX = 480  # coluna do site no desktop


# ---------------------------------------------------------------- utilidades

def ler(caminho):
    with open(caminho, encoding="utf-8") as f:
        return f.read()


def attr(tag_interna, nome):
    m = re.search(r'\b%s="([^"]*)"' % nome, tag_interna)
    return m.group(1) if m else None


def resolver(ctx, expr):
    """Resolve 'f.foto' / 'd' / 'isHome' dentro do contexto."""
    valor = ctx
    for parte in expr.strip().split("."):
        if isinstance(valor, dict):
            if parte not in valor:
                return None
            valor = valor[parte]
        else:
            return None
    return valor


# --------------------------------------------------- motor de template (sc-*)

ABERTURA = re.compile(r"<sc-(if|for)\b([^>]*)>")


def bloco(tpl, inicio, tipo):
    """Devolve (corpo, indice_depois_do_fechamento) contando aninhamento."""
    abre = re.compile(r"<sc-%s\b[^>]*>" % tipo)
    fecha = re.compile(r"</sc-%s>" % tipo)
    prof, i = 1, inicio
    while prof:
        ma, mf = abre.search(tpl, i), fecha.search(tpl, i)
        if mf is None:
            raise ValueError("<sc-%s> sem fechamento" % tipo)
        if ma and ma.start() < mf.start():
            prof += 1
            i = ma.end()
        else:
            prof -= 1
            i = mf.end()
            if not prof:
                return tpl[inicio:mf.start()], i
    raise ValueError("bloco malformado")


CHAVES = re.compile(r"\{\{\s*([^}]*?)\s*\}\}")


def interpolar(texto, ctx):
    def troca(m):
        v = resolver(ctx, m.group(1))
        return "" if v is None else str(v)
    return CHAVES.sub(troca, texto)


def renderizar(tpl, ctx):
    saida, i = [], 0
    while True:
        m = ABERTURA.search(tpl, i)
        if not m:
            saida.append(interpolar(tpl[i:], ctx))
            break
        saida.append(interpolar(tpl[i:m.start()], ctx))
        tipo, atributos = m.group(1), m.group(2)
        corpo, fim = bloco(tpl, m.end(), tipo)
        if tipo == "if":
            expr = CHAVES.match(attr(atributos, "value") or "")
            if expr and resolver(ctx, expr.group(1).strip()):
                saida.append(renderizar(corpo, ctx))
        else:
            expr = CHAVES.match(attr(atributos, "list") or "")
            itens = resolver(ctx, expr.group(1).strip()) if expr else None
            nome = attr(atributos, "as") or "item"
            for idx, item in enumerate(itens or []):
                filho = dict(ctx)
                filho[nome] = item
                filho["_i"] = idx
                saida.append(renderizar(corpo, filho))
        i = fim
    return "".join(saida)


# ------------------------------------------------- transformacoes pos-render

def trocar_image_slots(html):
    """<image-slot src fit shape placeholder> -> <img> responsiva."""
    def troca(m):
        interno = m.group(1)
        src = attr(interno, "src") or ""
        alt = attr(interno, "placeholder") or ""
        fit = attr(interno, "fit") or "cover"
        pos = attr(interno, "pos")
        if pos:
            fit += ";object-position:" + pos
        raio = "border-radius:50%;" if (attr(interno, "shape") == "circle") else ""
        if not src:
            # sem imagem definida: mantem o espaco reservado, sem <img> quebrada
            return ('<div aria-label="%s" style="width:100%%;height:100%%;'
                    'background:#e6e3dd"></div>' % alt)
        return ('<img src="%s" alt="%s" loading="lazy" decoding="async" '
                'style="width:100%%;height:100%%;object-fit:%s;%sdisplay:block">'
                % (src, alt, fit, raio))
    return re.sub(r"<image-slot([^>]*)>\s*</image-slot>", troca, html)


def fechar_correspondente(html, inicio, tag):
    """Indice do </tag> que fecha a tag aberta que termina em `inicio`."""
    abre = re.compile(r"<%s\b" % tag)
    fecha = re.compile(r"</%s>" % tag)
    prof, i = 1, inicio
    while prof:
        ma, mf = abre.search(html, i), fecha.search(html, i)
        if mf is None:
            raise ValueError("<%s> sem fechamento" % tag)
        if ma and ma.start() < mf.start():
            prof += 1
            i = ma.end()
        else:
            prof -= 1
            i = mf.end()
            if not prof:
                return mf.start(), mf.end()
    raise ValueError("tag malformada")


# prefixos injetados para que o <a> se comporte como o elemento original.
# vao no inicio do style: qualquer declaracao ja existente sobrescreve.
PREFIXO_A = {
    "button": ("display:inline-flex;align-items:center;justify-content:center;"
               "text-align:center;box-sizing:border-box;text-decoration:none;color:inherit;"),
    "div": "display:block;text-decoration:none;color:inherit;",
}


def trocar_navegacao(html):
    """<button|div data-nav="url"> ... </tag>  ->  <a href="url"> ... </a>"""
    padrao = re.compile(r'<(button|div)\b([^>]*?)\sdata-nav="([^"]*)"([^>]*)>')
    while True:
        m = padrao.search(html)
        if not m:
            return html
        tag, antes, destino, depois = m.groups()
        atributos = (antes + depois).strip()
        atributos = re.sub(r'\saria-label="[^"]*"', "", atributos)

        estilo = attr(atributos, "style") or ""
        atributos = re.sub(r'(?:^|\s)style="[^"]*"', "", atributos, count=1).strip()
        estilo = PREFIXO_A[tag] + estilo

        ini_fecha, fim_fecha = fechar_correspondente(html, m.end(), tag)
        interno = html[m.end():ini_fecha]
        novo = '<a href="%s" %s style="%s">%s</a>' % (
            destino, atributos.strip(), estilo, interno)
        html = html[:m.start()] + novo + html[fim_fecha:]


def extrair_hovers(html):
    """style-hover="..." (atributo do runtime) -> classe CSS com :hover real."""
    estilos, classes = {}, []

    def troca(m):
        regra = m.group(1)
        if regra not in estilos:
            estilos[regra] = "hv%d" % (len(estilos) + 1)
            classes.append(regra)
        return ' data-hv="%s"' % estilos[regra]

    html = re.sub(r'\sstyle-hover="([^"]*)"', troca, html)

    # aplica a classe no atributo class do proprio elemento
    def mover(m):
        interno = m.group(0)
        mh = re.search(r'\sdata-hv="([^"]*)"', interno)
        if not mh:
            return interno
        cls = mh.group(1)
        interno = interno.replace(mh.group(0), "")
        mc = re.search(r'\sclass="([^"]*)"', interno)
        if mc:
            return interno.replace(mc.group(0), ' class="%s %s"' % (mc.group(1), cls))
        return interno[:-1].rstrip() + ' class="%s">' % cls

    html = re.sub(r"<[a-zA-Z][^>]*\sdata-hv=\"[^\"]*\"[^>]*>", mover, html)
    css = "\n".join(".%s:hover{%s}" % (estilos[r], r) for r in classes)
    return html, css


# ------------------------------------------------------------------- montagem


def marcar_secoes(html):
    """Poe class="sec" em cada secao de primeiro nivel da pagina.

    Tudo no arquivo de design usa estilo inline, que vence folha de estilo.
    Sem um gancho de classe nao da para dar respiro lateral no desktop. As
    secoes de sangria (capa e tarjas) ficam de fora: elas posicionam filhos
    em absoluto e padding lateral quebraria o enquadramento.
    """
    # roda sobre o fragmento do corpo, antes de ele entrar no <main>
    i, fim = 0, len(html)
    saida, pos = [html[:i]], i
    abre = re.compile(r"<(div|footer)\b", re.I)
    while True:
        m = abre.search(html, pos)
        if not m or m.start() >= fim:
            break
        saida.append(html[pos:m.start()])
        fim_tag = html.index(">", m.start())
        _, fim_el = fechar_correspondente(html, fim_tag + 1, m.group(1))
        topo = html[m.start():fim_tag + 1]
        estilo = attr(topo, "style") or ""
        if not estilo:
            # invólucro sem estilo (o <div> que o sc-if da tela cria):
            # as secoes de verdade estao um nivel abaixo
            saida.append(topo + marcar_secoes(html[fim_tag + 1:fim_el - len("</%s>" % m.group(1))])
                         + "</%s>" % m.group(1))
            pos = fim_el
            continue
        capa = "position:relative;height:" in estilo
        tarja = "height:26px" in estilo or "height:14px" in estilo
        classe = "sec hero bleed" if capa else ("sec bleed" if tarja else "sec")
        mc = re.search(r'\sclass="([^"]*)"', topo)
        if mc:
            topo = topo.replace(mc.group(0), ' class="%s %s"' % (mc.group(1), classe))
        else:
            topo = topo[:-1].rstrip() + ' class="%s">' % classe
        saida.append(topo + html[fim_tag + 1:fim_el])
        pos = fim_el
    saida.append(html[pos:])
    return "".join(saida)


def fatiar(fonte):
    """Separa cabecalho, telas, rodape e menu do arquivo de origem."""
    ini_header = fonte.index('<div style="position:sticky;top:0;z-index:20;')
    ini_menu = fonte.index('<sc-if value="{{ menuOpen }}"')
    fim_menu = fonte.index("</sc-if>", ini_menu) + len("</sc-if>")

    corpo = fonte[ini_header:ini_menu]
    # o corpo termina com o </div> do container de rolagem do prototipo
    corpo = re.sub(r"<!--.*?-->", "", corpo, flags=re.S).rstrip()
    assert corpo.endswith("</div>"), corpo[-120:]
    corpo = corpo[: corpo.rfind("</div>")]

    menu = fonte[ini_menu:fim_menu]
    menu = menu[menu.index(">") + 1:]           # tira o <sc-if>
    menu = menu[: menu.rindex("</sc-if>")]

    estilo = re.search(r"<style>(.*?)</style>", fonte, re.S).group(1)
    return corpo, menu, estilo


NAV = {
    "goHome": "index.html",
    "goMestre": "mestre.html",
    "goNucleos": "nucleos.html",
    "goAulas": "aulas.html",
    "goEventos": "eventos.html",
    "goGaleria": "galeria.html",
    "scrollExp": "#experimental",
}

PAGINAS = [
    ("index.html",    "home",     "IFÉ — Escola de Capoeira Angola · Recife"),
    ("mestre.html",   "mestre",   "Mestre e Fundadores"),
    ("nucleos.html",  "nucleos",  "Núcleos"),
    ("aulas.html",    "aulas",    "Aulas e horários"),
    ("eventos.html",  "eventos",  "Eventos e agenda"),
    ("galeria.html",  "galeria",  "Galeria"),
]

MENU_ATIVO = []  # preenchido em main() a partir de paginasOcultas

MENU_DEF = [
    ("Início", "home", "index.html"),
    ("Mestre e Fundadores", "mestre", "mestre.html"),
    ("Núcleos", "nucleos", "nucleos.html"),
    ("Aulas", "aulas", "aulas.html"),
    ("Eventos e Agenda", "eventos", "eventos.html"),
    ("Galeria", "galeria", "galeria.html"),
]


def contexto(dados, tela, nucleo=None):
    nucleos = dados["nucleos"]
    # a sede e marcada por campo, nao pela posicao: a ordem da lista e editorial
    sede = next((n for n in nucleos if n.get("sede")), nucleos[0])
    ctx = dict(NAV)
    ctx["toggleMenu"] = "__menu"
    ctx["openSede"] = "nucleo-%s.html" % sede["slug"]
    ctx["stripes"] = True
    ctx["showNextEvent"] = True
    for _, chave, _ in MENU_ATIVO:
        ctx["is" + chave.capitalize()] = (tela == chave)
    ctx["isNucleos"] = (tela == "nucleos")
    ctx["isNucleo"] = (tela == "nucleo")
    ctx["menuOpen"] = True  # o menu vira overlay controlado por CSS/JS

    ctx["menu"] = [
        {"label": rotulo, "go": destino,
         "color": "#3f9b46" if tela == chave else "#ffffff",
         "mark": "●" if tela == chave else "→"}
        for rotulo, chave, destino in MENU_ATIVO
    ]
    ctx["chips"] = [
        {"nome": n["nome"].split(" · ")[0], "open": "nucleo-%s.html" % n["slug"]}
        for n in nucleos if not n.get("sede")
    ]
    ctx["nucleos"] = [dict(n, open="nucleo-%s.html" % n["slug"]) for n in nucleos]
    ctx["pins"] = [
        {"nome": n["pin"], "x": n["x"], "y": n["y"], "open": "nucleo-%s.html" % n["slug"]}
        for n in nucleos
    ]
    for chave in ("horarios", "pilares", "linhagem", "fundadores",
                  "marcos", "turmas"):
        ctx[chave] = dados[chave]
    # o local de cada evento vira link quando tiver mapa (e usado como texto,
    # nunca dentro de atributo, entao pode receber marcacao)
    def _atracoes(texto):
        """Destaca horario e nome. Sem isso a grade do dia vira um bloco corrido
        em que '8h', 'Mestra Tati' e 'Almoco' tem todos o mesmo peso."""
        if not texto:
            return ""
        itens = [i.strip() for i in texto.split("·") if i.strip()]
        hora_re = re.compile(r"^(\d{1,2}h\d{0,2})\s+(.+)$")
        linhas = []
        for it in itens:
            m = hora_re.match(it)
            if m:
                linhas.append(
                    '<span style="display:inline-block;min-width:44px;'
                    'font-weight:700;color:#24632a">' + m.group(1) + '</span>'
                    '<span style="font-weight:600;color:rgba(11,11,11,.85)">'
                    + m.group(2) + '</span>')
            else:
                linhas.append('<span style="font-weight:600;'
                              'color:rgba(11,11,11,.85)">' + it + '</span>')
        if len(linhas) > 2:   # grade de horarios: uma por linha
            return "".join('<div style="padding:1px 0">' + l + '</div>'
                           for l in linhas)
        sep = '<span style="color:rgba(11,11,11,.35)"> · </span>'
        return sep.join(linhas)

    ctx["eventos"] = [
        dict(e,
             nomes=_atracoes(e.get("nomes", "")),
             local=('<a href="%s" target="_blank" rel="noopener" '
                    'style="color:inherit">%s</a>' % (e["mapa"], e["local"]))
             if e.get("mapa") else e["local"])
        for e in dados["eventos"]]
    ctx["faqs"] = [
        dict(f, open=True, icon="+", toggle="__faq%d" % i)
        for i, f in enumerate(dados["faqs"])
    ]
    n = nucleo or sede
    ctx["nucleoNome"] = n["nome"]
    ctx["nucleoTag"] = n["tag"]
    ctx["nucleoProf"] = n["prof"]
    ctx["nucleoEndereco"] = n["end"]
    return ctx


CSS_BASE = """
*{-webkit-tap-highlight-color:transparent}
html{-webkit-text-size-adjust:100%%}
body{margin:0;background:#dcd9d3;font-family:"Figtree",system-ui,-apple-system,sans-serif;
     --color-bg:#ffffff;--color-surface:#f4f2ee;--color-text:#0b0b0b;--color-accent:#3f9b46;
     --color-accent-600:#34803a;--color-accent-700:#24632a;--color-divider:rgba(11,11,11,.14)}
a{color:#24632a;text-underline-offset:3px}
img{max-width:100%%}
.site{max-width:%(w)dpx;margin:0 auto;background:#ffffff;color:#0b0b0b;min-height:100vh;
      position:relative;isolation:isolate}
@media (min-width:%(w2)dpx){.site{box-shadow:0 0 80px rgba(11,11,11,.22)}}

/* menu: overlay real, sem depender de runtime */
.menu{position:fixed;inset:0;z-index:60;display:none;background:rgba(11,11,11,.55)}
.menu.aberto{display:block}
/* o painel do menu traz inset:0 inline (heranca do prototipo): precisa de
   !important para virar coluna centrada em vez de colar na borda esquerda */
.menu > div{position:fixed!important;inset:0 auto 0 50%%!important;
            width:100%%!important;max-width:%(w)dpx!important;
            transform:translateX(-50%%)!important}
body.travado{overflow:hidden}

/* acordeao do FAQ, antes controlado por estado do prototipo */
.faq-r{display:none}
.faq.aberto .faq-r{display:block}

/* rolagem horizontal das galerias sem barra visivel */
.zs{scrollbar-width:none}
.zs::-webkit-scrollbar{width:0;height:0}

:focus-visible{outline:2px solid #3f9b46;outline-offset:2px}
@media (prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
html{scroll-behavior:smooth}

/* ---------- telas maiores ----------
   O arquivo de design so previa celular e tudo usa estilo inline, que vence
   folha de estilo. Por isso os ajustes abaixo usam !important: e a unica
   forma de sobrepor os valores embutidos em cada elemento. */
.nav-desk{display:none}

@media (min-width:820px){
  .site{max-width:720px}
  .sec:not(.bleed){padding-left:44px!important;padding-right:44px!important}
}

@media (min-width:1120px){
  .site{max-width:1180px}
  /* respiro lateral: o conteudo fica em ~840px, o fundo ocupa a largura toda.
     As secoes .bleed ficam de fora porque posicionam filhos em absoluto. */
  .sec:not(.bleed){padding-left:170px!important;padding-right:170px!important}
  /* so a capa cresce; as tarjas de zebra mantem a altura original */
  .sec.hero{height:520px!important}
  /* o texto e os botoes da capa acompanham o mesmo respiro das secoes */
  .sec.hero > div[style*="bottom:0"]{padding-left:170px!important;
    padding-right:170px!important;padding-bottom:40px!important}
  .sec.hero > div[style*="bottom:0"] > div[style*="display:flex"]{max-width:440px}

  /* barra de navegacao no lugar do menu sanduiche */
  .nav-desk{display:flex;gap:24px;align-items:center}
  .nav-desk a{color:rgba(255,255,255,.75);text-decoration:none;font-size:13px;
              letter-spacing:.02em;white-space:nowrap}
  .nav-desk a:hover{color:#ffffff}
  .nav-desk a[aria-current="page"]{color:#3f9b46}
  .menu-btn{display:none!important}

  /* a linha de texto nao deve atravessar a tela inteira */
  .sec p, .sec > div > p{max-width:66ch}

  /* galeria em tres colunas */
  .grade-galeria{grid-template-columns:1fr 1fr 1fr!important}
  .grade-galeria > div{height:240px!important}
  .grade-galeria > div[style*="span 2"]{grid-column:span 3!important;height:420px!important}

  /* o cartaz e retrato: limitar a largura evita corte agressivo */
  .cartaz{max-width:460px;height:600px!important}

  /* rodape em quatro colunas */
  .rodape-cols{grid-template-columns:1.2fr 1fr 1fr!important;gap:32px!important}
}

@media (min-width:1400px){
  .site{max-width:1320px}
  .sec:not(.bleed){padding-left:240px!important;padding-right:240px!important}
}
"""

JS = """
(function(){
  var m=document.getElementById('menu');
  window.alternarMenu=function(e){
    if(e)e.preventDefault();
    var abriu=m.classList.toggle('aberto');
    document.body.classList.toggle('travado',abriu);
  };
  if(m)m.addEventListener('click',function(e){if(e.target===m)alternarMenu();});
  document.addEventListener('keydown',function(e){
    if(e.key==='Escape'&&m&&m.classList.contains('aberto'))alternarMenu();
  });
  var ini=document.querySelector('.faq.aberto .faq-i');
  if(ini)ini.textContent='\\u2013';
  if(matchMedia('(prefers-reduced-motion: reduce)').matches){
    document.querySelectorAll('video[autoplay]').forEach(function(v){
      v.removeAttribute('autoplay');v.pause();
    });
  }
  var faixa=document.querySelector('[data-carrossel]');
  if(faixa&&!matchMedia('(prefers-reduced-motion: reduce)').matches){
    var pausaAte=0,visivel=true;
    var pausar=function(){pausaAte=Date.now()+9000;};
    ['pointerdown','touchstart','wheel','mouseenter','focusin'].forEach(function(ev){
      faixa.addEventListener(ev,pausar,{passive:true});
    });
    if(window.IntersectionObserver){
      new IntersectionObserver(function(es){visivel=es[0].isIntersecting;},
        {threshold:0.35}).observe(faixa);
    }
    setInterval(function(){
      if(!visivel||document.hidden||Date.now()<pausaAte)return;
      var cs=faixa.children;if(cs.length<2)return;
      var base=cs[0].offsetLeft,alvo=0;
      for(var i=0;i<cs.length;i++){
        var x=cs[i].offsetLeft-base;
        if(x>faixa.scrollLeft+8){alvo=x;break;}
      }
      if(faixa.scrollLeft+faixa.clientWidth>=faixa.scrollWidth-8)alvo=0;
      faixa.scrollTo({left:alvo,behavior:'smooth'});
    },4000);
  }
  document.querySelectorAll('[data-faq]').forEach(function(b){
    b.addEventListener('click',function(e){
      e.preventDefault();
      var c=b.closest('.faq'),aberto=c.classList.contains('aberto');
      document.querySelectorAll('.faq').forEach(function(o){
        o.classList.remove('aberto');
        var i=o.querySelector('.faq-i'); if(i)i.textContent='+';
      });
      if(!aberto){c.classList.add('aberto');
        var i=c.querySelector('.faq-i'); if(i)i.textContent='\\u2013';}
    });
  });
})();
"""

PAGINA = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>%(titulo)s</title>
<meta name="description" content="%(descricao)s">
<meta name="theme-color" content="#0b0b0b">
<link rel="canonical" href="%(canonical)s">
<link rel="icon" href="logo-ife.jpg">
<link rel="apple-touch-icon" href="logo-ife.jpg">
<meta property="og:type" content="website">
<meta property="og:site_name" content="%(nome_completo)s">
<meta property="og:title" content="%(titulo)s">
<meta property="og:description" content="%(descricao)s">
<meta property="og:image" content="%(base)s/compartilhar.jpg">
<meta property="og:image:type" content="image/jpeg">
<meta property="og:image:width" content="1000">
<meta property="og:image:height" content="1000">
<meta property="og:image:alt" content="Brasão da Escola de Capoeira Angola IFÉ">
<meta property="og:locale" content="pt_BR">
<meta name="twitter:card" content="summary">
<meta name="twitter:image" content="%(base)s/compartilhar.jpg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Caprasimo&family=Figtree:wght@400;500;600;700;800&display=swap">
<link rel="stylesheet" href="__ESTILO__">
</head>
<body>
<main class="site">
%(corpo)s
</main>
<div class="menu" id="menu">
%(menu)s
</div>
<script src="__APP__" defer></script>
</body>
</html>
"""


def preparar(fragmento):
    """Trocas feitas no template antes de renderizar."""
    # onClick de estado -> data-nav (vira href depois da interpolacao)
    fragmento = fragmento.replace("onClick=", "data-nav=")
    fragmento = fragmento.replace(
        '<div style="height:430px;border-radius:20px;overflow:hidden;margin-bottom:18px">',
        '<div class="cartaz" style="height:430px;border-radius:20px;'
        'overflow:hidden;margin-bottom:18px">')
    # a programacao traz artistas e mestres por dia; o card ganha uma linha
    fragmento = fragmento.replace('<div style="font-size:12.5px;color:rgba(11,11,11,.55);margin-top:3px">{{ e.local }}</div>', '<div style="font-size:12.5px;line-height:1.5;color:rgba(11,11,11,.72);margin-top:6px">{{ e.nomes }}</div><div style="font-size:12.5px;color:rgba(11,11,11,.55);margin-top:3px">{{ e.local }}</div>')
    fragmento = fragmento.replace(
        '<image-slot id="{{ f.slot }}" src="{{ f.foto }}" shape="rect" fit="cover"',
        '<image-slot id="{{ f.slot }}" src="{{ f.foto }}" pos="{{ f.pos }}" '
        'shape="rect" fit="cover"')
    fragmento = fragmento.replace(">Mapa \u00b7 placeholder<", ">Onde estamos<")
    # O arquivo de origem abre <sc-if showNextEvent> e nunca fecha: o runtime do
    # prototipo tolerava, HTML de verdade nao. Fecha logo apos o bloco do evento.
    marca = fragmento.find(">O que a roda ensina<")
    if marca > 0:
        ini = fragmento.rfind('<div style="padding:34px 20px 8px', 0, marca)
        if ini > 0:
            fragmento = fragmento[:ini] + "</sc-if>\n" + fragmento[ini:]

    # Evento antes da galeria (no arquivo de design ele vinha depois).
    abre = fragmento.find('<sc-if value="{{ showNextEvent }}"')
    galeria = '<div style="padding:30px 0 34px;background:#ffffff">'
    if abre > 0 and galeria in fragmento:
        fecha = fragmento.index("</sc-if>", abre) + len("</sc-if>")
        bloco_evento = fragmento[abre:fecha]
        fragmento = fragmento[:abre] + fragmento[fecha:]
        g = fragmento.index(galeria)
        fragmento = fragmento[:g] + bloco_evento + "\n\n          " + fragmento[g:]

    # Texto de apresentacao completo, logo abaixo da capa. Os cinco paragrafos
    # nao cabem sobre a foto: a capa tem 430px e ainda leva os botoes.
    abre2 = fragmento.find('<sc-if value="{{ showNextEvent }}"')
    if abre2 > 0:
        fragmento = fragmento[:abre2] + '<div style="padding:34px 20px 36px;background:#ffffff">\n            <p style="margin:0 0 16px;font-size:16px;line-height:1.65;color:rgba(11,11,11,.86)">Somos a Escola de Capoeira Angola Ifé, sob a guiança e coordenação do Mestre Baygon.</p>\n            <p style="margin:0 0 15px;font-size:15px;line-height:1.7;color:rgba(11,11,11,.72)">Vivemos e compartilhamos a Capoeira Angola no chão, no canto e na roda, com respeito por quem veio antes e compromisso com quem virá depois.</p>\n            <p style="margin:0 0 15px;font-size:15px;line-height:1.7;color:rgba(11,11,11,.72)">Recebemos a tradição como herança viva: preservamos suas raízes, ressignificamos seus caminhos e mantemos a roda em movimento.</p>\n            <p style="margin:0 0 15px;font-size:15px;line-height:1.7;color:rgba(11,11,11,.72)">Nosso exercício é também enfrentar as marcas das opressões coloniais e construir outros modos de existir, aprender e conviver — com uma perspectiva decolonial, inclusiva e diversa.</p>\n            <p style="margin:0;font-size:15.5px;line-height:1.65;font-weight:600;color:rgba(11,11,11,.88)">Porque a Capoeira que acreditamos é aquela que honra a ancestralidade, acolhe a diferença e abre caminhos para o futuro.</p>\n          </div>\n\n          ' + fragmento[abre2:]

    # No bloco do evento, "O Mestre" da lugar a "Programacao" (leva a agenda).
    fragmento = fragmento.replace(
        'data-nav="{{ goMestre }}" style="min-height:48px;padding:0 18px;'
        'border:1px solid rgba(255,255,255,.42)',
        'data-nav="{{ goEventos }}" style="min-height:48px;padding:0 18px;'
        'border:1px solid rgba(255,255,255,.42)')
    fragmento = fragmento.replace(">O Mestre</button>", ">Programação</button>")
    # botao secundario da capa: Nucleos -> Eventos
    fragmento = fragmento.replace(
        'data-nav="{{ goNucleos }}" style="min-height:48px;padding:0 18px;'
        'border:1px solid rgba(255,255,255,.5);border-radius:999px;'
        'background:transparent;color:#ffffff;font-family:\'Caprasimo\',system-ui;'
        'font-size:14.5px;cursor:pointer" style-hover="background:rgba(255,255,255,.14)">Núcleos<',
        'data-nav="{{ goEventos }}" style="min-height:48px;padding:0 18px;'
        'border:1px solid rgba(255,255,255,.5);border-radius:999px;'
        'background:transparent;color:#ffffff;font-family:\'Caprasimo\',system-ui;'
        'font-size:14.5px;cursor:pointer" style-hover="background:rgba(255,255,255,.14)">Eventos<')

    return fragmento


def pos_processar(html, dados, nucleo=None, ctx_atual=None):
    # trocas de texto declaradas em conteudo.json (o texto vem do .dc.html)
    for antes, depois in (dados.get("substituicoes") or {}).items():
        if not antes.startswith("_"):
            html = html.replace(antes, depois)
    html = trocar_image_slots(html)

    # botao de menu e itens do FAQ: comportamento local, nao navegacao
    html = html.replace('data-nav="__menu"', 'href="#menu" onclick="alternarMenu(event)"')
    html = re.sub(r'data-nav="__faq(\d+)"', r'data-faq="\1"', html)

    html = trocar_navegacao(html)

    # marca os blocos do FAQ para o acordeao (o primeiro comeca aberto)
    partes = html.split('<div style="border-radius:20px;background:#f4f2ee;overflow:hidden">')
    if len(partes) > 1:
        montado = [partes[0]]
        for i, p in enumerate(partes[1:]):
            classe = "faq aberto" if i == 0 else "faq"
            montado.append('<div class="%s" style="border-radius:20px;'
                           'background:#f4f2ee;overflow:hidden">%s' % (classe, p))
        html = "".join(montado)
    html = html.replace(
        '<span style="flex:none;width:26px;height:26px;border-radius:50%;background:#0b0b0b;'
        'color:#3f9b46;display:flex;align-items:center;justify-content:center;font-size:14px">+</span>',
        '<span class="faq-i" style="flex:none;width:26px;height:26px;border-radius:50%;'
        'background:#0b0b0b;color:#3f9b46;display:flex;align-items:center;'
        'justify-content:center;font-size:14px">+</span>')
    html = html.replace(
        '<div style="padding:0 16px 18px;font-size:13.5px;line-height:1.6;color:rgba(11,11,11,.68)">',
        '<div class="faq-r" style="padding:0 16px 18px;font-size:13.5px;'
        'line-height:1.6;color:rgba(11,11,11,.68)">')

    # CTA de aula experimental -> formulario real ja usado no design
    # (ordem: formulario > whatsapp > instagram)
    zap = (dados["site"].get("whatsapp") or "").strip()
    # "Aula experimental" fala com a escola. O formulario do Google e a inscricao
    # do Meu Patua e so vale para os botoes do evento.
    destino = (dados["site"].get("contatoAula")
               or ("https://wa.me/%s" % re.sub(r"\D", "", zap) if zap else None)
               or dados["site"]["instagram"])
    # o <a> precisa dos mesmos alinhamentos que o <button> tinha por padrao;
    # sem isso o rotulo fica no canto e o link aparece sublinhado
    centrado_cta = ("display:flex;align-items:center;justify-content:center;"
                    "text-align:center;box-sizing:border-box;text-decoration:none;")
    html = re.sub(
        r'<button style="(min-height:52px;[^"]*)"([^>]*)>([^<]*)</button>',
        lambda m: ('<a href="' + destino + '" target="_blank" rel="noopener" style="'
                   + centrado_cta + m.group(1) + '"' + m.group(2) + '>'
                   + m.group(3) + '</a>'),
        html)

    # campos que nao enviavam nada (o prototipo nao tinha backend): removidos,
    # o CTA acima leva ao formulario de verdade.
    html = re.sub(r'<input class="input"[^>]*>\s*', "", html)
    # a linha "Sua cidade ou bairro" some junto; o botao redondo vira link largo
    html = html.replace(
        '<div style="display:flex;gap:8px;margin-bottom:16px">\n              \n            </div>',
        "")

    # CTAs da pagina de nucleo: no prototipo eram botoes sem acao nenhuma.
    # viram links reais para contato e para o mapa do endereco.
    if nucleo:
        centrado = ("display:inline-flex;align-items:center;justify-content:center;"
                    "text-decoration:none;box-sizing:border-box;color:inherit;")
        zap_n = (nucleo.get("whatsapp") or "").strip() or zap
        if zap_n:
            contato, rotulo = "https://wa.me/%s" % re.sub(r"\D", "", zap_n), "WhatsApp do núcleo"
        else:
            contato, rotulo = dados["site"]["instagram"], "Falar com o núcleo"

        def link(m, href, texto, extra=""):
            estilo = m.group(1)
            return ('<a href="%s" target="_blank" rel="noopener"%s style="%s%s">%s</a>'
                    % (href, extra, centrado, estilo, texto))

        html = re.sub(
            r'<button style="(flex:1;min-height:50px;[^"]*)"[^>]*>WhatsApp do n[^<]*</button>',
            lambda m: link(m, contato, rotulo), html)

        mapa = nucleo.get("mapa") or ("https://www.google.com/maps/search/?api=1&query="
                                      + urllib.parse.quote(nucleo["end"].strip()))
        html = re.sub(
            r'<button style="(width:50px;height:50px;[^"]*)"[^>]*>\u2197</button>',
            lambda m: link(m, mapa, "\u2197", ' aria-label="Ver no mapa"'), html)

    # Video na capa, no lugar da foto. Toca mudo e em laco (autoplay so e
    # permitido sem audio); a foto vira poster, aparecendo enquanto carrega.
    vid = dados["site"].get("videoCapa")
    if vid:
        m_capa = re.search(r'<img src="(fotos/roda-quadra[^"]*)"[^>]*'
                           r'object-position:([^;]*);[^>]*>', html)
        if m_capa:
            poster, pos_capa = m_capa.group(1), m_capa.group(2)
            html = html[:m_capa.start()] + (
                '<video src="' + vid + '" poster="' + poster + '" autoplay muted loop '
                'playsinline preload="metadata" aria-label="Roda na sede" '
                'style="width:100%;height:100%;object-fit:cover;object-position:'
                + pos_capa + ';display:block"></video>') + html[m_capa.end():]

    # A pagina Galeria e montada a partir da lista em conteudo.json, em vez dos
    # seis espacos fixos do arquivo de design (que nao comportavam as fotos novas).
    grade = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">'
    grade_cls = grade[:-1] + ' class="grade-galeria">'
    if grade in html and dados.get("galeria"):
        ini = html.index(grade)
        _, fim = fechar_correspondente(html, ini + len(grade), "div")
        celulas = []
        for foto in dados["galeria"]:
            largo = foto.get("tamanho") == "largo"
            moldura = ("grid-column:span 2;height:300px;border-radius:20px"
                       if largo else "height:150px;border-radius:18px")
            celulas.append(
                '<div style="%s;overflow:hidden;filter:grayscale(1) contrast(1.1)">'
                '<img src="%s" alt="%s" loading="lazy" decoding="async" '
                'style="width:100%%;height:100%%;object-fit:cover;'
                'object-position:%s;display:block"></div>'
                % (moldura, foto["src"], foto["alt"], foto.get("pos", "center center")))
        html = html[:ini] + grade_cls + "\n" + "\n".join(celulas) + "\n</div>" + html[fim:]

    # A faixa "A roda por dentro" da home vem da mesma lista da Galeria, para as
    # duas nao sairem do ar desencontradas quando as fotos mudarem.
    faixa = ('<div class="zs" style="display:flex;gap:10px;overflow-x:auto;'
             'padding:0 20px 4px;scrollbar-width:none">')
    faixa_auto = faixa[:-1] + ' data-carrossel>'
    if faixa in html and dados.get("galeria"):
        ini = html.index(faixa)
        _, fim = fechar_correspondente(html, ini + len(faixa), "div")
        cartoes = []
        porsrc = {f["src"]: f for f in dados["galeria"]}
        escolhidas = [porsrc[s] for s in dados.get("destaquesHome", []) if s in porsrc] \
            or dados["galeria"][:6]
        for i, foto in enumerate(escolhidas[:6]):
            pos = foto.get("pos", "center center")
            img = ('<img src="%s" alt="%s" loading="lazy" decoding="async" '
                   'style="width:100%%;height:100%%;object-fit:cover;'
                   'object-position:%s;display:block">' % (foto["src"], foto["alt"], pos))
            if i == 0:
                # o primeiro cartao e maior e leva a legenda por cima
                cartoes.append(
                    '<a href="galeria.html" style="display:block;text-decoration:none;'
                    'color:inherit;position:relative;flex:none;width:230px;height:290px;'
                    'border-radius:22px;overflow:hidden;background:#0b0b0b">'
                    '<div style="position:absolute;inset:0;filter:grayscale(1) contrast(1.12)">'
                    '%s</div>'
                    '<span style="position:absolute;left:12px;bottom:12px;font-size:11px;'
                    'font-weight:700;color:#ffffff;background:rgba(11,11,11,.7);'
                    'padding:4px 10px;border-radius:999px">%s</span></a>'
                    % (img, foto["alt"]))
            else:
                cartoes.append(
                    '<a href="galeria.html" style="display:block;text-decoration:none;'
                    'color:inherit;flex:none;width:180px;height:290px;border-radius:22px;'
                    'overflow:hidden;filter:grayscale(1) contrast(1.1)">%s</a>' % img)
        html = html[:ini] + faixa_auto + "\n" + "\n".join(cartoes) + "\n</div>" + html[fim:]

    # Rodape reconstruido: o do arquivo de design tinha so logo, endereco e um
    # botao, deixando o fim da pagina sem saida. Agora leva navegacao, horarios,
    # contato e assinatura. Montado por concatenacao (o CSS tem "%" demais para
    # conviver com formatacao de string).
    ab = '<div style="padding:30px 20px 34px;background:#0b0b0b;color:rgba(255,255,255,.7)">'
    if ab in html:
        ini_r = html.index(ab)
        _, fim_r = fechar_correspondente(html, ini_r + len(ab), "div")
        antigo = html[ini_r:fim_r]
        t0 = antigo.index('<div style="height:14px;background-image:')
        tarja = antigo[t0:antigo.index("></div>", t0) + len("></div>")]

        site = dados["site"]
        rot = ('font-size:10px;letter-spacing:.2em;text-transform:uppercase;'
               'color:rgba(255,255,255,.42);margin-bottom:10px')
        lnk = ('display:block;color:#ffffff;text-decoration:none;font-size:13.5px;'
               'line-height:1.45;padding:3px 0')
        pil = ('display:inline-flex;align-items:center;gap:8px;font-size:12.5px;'
               'font-weight:600;padding:10px 16px;border-radius:999px;'
               'text-decoration:none;box-sizing:border-box')

        nav = "".join('<a href="' + d + '" style="' + lnk + '">' + r + '</a>'
                      for r, _, d in MENU_ATIVO)
        hor = "".join('<div style="font-size:13.5px;line-height:1.45;padding:3px 0;'
                      'color:#ffffff">' + h["dia"] +
                      '<span style="color:rgba(255,255,255,.55)"> \u00b7 ' + h["hora"] +
                      '</span></div>' for h in dados["horarios"])
        # alfinete de mapa, no mesmo tracado do icone do Instagram ja usado aqui
        pin = ('<svg width="15" height="15" viewBox="0 0 24 24" fill="none" '
               'stroke="currentColor" stroke-width="2.4" stroke-linecap="round" '
               'stroke-linejoin="round" aria-hidden="true" '
               'style="flex:none;margin-top:2px">'
               '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>'
               '<circle cx="12" cy="10" r="3"></circle></svg>')
        lnk_mapa = ('display:flex;align-items:flex-start;gap:7px;color:#ffffff;'
                    'text-decoration:none;font-size:13.5px;line-height:1.45;padding:3px 0')
        if site.get("mapaSede"):
            end = ('<a href="' + site["mapaSede"] + '" target="_blank" rel="noopener" '
                   'title="Abrir no Google Maps" style="' + lnk_mapa + '">'
                   + pin + '<span>' + site["sede"] + '</span></a>')
        else:
            end = ('<div style="' + lnk_mapa + '">' + pin
                   + '<span>' + site["sede"] + '</span></div>')
        inscricao = (site.get("contatoAula")
                     or ("https://wa.me/" + re.sub(r"\D", "", zap) if zap else None)
                     or site["instagram"])

        p = ['<footer style="padding:30px 20px 26px;background:#0b0b0b;'
             'color:rgba(255,255,255,.7)">', tarja,
             '<div style="display:flex;align-items:center;gap:13px;margin-bottom:26px">'
             '<img src="logo-ife.jpg" alt="" style="width:56px;height:56px;'
             'border-radius:50%;object-fit:cover;background:#ffffff;flex:none">'
             "<div><div style=\"font-family:'Caprasimo',system-ui;font-size:19px;"
             'color:#ffffff;text-transform:uppercase;letter-spacing:-.01em;'
             'line-height:1.05">Escola de Capoeira<br>Angola IF\u00c9</div>'
             '<div style="font-size:10.5px;letter-spacing:.18em;text-transform:uppercase;'
             'color:#3f9b46;margin-top:7px">Mestre Baygon</div></div></div>',
             '<div class="rodape-cols" style="display:grid;'
             'grid-template-columns:1fr 1fr;gap:26px 18px;margin-bottom:26px">',
             '<div><div style="' + rot + '">Navega\u00e7\u00e3o</div>' + nav + '</div>',
             '<div><div style="' + rot + '">Treinos</div>' + hor +
             '<div style="' + rot + ';margin-top:20px">Sede</div>' + end + '</div>',
             '</div>',
             '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:24px">'
             '<a href="' + site["instagram"] + '" target="_blank" rel="noopener" style="'
             + pil + ';border:1px solid rgba(255,255,255,.24);color:#ffffff">'
             + site["instagramHandle"] + '</a>'
             '<a href="' + inscricao + '" target="_blank" rel="noopener" style="'
             + pil + ';background:#3f9b46;color:#0b0b0b;border:0">Aula experimental</a>'
             '</div>',
             '<div style="border-top:1px solid rgba(255,255,255,.12);padding-top:16px;'
             'font-size:11.5px;line-height:1.6;color:rgba(255,255,255,.4)">\u00a9 '
             + site.get("ano", "") + ' Escola de Capoeira Angola IF\u00c9 \u00b7 '
             + site.get("cidade", "") + '</div>',
             '</footer>']
        html = html[:ini_r] + "".join(p) + html[fim_r:]

    for vazio in ('<div style="font-size:12.5px;line-height:1.5;color:rgba(11,11,11,.72);margin-top:6px"></div>',
                  '<div style="font-size:12.5px;color:rgba(11,11,11,.55);margin-top:3px"></div>'):
        html = html.replace(vazio, "")

    # campos vazios da ficha de fundador nao devem virar espaco em branco
    for vazio in ('<div style="font-size:12px;color:rgba(11,11,11,.5);margin-bottom:10px"></div>',
                  '<div style="font-size:13.5px;line-height:1.55;color:rgba(11,11,11,.7)"></div>'):
        html = html.replace(vazio, "")

    # Navegacao horizontal para telas grandes. No celular continua o menu
    # sanduiche; esta barra so aparece a partir de 1120px.
    cab = '<a href="#menu" onclick="alternarMenu(event)"'
    cab_btn = '<button href="#menu" onclick="alternarMenu(event)"'
    for marca_btn in (cab_btn, cab):
        if marca_btn in html:
            itens = "".join('<a href="%s"%s>%s</a>'
                            % (d, ' aria-current="page"' if ctx_atual == c else "", r)
                            for r, c, d in MENU_ATIVO)
            html = html.replace(marca_btn,
                                '<nav class="nav-desk">' + itens + '</nav>'
                                + marca_btn.replace("<button", '<button class="menu-btn"')
                                           .replace('<a href="#menu"',
                                                    '<a class="menu-btn" href="#menu"'), 1)
            break

    # enderecos viram links de mapa
    sede, muafro = dados["site"].get("mapaSede"), dados["site"].get("mapaMuafro")
    if sede:
        html = html.replace(
            "Sede: Rua da União, 287 — Recife/PE",
            'Sede: <a href="%s" target="_blank" rel="noopener" '
            'style="color:#ffffff">Rua da União, 287 — Recife/PE</a>' % sede)
    if sede and muafro:
        html = html.replace(
            ">Sede ECAI · MUAFRO · Marco Zero<",
            '><a href="%s" target="_blank" rel="noopener" style="color:inherit">Sede ECAI</a>'
            ' · <a href="%s" target="_blank" rel="noopener" style="color:inherit">MUAFRO</a>'
            ' · Marco Zero<' % (sede, muafro))

    # primeira imagem da pagina carrega com prioridade (LCP)
    html = html.replace('loading="lazy"', "", 1)
    return html


def main():
    if not os.path.exists(ORIGEM):
        sys.exit("nao encontrei %s" % ORIGEM)
    fonte = ler(ORIGEM)
    dados = json.loads(ler(CONTEUDO))
    corpo_tpl, menu_tpl, estilo_origem = fatiar(fonte)
    corpo_tpl, menu_tpl = preparar(corpo_tpl), preparar(menu_tpl)

    site = dados["site"]
    base = site["url"].rstrip("/")

    if os.path.isdir(SAIDA):
        shutil.rmtree(SAIDA)
    os.makedirs(SAIDA)

    # paginas escondidas saem do menu, do sitemap e nem chegam a ser geradas
    global MENU_ATIVO
    ocultas = set(dados.get("paginasOcultas", []))
    MENU_ATIVO = [m for m in MENU_DEF if m[1] not in ocultas]
    if ocultas:
        print("ocultas:", ", ".join(sorted(ocultas)))

    alvos = [(arq, tela, tit, None) for arq, tela, tit in PAGINAS
             if tela not in ocultas]
    alvos += [("nucleo-%s.html" % n["slug"], "nucleo",
               "%s — Núcleo" % n["nome"].split(" · ")[0], n)
              for n in dados["nucleos"]]

    css_hover = ""
    paginas = []
    for arquivo, tela, titulo, nucleo in alvos:
        ctx = contexto(dados, tela, nucleo)
        corpo = marcar_secoes(pos_processar(renderizar(corpo_tpl, ctx), dados, nucleo, tela))
        menu = pos_processar(renderizar(menu_tpl, ctx), dados)
        corpo, c1 = extrair_hovers(corpo)
        menu, c2 = extrair_hovers(menu)
        css_hover = c1 + "\n" + c2  # mesmo conjunto em todas as paginas

        if tela == "home":
            titulo_final = titulo
            descricao = site["descricao"]
        else:
            titulo_final = "%s — %s" % (titulo, site["nomeCompleto"])
            descricao = "%s · %s" % (titulo, site["descricao"])

        html = PAGINA % {
            "titulo": titulo_final,
            "descricao": descricao,
            "canonical": "%s/%s" % (base, "" if arquivo == "index.html" else arquivo),
            "nome_completo": site["nomeCompleto"],
            "base": base,
            "corpo": corpo,
            "menu": menu,
        }
        paginas.append((arquivo, html))

    # Nome com hash do conteudo: o HTML vai sem cache, mas CSS e JS ficam
    # guardados. Sem isso um navegador podia juntar HTML novo com CSS velho e
    # exibir a pagina quebrada ate o cache vencer.
    css = (CSS_BASE % {"w": LARGURA_MAX, "w2": LARGURA_MAX + 40}) + "\n" + css_hover
    def versionado(nome, ext, conteudo):
        h = hashlib.sha1(conteudo.encode("utf-8")).hexdigest()[:8]
        arq = "%s.%s.%s" % (nome, h, ext)
        with open(os.path.join(SAIDA, arq), "w", encoding="utf-8") as f:
            f.write(conteudo)
        return arq

    nome_css = versionado("estilo", "css", css)
    nome_js = versionado("app", "js", JS)
    for arquivo, html in paginas:
        html = html.replace("__ESTILO__", nome_css).replace("__APP__", nome_js)
        with open(os.path.join(SAIDA, arquivo), "w", encoding="utf-8") as f:
            f.write(html)

    # imagens locais referenciadas por qualquer pagina gerada
    referencias = set()
    for arquivo, _, _, _ in alvos:
        html_gerado = ler(os.path.join(SAIDA, arquivo))
        referencias |= set(re.findall(r'src="([^":]+)"', html_gerado))
        referencias |= set(re.findall(r"url\('((?!data:)[^':]+)'\)", html_gerado))
        referencias |= set(re.findall(r'poster="([^":]+)"', html_gerado))
    referencias.add("compartilhar.jpg")  # so citada em <meta>, nao em <img>
    gerados = {nome_css, nome_js}
    copiadas = 0
    for rel in sorted(referencias):
        if rel in gerados or not os.path.exists(os.path.join(RAIZ, rel)):
            continue
        destino_img = os.path.join(SAIDA, rel)
        pasta = os.path.dirname(destino_img)
        if pasta and not os.path.isdir(pasta):
            os.makedirs(pasta)
        shutil.copy(os.path.join(RAIZ, rel), destino_img)
        copiadas += 1

    # robots + sitemap
    with open(os.path.join(SAIDA, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n" % base)
    urls = "".join(
        "  <url><loc>%s/%s</loc></url>\n" % (base, "" if a == "index.html" else a)
        for a, _, _, _ in alvos)
    with open(os.path.join(SAIDA, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                '%s</urlset>\n' % urls)

    print("gerado: %d paginas, %d imagens em dist/" % (len(alvos), copiadas))
    for arquivo, _, _, _ in alvos:
        print("  ", arquivo)


if __name__ == "__main__":
    main()
