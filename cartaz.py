#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reescreve a frase dentro do oval do cartaz do Meu Patua.

O texto original esta achatado no PNG, entao nao da para "editar" de verdade:
o que este script faz e (1) apagar as duas linhas cobrindo-as com a propria
textura de palha do oval e (2) redesenhar a frase nova em Oswald Bold, que e
a fonte mais proxima da original entre as testadas.

Uso:  python3 cartaz.py "A CAPOEIRA E SIMPLES," "SO BASTA TER AMOR."
"""

import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

RAIZ = os.path.dirname(os.path.abspath(__file__))
# sempre parte do cartaz intacto, para o script poder rodar de novo
ORIGEM = os.path.join(RAIZ, "evento-meu-patua.original.png")
SAIDA = os.path.join(RAIZ, "evento-meu-patua.png")
FONTE = os.path.join(RAIZ, "_fontes", "Oswald.ttf")

# medidas lidas do proprio cartaz (ver README abaixo)
COR_TEXTO = (70, 71, 37)
CAIXA_ALTA = 52          # altura da caixa alta original, em px
BASE_1, BASE_2 = 757, 846  # linhas de base das duas linhas
CENTRO_X = 525           # centro horizontal do oval
LARGURA_MAX = 470        # limite para nao encostar na costura vermelha

# janelas onde procurar palha limpa; o recorte exato e calculado em faixa_limpa
JANELAS = [(648, 682), (862, 896)]  # longe dos acentos das duas linhas
# area onde o texto vive (o que estiver fora disso nao e tocado)
AREA = (280, 683, 800, 862)


def eh_costura(p):
    # a costura e vinho escuro (r-g ~57, verde ~92); a palha e bege clara
    # (r-g ~19, verde ~205). Testar so "r maior que g" confundia as duas.
    r, g, b = p
    return r - g > 35 and g < 160


def faixa_limpa(im, y0, y1):
    """Maior retangulo em y0..y1 sem costura vermelha nem tinta do texto.
    Calculado em vez de fixado: a costura e uma curva, entao uma faixa que
    parece limpa numa linha encosta nela algumas linhas acima ou abaixo."""
    pi = im.load()
    esq, dir_ = 0, im.width
    for y in range(y0, y1):
        e, d = CENTRO_X, CENTRO_X
        while e > 100 and not (eh_costura(pi[e - 1, y]) or eh_tinta(pi[e - 1, y])):
            e -= 1
        while d < im.width - 100 and not (eh_costura(pi[d, y]) or eh_tinta(pi[d, y])):
            d += 1
        esq, dir_ = max(esq, e), min(dir_ if dir_ else d, d)
    return (y0, y1, esq + 3, dir_ - 3)


def eh_tinta(p):
    r, g, b = p
    return r < 125 and b < 95 and abs(g - r) < 18


# elipse inscrita na costura. Varrer pixel a pixel nao serve: a costura e
# tracejada e a varredura escapa pelos vaos entre os pontos, indo parar no
# fundo de juta. Estes valores foram ajustados contra a costura medida.
OVAL_CX, OVAL_CY, OVAL_A, OVAL_B = 521, 777, 262, 158


def limites_do_oval(im, y):
    t = (y - OVAL_CY) / float(OVAL_B)
    if abs(t) >= 1:
        return OVAL_CX, OVAL_CX
    meia = OVAL_A * math.sqrt(1 - t * t)
    return int(OVAL_CX - meia), int(OVAL_CX + meia)


def brilho_da_linha(im, y, xl, xr):
    """Media da linha ignorando a tinta do texto, para captar so a palha."""
    pi = im.load()
    v = [sum(pi[x, y]) / 3.0 for x in range(xl, xr) if not eh_tinta(pi[x, y])]
    return sum(v) / len(v) if v else None


def palha(im):
    """Refaz a palha em toda a faixa interna do oval onde o texto vivia.

    Mascarar letra a letra nao funciona: com a dilatacao necessaria as letras
    se fundem num retangulo e a borda esfumada deixa um halo visivel. Aqui a
    faixa inteira e substituida em opacidade cheia, com o brilho de cada linha
    preservado (o oval tem sombreado) e um degrade so nas bordas de cima e
    de baixo, onde encosta na palha original.
    """
    _, y0, _, y1 = AREA
    fundo = im.copy()
    pf, po = fundo.load(), im.load()

    tiras = []
    for (jy0, jy1) in JANELAS:
        fy0, fy1, fx0, fx1 = faixa_limpa(im, jy0, jy1)
        t = im.crop((fx0, fy0, fx1, fy1))
        tiras += [t, t.transpose(Image.FLIP_LEFT_RIGHT)]

    DEGRADE = 7
    for y in range(y0, y1):
        xl, xr = limites_do_oval(im, y)
        tira = tiras[(y // 23) % len(tiras)]
        ty = (y - y0) % tira.height
        linha = [tira.getpixel(((x - xl) % tira.width, ty)) for x in range(xl, xr)]
        alvo = brilho_da_linha(im, y, xl, xr)
        med = sum(sum(p) / 3.0 for p in linha) / len(linha)
        k = max(0.9, min(1.12, (alvo / med) if (alvo and med) else 1.0))

        # nas primeiras e ultimas linhas, mistura com o original
        borda = min(y - y0, y1 - 1 - y)
        peso = 1.0 if borda >= DEGRADE else borda / float(DEGRADE)

        for j, x in enumerate(range(xl, xr)):
            r, g, b = linha[j]
            novo_px = (min(255, int(r * k)), min(255, int(g * k)), min(255, int(b * k)))
            if peso >= 1.0:
                pf[x, y] = novo_px
            else:
                orig = po[x, y]
                pf[x, y] = tuple(int(orig[c] * (1 - peso) + novo_px[c] * peso)
                                 for c in range(3))
    return fundo


def ajusta_fonte(texto, alvo_caixa, largura_max):
    """Maior corpo que respeita a caixa alta e a largura disponivel."""
    escolhida = None
    for corpo in range(20, 120):
        f = ImageFont.truetype(FONTE, corpo)
        caixa = f.getbbox("H")[3] - f.getbbox("H")[1]
        larg = f.getbbox(texto)[2] - f.getbbox(texto)[0]
        if caixa <= alvo_caixa and larg <= largura_max:
            escolhida = f
    return escolhida


def desenha(im, linhas):
    d = ImageDraw.Draw(im)
    # um so corpo para as duas linhas: o da linha mais larga manda
    corpo = None
    for texto in linhas:
        f = ajusta_fonte(texto, CAIXA_ALTA, LARGURA_MAX)
        if corpo is None or f.size < corpo.size:
            corpo = f
    for texto, base in zip(linhas, (BASE_1, BASE_2)):
        bb = corpo.getbbox(texto)
        topo_caixa = corpo.getbbox("H")[1]
        x = CENTRO_X - (bb[2] - bb[0]) // 2 - bb[0]
        y = base - (corpo.getbbox("H")[3] - topo_caixa) - topo_caixa
        d.text((x, y), texto, font=corpo, fill=COR_TEXTO)
    return corpo.size


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    linhas = [sys.argv[1], sys.argv[2]]
    if not os.path.exists(FONTE):
        sys.exit("fonte nao encontrada em %s" % FONTE)

    im = palha(Image.open(ORIGEM).convert("RGB"))
    corpo = desenha(im, linhas)
    im.save(SAIDA)
    # versao leve para a web: o PNG original tem ~3 MB, pesado no celular
    jpg = SAIDA.replace(".png", ".jpg")
    im.save(jpg, quality=86, optimize=True, progressive=True)
    print("cartaz regravado (corpo %dpx): %s | %s" % (corpo, linhas[0], linhas[1]))
    print("  %s  %.1f KB" % (os.path.basename(jpg), os.path.getsize(jpg) / 1024.0))


if __name__ == "__main__":
    main()
