/**
 * Menu do site — era a constante MENU_DEF dentro do build.py.
 *
 * A lista completa fica aqui; paginasOcultas no conteudo.json tira itens do
 * menu, do sitemap e da geracao. Hoje 'mestre' esta oculta.
 */

import { conteudo } from './conteudo';

export type Tela = 'home' | 'mestre' | 'nucleos' | 'aulas' | 'eventos' | 'galeria' | 'nucleo';

type Item = { rotulo: string; tela: Tela; url: string };

const TODAS: Item[] = [
  { rotulo: 'Início', tela: 'home', url: 'index.html' },
  { rotulo: 'Mestre e Fundadores', tela: 'mestre', url: 'mestre.html' },
  { rotulo: 'Núcleos', tela: 'nucleos', url: 'nucleos.html' },
  { rotulo: 'Aulas', tela: 'aulas', url: 'aulas.html' },
  { rotulo: 'Eventos e Agenda', tela: 'eventos', url: 'eventos.html' },
  { rotulo: 'Galeria', tela: 'galeria', url: 'galeria.html' },
];

const ocultas = new Set(conteudo.paginasOcultas);

export const menu = TODAS.filter((i) => !ocultas.has(i.tela));
export const oculta = (tela: Tela) => ocultas.has(tela);
