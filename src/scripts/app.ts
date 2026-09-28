/**
 * Comportamento do site — porte do bloco JS que era uma string dentro do
 * build.py. Mesmas quatro responsabilidades, agora com tipo e sem escapar
 * aspas na mao.
 *
 * Tudo aqui degrada bem: sem JS o menu nao abre, mas todo o conteudo continua
 * acessivel pelo rodape, que repete a navegacao inteira.
 */

const menu = document.getElementById('menu');

/** Global porque o markup chama por onclick= — herdado do prototipo. */
declare global {
  interface Window {
    alternarMenu: (e?: Event) => void;
  }
}

window.alternarMenu = (e?: Event) => {
  e?.preventDefault();
  if (!menu) return;
  const abriu = menu.classList.toggle('aberto');
  document.body.classList.toggle('travado', abriu);
  document
    .querySelector('.menu-btn[aria-expanded]')
    ?.setAttribute('aria-expanded', String(abriu));
};

// clique no veu fecha; Esc tambem
menu?.addEventListener('click', (e) => {
  if (e.target === menu) window.alternarMenu();
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && menu?.classList.contains('aberto')) window.alternarMenu();
});

const semMovimento = matchMedia('(prefers-reduced-motion: reduce)').matches;

// o item aberto do FAQ ja nasce com o sinal de menos
const primeiro = document.querySelector('.faq.aberto .faq-i');
if (primeiro) primeiro.textContent = '–';

if (semMovimento) {
  document.querySelectorAll<HTMLVideoElement>('video[autoplay]').forEach((v) => {
    v.removeAttribute('autoplay');
    v.pause();
  });
}

// carrossel: anda sozinho, mas para 9s a cada toque e so roda se estiver visivel
const faixa = document.querySelector<HTMLElement>('[data-carrossel]');
if (faixa && !semMovimento) {
  let pausaAte = 0;
  let visivel = true;
  const pausar = () => { pausaAte = Date.now() + 9000; };

  (['pointerdown', 'touchstart', 'wheel', 'mouseenter', 'focusin'] as const).forEach((ev) =>
    faixa.addEventListener(ev, pausar, { passive: true }),
  );

  if (window.IntersectionObserver) {
    new IntersectionObserver((es) => { visivel = !!es[0]?.isIntersecting; }, { threshold: 0.35 })
      .observe(faixa);
  }

  setInterval(() => {
    if (!visivel || document.hidden || Date.now() < pausaAte) return;
    const cs = faixa.children;
    if (cs.length < 2) return;

    const base = (cs[0] as HTMLElement).offsetLeft;
    let alvo = 0;
    for (const c of cs) {
      const x = (c as HTMLElement).offsetLeft - base;
      if (x > faixa.scrollLeft + 8) { alvo = x; break; }
    }
    if (faixa.scrollLeft + faixa.clientWidth >= faixa.scrollWidth - 8) alvo = 0;
    faixa.scrollTo({ left: alvo, behavior: 'smooth' });
  }, 4000);
}

// acordeao do FAQ: abre um, fecha os outros
document.querySelectorAll<HTMLElement>('[data-faq]').forEach((b) => {
  b.addEventListener('click', (e) => {
    e.preventDefault();
    const caixa = b.closest('.faq');
    const estavaAberto = caixa?.classList.contains('aberto');

    document.querySelectorAll('.faq').forEach((o) => {
      o.classList.remove('aberto');
      const i = o.querySelector('.faq-i');
      if (i) i.textContent = '+';
    });

    if (!estavaAberto && caixa) {
      caixa.classList.add('aberto');
      const i = caixa.querySelector('.faq-i');
      if (i) i.textContent = '–';
    }
  });
});

export {};
