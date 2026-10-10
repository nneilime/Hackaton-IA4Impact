// Proxy de dev vers Prism (mock de l'API), utilisé par `pnpm start:mock`.
// Prism sert /ask, pas /api/ask : on retire le préfixe /api.
// Prism répond 401 sans en-tête X-API-Key : on en ajoute un quelconque (c'est un mock, pas un secret).
export default {
  '/api': {
    target: 'http://localhost:4010',
    changeOrigin: true,
    pathRewrite: { '^/api': '' },
    headers: { 'X-API-Key': 'mock' },
  },
};
