# Site da Escola de Capoeira Angola IFÉ

Site estático em [Astro](https://astro.build), publicado no Firebase Hosting
em **[ecai.net.br](https://ecai.net.br)**.

## Rodar

```bash
npm install          # uma vez
npm run dev          # http://localhost:4321
```

## Publicar

```bash
npm run deploy
```

O deploy é deliberadamente chato: roda o build em modo `ESTRITO=1`, confere o
resultado e compara com a referência antes de subir. Qualquer um dos três
falhando, nada é publicado.

| Comando | O que faz |
|---|---|
| `npm run build` | Gera `dist/` e roda a verificação |
| `npm run verificar` | Placeholder no ar, link quebrado, arquivo faltando, `alt` ausente |
| `npm run comparar` | Compara `dist/` com `_referencia/` (o site pré-migração) |
| `npm run check` | Checagem de tipos do Astro |

## Onde fica o quê

```
src/
├── dados/
│   ├── conteudo.json    ← o arquivo que você edita
│   ├── conteudo.ts      ← schema Zod: valida e tipa o de cima
│   └── navegacao.ts     ← itens do menu
├── styles/
│   ├── tokens.css       ← cores, fontes, larguras. Nenhum componente escreve hex
│   ├── base.css         ← reset, coluna do site, menu, degraus de desktop
│   └── zebra.css        ← gerado; não edite à mão
├── components/          ← Cabecalho, Menu, Rodape, Faq, GradeGaleria, ...
├── layouts/Base.astro   ← <head>, coluna, cabeçalho, menu, rodapé
├── pages/               ← uma página por arquivo; nucleo-[slug] gera as quatro
└── scripts/app.ts       ← menu, acordeão do FAQ, carrossel

public/                  ← servido como está: fotos/, video/, logo, cartaz
origem/                  ← originais de câmera e fonte do cartaz. Nunca publicados
ferramentas/             ← scripts de apoio (Python 3, sem dependências além do Pillow no cartaz)
_referencia/             ← o site como era antes da migração, congelado
_legado/                 ← build.py, o export de design e o que veio com ele
```

## Mexer no conteúdo

Quase tudo está em `src/dados/conteudo.json`. O schema em `conteudo.ts` é
quem decide o que é válido, e o build **para** se:

- faltar campo, sobrar campo ou o tipo estiver errado;
- uma foto citada não existir em `public/`;
- dois núcleos tiverem o mesmo `slug`;
- nenhum núcleo estiver marcado com `"sede": true`.

Acrescentar um núcleo em `nucleos` cria a página dele, o alfinete no mapa e
a linha na lista, sem tocar em código.

### Placeholders

Os textos do rascunho original vinham com marcas `⟨assim⟩`. Três ainda estão
no ar: `⟨5⟩` e `⟨60+⟩` no FAQ de Aulas, `⟨2026⟩` no topo de Eventos. Durante o
desenvolvimento eles só geram aviso; `npm run deploy` recusa publicar.

## Por que existe `_referencia/`

A migração do gerador antigo (`_legado/build.py`, que fatiava um export de
ferramenta de design e o remendava com 25 substituições por string) foi feita
página a página, conferindo cada uma contra o site que estava no ar. As nove
fecham idênticas em texto, títulos, links e imagens.

Enquanto `_referencia/` existir, `npm run comparar` continua sendo uma rede
contra regressão. Vale apagar quando o site já tiver mudado de propósito o
bastante para a comparação não dizer mais nada.

## Imagens

`public/fotos/` tem as fotos tratadas em 1400×788; os originais de câmera
(7680×4320) estão em `origem/fotos/`. Hoje a redução é manual — o passo
natural seguinte é trocar isso por `astro:assets`, que gera webp/avif e
`srcset` a partir dos originais.

O cartaz do evento é gerado:

```bash
python3 ferramentas/cartaz.py "PRIMEIRA LINHA" "SEGUNDA LINHA"
```

## Hospedagem

`firebase.json` publica `dist/` no alvo `capoeira` do projeto `proza-1404`.
As URLs terminam em `.html` (`cleanUrls: false`, e `build.format: 'file'` no
`astro.config.mjs`) porque é assim que o site já está indexado.
