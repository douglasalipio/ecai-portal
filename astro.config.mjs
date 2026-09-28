// @ts-check
import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://ecai.net.br',

  // O site publicado usa /aulas.html, nao /aulas/. O firebase.json esta com
  // cleanUrls: false e o sitemap lista os .html — mudar isso invalidaria as
  // URLs ja indexadas. 'file' faz o Astro emitir aulas.html em vez de
  // aulas/index.html.
  build: { format: 'file' },
  trailingSlash: 'never',

  // mesma pasta que o firebase.json ja publica
  outDir: './dist',

  devToolbar: { enabled: false },
});
