const { send, readBody, handleError, guard, authenticate, checkEventCode } = require("../_lib/http");
const { readTeams, commitFiles, getUserEmails } = require("../_lib/github");

module.exports = async (req, res) => {
  if (guard(req, res)) return;
  try {
    if (req.method !== "POST") return send(res, 405, { error: "Méthode non autorisée" });

    const auth = await authenticate(req);
    if (!auth) return send(res, 401, { error: "Connecte-toi avec GitHub pour continuer." });
    if (!checkEventCode(req)) return send(res, 403, { error: "Code d'accès invalide." });

    const { slug } = await readBody(req);
    if (!slug) return send(res, 400, { error: "slug manquant" });

    const { user, token } = auth;
    const emails = await getUserEmails(token);
    if (user.email) emails.push(user.email.toLowerCase());

    const store = await readTeams();
    const team = store.teams.find((t) => t.slug === slug);
    if (!team) return send(res, 404, { error: "Équipe introuvable." });

    const member = (team.members || []).find(
      (m) => (m.login && m.login.toLowerCase() === user.login.toLowerCase()) ||
        emails.includes(String(m.email).toLowerCase())
    );
    if (!member) return send(res, 403, { error: "Tu ne fais pas partie de cette équipe." });

    member.login = null;
    member.joined = false;

    await commitFiles(
      { "teams.json": JSON.stringify(store, null, 2) + "\n" },
      `teams: ${user.login} quitte ${slug}`
    );

    return send(res, 200, { team });
  } catch (err) {
    return handleError(res, err);
  }
};
