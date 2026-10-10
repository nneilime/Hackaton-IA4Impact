import { traiter } from '../serveur.mjs';

export default function (req, res) {
  const u = new URL(req.url, 'http://x');
  const chemin = u.searchParams.get('__chemin');
  if (chemin !== null) {
    u.searchParams.delete('__chemin');
    req.url = (chemin || '/') + (u.searchParams.size ? `?${u.searchParams}` : '');
  }
  return traiter(req, res);
}
