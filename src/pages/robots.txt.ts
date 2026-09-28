/** robots.txt — mesma saida que o build.py produzia. */
import type { APIRoute } from 'astro';
import { conteudo } from '../dados/conteudo';

export const GET: APIRoute = () => {
  const base = conteudo.site.url.replace(/\/$/, '');
  return new Response(`User-agent: *\nAllow: /\nSitemap: ${base}/sitemap.xml\n`, {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
};
