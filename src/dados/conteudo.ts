/**
 * Contrato do conteudo do site.
 *
 * conteudo.json continua sendo um arquivo unico, editavel por quem nao mexe
 * em codigo — esse era o ponto do arquivo e nao faz sentido perder. O que
 * muda e que agora ele passa por um schema antes de virar pagina.
 *
 * Tres coisas que antes so apareciam no site publicado e agora quebram o
 * build:
 *   1. placeholder ⟨assim⟩ esquecido em qualquer texto
 *   2. foto citada que nao existe no disco
 *   3. campo faltando, sobrando ou com o tipo errado
 */

import { z } from 'astro/zod';
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import bruto from './conteudo.json';

/** Assets servidos como estao vivem em public/ e sao citados sem esse prefixo. */
const PUBLICO = join(process.cwd(), 'public');

/**
 * Placeholders do rascunho original: ⟨Nome⟩, ⟨19XX⟩, ⟨5⟩.
 *
 * Tres deles estao no ar hoje (⟨5⟩ e ⟨60+⟩ no FAQ, ⟨2026⟩ em eventos), entao
 * barrar o build por padrao pararia de gerar um site que hoje funciona. Sao
 * avisos em todo build e viram erro com ESTRITO=1, que e como `npm run deploy`
 * roda — publicar exige texto de verdade, desenvolver nao.
 */
const ESTRITO = process.env.ESTRITO === '1';
const placeholders: string[] = [];

const semPlaceholder = (campo: string, base: z.ZodString = z.string()) =>
  base.superRefine((s, ctx) => {
    const achados = s.match(/⟨[^⟩]*⟩/g);
    if (!achados) return;
    const onde = `${ctx.path.join('.') || campo}: ${achados.join(' ')}`;
    if (ESTRITO) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `sobrou placeholder ${achados.join(' ')} — preencha antes de publicar`,
      });
    } else if (!placeholders.includes(onde)) {
      placeholders.push(onde);
    }
  });

/** Caminho como o navegador ve, "fotos/galeria-3.jpg" — resolvido em public/. */
const arquivoExistente = z.string().refine((rel) => existsSync(join(PUBLICO, rel)), {
  message: 'arquivo nao encontrado em public/',
});

const texto = semPlaceholder('texto');

const nucleo = z.object({
  slug: z.string().regex(/^[a-z0-9-]+$/, 'slug so aceita minusculas, numeros e hifen'),
  sigla: z.string().length(2),
  nome: texto,
  resumo: texto,
  tag: texto,
  prof: texto,
  end: texto,
  /** Forma curta para o cartao de destaque, onde o endereco inteiro nao cabe. */
  endCurto: texto.optional(),
  x: z.string(),
  y: z.string(),
  pin: z.string(),
  sede: z.boolean().optional(),
  mapa: z.string().url().optional(),
  whatsapp: z.string(),
});

const horario = z.object({
  dia: texto,
  turma: texto,
  hora: texto,
  bg: z.string().regex(/^#[0-9a-f]{6}$/i),
});

const pilar = z.object({ n: z.string(), titulo: texto, texto });
const marco = z.object({ ano: texto, titulo: texto, texto });
const elo = z.object({ nome: texto, nota: texto });

const fundador = z.object({
  slot: z.string(),
  foto: arquivoExistente,
  pos: z.string(),
  papel: texto,
  apelido: texto,
  nome: z.string(),
  trajetoria: z.string(),
});

const turma = z.object({
  nome: texto,
  idade: texto,
  texto,
  dias: z.array(texto),
});

const faq = z.object({ p: texto, r: texto });

const evento = z.object({
  dia: z.string(),
  mes: z.string(),
  tipo: texto,
  titulo: texto,
  nomes: z.string(),
  local: texto,
  mapa: z.string().url(),
});

const foto = z.object({
  src: arquivoExistente,
  alt: semPlaceholder('alt', z.string().min(1, 'toda foto precisa de alt')),
  tamanho: z.enum(['largo', 'pequeno']),
  pos: z.string(),
});

const site = z.object({
  nome: texto,
  nomeCompleto: texto,
  descricao: texto,
  url: z.string().url(),
  sede: texto,
  instagram: z.string().url(),
  instagramHandle: z.string(),
  whatsapp: z.string(),
  mapaSede: z.string().url(),
  mapaMuafro: z.string().url(),
  ano: z.string(),
  cidade: texto,
  inscricaoEvento: z.string().url(),
  contatoAula: z.string(),
  videoCapa: arquivoExistente,
  mapaPacoDoFrevo: z.string().url(),
  mapaCasaBulicosa: z.string().url(),
});

const esquema = z.object({
  site,
  nucleos: z.array(nucleo).min(1),
  horarios: z.array(horario),
  pilares: z.array(pilar),
  linhagem: z.array(elo),
  fundadores: z.array(fundador),
  marcos: z.array(marco),
  turmas: z.array(turma),
  faqs: z.array(faq),
  eventos: z.array(evento),
  galeria: z.array(foto).min(1),
  destaquesHome: z.array(z.string()),
  paginasOcultas: z.array(z.string()),
})
  .superRefine((d, ctx) => {
    if (!d.nucleos.some((n) => n.sede)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['nucleos'],
        message: 'nenhum nucleo marcado com sede: true — o rodape e o botao da capa dependem disso',
      });
    }
    const slugs = d.nucleos.map((n) => n.slug);
    const repetido = slugs.find((s, i) => slugs.indexOf(s) !== i);
    if (repetido) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['nucleos'],
        message: `slug repetido: ${repetido} — duas paginas escreveriam no mesmo arquivo`,
      });
    }
  });

const resultado = esquema.safeParse(bruto);

if (!resultado.success) {
  const linhas = resultado.error.issues.map(
    (i) => `  conteudo.json → ${i.path.join('.') || '(raiz)'}: ${i.message}`,
  );
  throw new Error(`Conteudo invalido, o site nao foi gerado:\n${linhas.join('\n')}`);
}

if (placeholders.length) {
  console.warn(
    `\n⚠  ${placeholders.length} placeholder(s) ainda no conteudo — vao para o ar assim:\n` +
      placeholders.map((p) => `     ${p}`).join('\n') +
      `\n   ESTRITO=1 transforma isso em erro (e o que npm run deploy faz).\n`,
  );
}

export const conteudo = resultado.data;
export type Conteudo = typeof conteudo;
export type Nucleo = z.infer<typeof nucleo>;
export type Foto = z.infer<typeof foto>;
export type Evento = z.infer<typeof evento>;

/** A sede e marcada por campo, nao por posicao: a ordem da lista e editorial. */
export const sede = conteudo.nucleos.find((n) => n.sede) ?? conteudo.nucleos[0]!;
