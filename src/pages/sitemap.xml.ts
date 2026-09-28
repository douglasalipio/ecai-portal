/**
 * Sitemap. Nao uso @astrojs/sitemap porque ele publica um indice
 * (sitemap-index.xml + sitemap-0.xml) e o Google ja conhece /sitemap.xml
 * deste site — trocar a URL joga fora o historico de rastreamento.
 *
 * A ordem e a mesma de antes: paginas fixas na ordem do menu, depois os
 * nucleos na ordem do conteudo.
 */
import type { APIRoute } from 'astro';
import { conteudo } from '../dados/conteudo';
import { menu } from '../dados/navegacao';

export const GET: APIRoute = () => {
  const base = conteudo.site.url.replace(/\/$/, '');

  const arquivos = [
    ...menu.map((i) => i.url),
    ...conteudo.nucleos.map((n) => `nucleo-${n.slug}.html`),
  ];

  const urls = arquivos
    .map((a) => `  <url><loc>${base}/${a === 'index.html' ? '' : a}</loc></url>\n`)
    .join('');

  return new Response(
    '<?xml version="1.0" encoding="UTF-8"?>\n' +
      '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
      `${urls}</urlset>\n`,
    { headers: { 'Content-Type': 'application/xml; charset=utf-8' } },
  );
};
