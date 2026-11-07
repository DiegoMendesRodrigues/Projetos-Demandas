// Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
// Desenvolvido por Diego Mendes Rodrigues
// Service worker do aplicativo instalável, servido por /sw.js (service_worker em routes.py), que
// troca os marcadores abaixo pela versão, pela página sem conexão e pelos arquivos guardados.
// Só os arquivos estáticos e a página /offline ficam no cache: as páginas com dados do usuário
// vão sempre ao servidor.
"use strict";

const VERSAO = "__VERSAO__";
const PREFIXO_DO_CACHE = "projetos-demandas-";
const CACHE = PREFIXO_DO_CACHE + VERSAO;
const PAGINA_OFFLINE = "__OFFLINE__";
const ARQUIVOS = [] /* __ARQUIVOS__ */;

self.addEventListener("install", (evento) => {
  evento.waitUntil(
    caches.open(CACHE)
      // A página sem conexão é pedida sem os cookies: ela é igual para todos.
      .then((cache) => cache.addAll([...ARQUIVOS, new Request(PAGINA_OFFLINE, { credentials: "omit" })]))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches.keys()
      .then((nomes) => Promise.all(
        nomes
          .filter((nome) => nome !== CACHE && nome.startsWith(PREFIXO_DO_CACHE))
          .map((nome) => caches.delete(nome)),
      ))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (evento) => {
  const pedido = evento.request;
  const endereco = new URL(pedido.url);

  if (pedido.method !== "GET" || endereco.origin !== self.location.origin) {
    return;
  }
  if (pedido.mode === "navigate") {
    // As páginas vêm sempre do servidor; sem conexão, aparece a página /offline.
    evento.respondWith(fetch(pedido).catch(() => caches.match(PAGINA_OFFLINE)));
    return;
  }
  if (ARQUIVOS.includes(endereco.pathname) && !endereco.search) {
    evento.respondWith(caches.match(pedido).then((guardada) => guardada || fetch(pedido)));
  }
});
