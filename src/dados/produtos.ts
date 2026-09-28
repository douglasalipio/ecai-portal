/**
 * Contrato do catalogo da loja.
 *
 * A loja nao vende: ela junta o que a pessoa gostou e entrega a lista pronta
 * numa conversa de WhatsApp, onde o frete e combinado caso a caso. Por isso
 * nao ha estoque, pagamento nem calculo de frete em lugar nenhum daqui.
 */

import { z } from 'astro/zod';
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import bruto from './produtos.json';
import { conteudo } from './conteudo';

const PUBLICO = join(process.cwd(), 'public');

const arquivoExistente = z.string().refine((rel) => existsSync(join(PUBLICO, rel)), {
  message: 'arquivo nao encontrado em public/',
});

const categoria = z.object({
  slug: z.string().regex(/^[a-z0-9-]+$/),
  nome: z.string().min(1),
});

const variacao = z.object({
  nome: z.string().min(1),
  opcoes: z.array(z.string().min(1)).min(2, 'variacao com uma opcao so nao e variacao'),
});

const produto = z.object({
  slug: z.string().regex(/^[a-z0-9-]+$/, 'slug so aceita minusculas, numeros e hifen'),
  nome: z.string().min(1),
  categoria: z.string(),
  /** Em CENTAVOS, inteiro. Dinheiro em float erra na soma. */
  preco: z.number().int().positive('preco em centavos, inteiro e maior que zero'),
  descricao: z.string().min(1),
  fotos: z.array(arquivoExistente).min(1, 'todo produto precisa de ao menos uma foto'),
  variacoes: z.array(variacao),
  disponivel: z.boolean(),
  /** Marca produto de demonstracao; barra a publicacao da loja. */
  exemplo: z.boolean().optional(),
});

const esquema = z.object({
  loja: z.object({
    whatsapp: z.string(),
    sobretitulo: z.string().min(1),
    titulo: z.string().min(1),
    chamada: z.string().min(1),
    avisoFrete: z.string().min(1),
  }),
  categorias: z.array(categoria).min(1),
  produtos: z.array(produto),
}).superRefine((d, ctx) => {
  const slugs = d.produtos.map((p) => p.slug);
  const repetido = slugs.find((s, i) => slugs.indexOf(s) !== i);
  if (repetido) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['produtos'],
      message: `slug repetido: ${repetido} — duas paginas escreveriam no mesmo arquivo`,
    });
  }

  const conhecidas = new Set(d.categorias.map((c) => c.slug));
  for (const [i, p] of d.produtos.entries()) {
    if (!conhecidas.has(p.categoria)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['produtos', i, 'categoria'],
        message: `categoria "${p.categoria}" nao existe — some da vitrine sem avisar`,
      });
    }
  }
});

const resultado = esquema.safeParse(bruto);

if (!resultado.success) {
  const linhas = resultado.error.issues.map(
    (i) => `  produtos.json → ${i.path.join('.') || '(raiz)'}: ${i.message}`,
  );
  throw new Error(`Catalogo invalido, o site nao foi gerado:\n${linhas.join('\n')}`);
}

/**
 * A loja so vale publicar inteira. Enquanto 'loja' estiver em paginasOcultas
 * a pagina existe mas nao e linkada nem entra no sitemap, e estas duas
 * condicoes sao apenas avisadas. Ao tira-la de la, viram erro de build:
 * loja sem numero de WhatsApp nao tem como receber pedido, e produto de
 * exemplo no ar e pior do que loja nenhuma.
 */
const publicada = !conteudo.paginasOcultas.includes('loja');
const pendencias: string[] = [];

if (!resultado.data.loja.whatsapp.trim()) {
  pendencias.push('loja.whatsapp esta vazio — o botao de pedido nao tem para onde ir');
}
const deExemplo = resultado.data.produtos.filter((p) => p.exemplo).map((p) => p.slug);
if (deExemplo.length) {
  pendencias.push(`produtos de exemplo ainda no catalogo: ${deExemplo.join(', ')}`);
}

if (pendencias.length) {
  const texto = pendencias.map((p) => `     ${p}`).join('\n');
  if (publicada) {
    throw new Error(
      `A loja esta publicada mas nao esta pronta:\n${texto}\n` +
      `   Resolva, ou ponha "loja" de volta em paginasOcultas.`,
    );
  }
  console.warn(
    `\n⚠  Loja ainda oculta (paginasOcultas), e falta:\n${texto}\n` +
    `   Publicar com isso pendente barra o build.\n`,
  );
}

export const loja = resultado.data.loja;
export const categorias = resultado.data.categorias;
export const produtos = resultado.data.produtos.filter((p) => p.disponivel);

export type Produto = z.infer<typeof produto>;

/** Produtos de demonstracao ainda no catalogo. */
export const exemplos = produtos.filter((p) => p.exemplo).map((p) => p.slug);

/** "R$ 450,00" a partir de 45000. */
export const emReais = (centavos: number) =>
  (centavos / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

/** Agrupa na ordem das categorias, ignorando categoria vazia. */
export const porCategoria = categorias
  .map((c) => ({ ...c, itens: produtos.filter((p) => p.categoria === c.slug) }))
  .filter((c) => c.itens.length > 0);
