/**
 * Lista de interesse da loja.
 *
 * Nao e carrinho de compras: o site nao cobra nada. A pessoa junta o que
 * gostou, e ao finalizar isso vira uma mensagem itemizada num WhatsApp, onde
 * o frete e o pagamento sao combinados por gente de verdade.
 *
 * Por isso nao ha estoque, reserva nem expiracao — a lista e so um bloco de
 * anotacoes que sobrevive entre paginas.
 */

const CHAVE = 'ife:lista:v1';

/** Limite conservador para o texto da URL do wa.me; acima disso encurta. */
const LIMITE_MENSAGEM = 1500;

type Linha = { slug: string; variacao: string; qtd: number };
type Ficha = { nome: string; preco: number; variacaoNome: string };

/** slug -> ficha, embutido na pagina pelo componente Carrinho. */
const catalogo: Record<string, Ficha> = (() => {
  const el = document.getElementById('catalogo-loja');
  try {
    return el ? JSON.parse(el.textContent || '{}') : {};
  } catch {
    return {};
  }
})();

const emReais = (centavos: number) =>
  (centavos / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

/** Produto + variacao formam a identidade: P e G sao linhas diferentes. */
const idDe = (l: Linha) => (l.variacao ? `${l.slug}|${l.variacao}` : l.slug);

function ler(): Linha[] {
  try {
    const cru = JSON.parse(localStorage.getItem(CHAVE) || '[]');
    if (!Array.isArray(cru)) return [];
    // descarta o que nao esta mais no catalogo: produto retirado nao pode
    // reaparecer numa lista velha de quem voltou meses depois
    return cru.filter(
      (l): l is Linha =>
        l && typeof l.slug === 'string' && catalogo[l.slug] &&
        typeof l.qtd === 'number' && l.qtd > 0,
    );
  } catch {
    return [];
  }
}

function gravar(linhas: Linha[]) {
  localStorage.setItem(CHAVE, JSON.stringify(linhas));
  document.dispatchEvent(new CustomEvent('lista:mudou'));
}

export function adicionar(slug: string, variacao = '', qtd = 1) {
  const linhas = ler();
  const alvo = idDe({ slug, variacao, qtd });
  const achou = linhas.find((l) => idDe(l) === alvo);
  if (achou) achou.qtd += qtd;
  else linhas.push({ slug, variacao, qtd });
  gravar(linhas);
}

export function mudarQtd(id: string, delta: number) {
  const linhas = ler()
    .map((l) => (idDe(l) === id ? { ...l, qtd: l.qtd + delta } : l))
    .filter((l) => l.qtd > 0);
  gravar(linhas);
}

export function remover(id: string) {
  gravar(ler().filter((l) => idDe(l) !== id));
}

export function limpar() {
  gravar([]);
}

export const quantas = () => ler().reduce((s, l) => s + l.qtd, 0);

export const total = () =>
  ler().reduce((s, l) => s + (catalogo[l.slug]?.preco ?? 0) * l.qtd, 0);

export function itens() {
  return ler().map((l) => {
    const f = catalogo[l.slug]!;
    return {
      id: idDe(l),
      slug: l.slug,
      qtd: l.qtd,
      nome: f.nome,
      variacao: l.variacao,
      variacaoNome: f.variacaoNome,
      preco: f.preco,
      subtotal: f.preco * l.qtd,
    };
  });
}

/**
 * Monta a mensagem do WhatsApp. Diz "gostei destes itens", nao "comprei":
 * quem responde precisa entender que ainda ha frete a combinar.
 */
export function mensagem() {
  const linhas = itens();
  if (!linhas.length) return '';

  const lista = linhas.map((i) => {
    const qual = i.variacao ? ` (${i.variacaoNome.toLowerCase()} ${i.variacao})` : '';
    const quantos = i.qtd > 1 ? ` — ${i.qtd}x` : '';
    return `• ${i.nome}${qual}${quantos} — ${emReais(i.subtotal)}`;
  });

  let corpo = lista.join('\n');
  if (corpo.length > LIMITE_MENSAGEM) {
    // URL muito longa quebra em alguns aparelhos; manda o que cabe e avisa
    const cabem: string[] = [];
    let conta = 0;
    for (const l of lista) {
      if (conta + l.length > LIMITE_MENSAGEM) break;
      cabem.push(l);
      conta += l.length + 1;
    }
    corpo = `${cabem.join('\n')}\n• …e mais ${lista.length - cabem.length} item(ns)`;
  }

  return [
    'Olá! Gostei destes itens da loja da IFÉ:',
    '',
    corpo,
    '',
    `Produtos: ${emReais(total())}`,
    '',
    'Queria saber do frete e como faço pra levar.',
  ].join('\n');
}

export function linkWhatsapp(numero: string) {
  const texto = encodeURIComponent(mensagem());
  return `https://wa.me/${numero.replace(/\D/g, '')}?text=${texto}`;
}

export { emReais };
