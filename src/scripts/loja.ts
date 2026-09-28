/**
 * Liga a gaveta da lista ao estado em carrinho.ts.
 *
 * Carrega so nas paginas que tem a gaveta (loja e produto); as paginas de
 * conteudo continuam com os ~2 KB de JS de sempre.
 */

import { itens, total, quantas, adicionar, mudarQtd, remover, limpar, linkWhatsapp, emReais }
  from './carrinho';

const gaveta = document.getElementById('lista');
if (gaveta) {
  const corpo = gaveta.querySelector<HTMLElement>('[data-lista-corpo]')!;
  const somaEl = gaveta.querySelector<HTMLElement>('[data-lista-total]')!;
  const pedir = gaveta.querySelector<HTMLAnchorElement>('[data-lista-pedir]')!;
  const numero = gaveta.dataset.whatsapp || '';

  const abrir = () => {
    gaveta.hidden = false;
    document.body.classList.add('travado');
  };
  const fechar = () => {
    gaveta.hidden = true;
    document.body.classList.remove('travado');
  };

  function desenhar() {
    const linhas = itens();

    corpo.innerHTML = linhas.length
      ? linhas.map((i) => `
        <div class="item" data-id="${i.id}">
          <div class="dados">
            <div class="nome">${i.nome}</div>
            ${i.variacao ? `<div class="variacao">${i.variacaoNome}: ${i.variacao}</div>` : ''}
            <div class="preco">${emReais(i.preco)}</div>
          </div>
          <div class="qtd">
            <button data-menos aria-label="Tirar um">−</button>
            <span>${i.qtd}</span>
            <button data-mais aria-label="Pôr mais um">+</button>
          </div>
          <button class="tirar" data-tirar aria-label="Tirar da lista">✕</button>
        </div>`).join('')
      : '<p class="vazia">Sua lista está vazia. Escolha o que gostou na loja.</p>';

    somaEl.textContent = emReais(total());

    const podePedir = linhas.length > 0 && numero !== '';
    pedir.setAttribute('aria-disabled', String(!podePedir));
    pedir.href = podePedir ? linkWhatsapp(numero) : '#';
    if (linhas.length && !numero) pedir.textContent = 'WhatsApp não cadastrado';
    else pedir.textContent = 'Pedir no WhatsApp';

    // contador no cabecalho
    const n = quantas();
    document.querySelectorAll<HTMLElement>('[data-lista-conta]').forEach((el) => {
      el.textContent = String(n);
      el.hidden = n === 0;
    });
  }

  // cliques dentro da gaveta
  corpo.addEventListener('click', (e) => {
    const alvo = e.target as HTMLElement;
    const item = alvo.closest<HTMLElement>('.item');
    if (!item) return;
    const id = item.dataset.id!;
    if (alvo.closest('[data-mais]')) mudarQtd(id, +1);
    else if (alvo.closest('[data-menos]')) mudarQtd(id, -1);
    else if (alvo.closest('[data-tirar]')) remover(id);
  });

  gaveta.querySelector('[data-lista-limpar]')?.addEventListener('click', () => limpar());
  gaveta.querySelector('[data-lista-fechar]')?.addEventListener('click', fechar);
  gaveta.addEventListener('click', (e) => { if (e.target === gaveta) fechar(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !gaveta.hidden) fechar();
  });

  // botoes de adicionar, na vitrine e na pagina do produto
  document.querySelectorAll<HTMLElement>('[data-adicionar]').forEach((botao) => {
    botao.addEventListener('click', () => {
      const slug = botao.dataset.adicionar!;
      const escolha = document.querySelector<HTMLSelectElement>(`[data-variacao="${slug}"]`);
      adicionar(slug, escolha?.value ?? '');
      abrir();
    });
  });

  document.querySelectorAll<HTMLElement>('[data-lista-abrir]')
    .forEach((b) => b.addEventListener('click', abrir));

  document.addEventListener('lista:mudou', desenhar);
  desenhar();
}
