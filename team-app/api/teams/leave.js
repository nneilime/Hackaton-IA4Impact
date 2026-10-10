const { send, readBody, handleError, guard, authenticate, checkEventCode } = require("../_lib/http");
const {
  readTeams,
  readParticipants,
  serializeParticipants,
  commitFiles,
  getUserEmails,
} = require("../_lib/github");
const { hashEmail } = require("../_lib/emailCrypto");
const { publicTeam } = require("../_lib/teams");

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
    const hashes = [...new Set(emails.map((e) => hashEmail(e)))];
    const loginLc = user.login.toLowerCase();

    const store = await readTeams();
    const team = store.teams.find((t) => t.slug === slug);
    if (!team) return send(res, 404, { error: "Équipe introuvable." });

    const member = (team.members || []).find((m) => m && m.login && String(m.login).toLowerCase() === loginLc);
    if (!member) return send(res, 403, { error: "Tu ne fais pas partie de cette équipe." });

    member.login = null;
    member.status = "invited";

    const participants = await readParticipants();
    const row = participants.rows.find(
      (r) =>
        String(r.team_name || "").toLowerCase() === String(team.name || "").toLowerCase() &&
        (String(r.login || "").toLowerCase() === loginLc ||
          hashes.includes(String(r.email_hash || "")))
    );
    if (row) row.login = "";

    await commitFiles(
      {
        "teams.json": JSON.stringify(store, null, 2) + "\n",
        "participants.csv": serializeParticipants(participants.rows),
      },
      `teams: ${user.login} quitte ${slug}`
    );

    return send(res, 200, { team: publicTeam(team) });
  } catch (err) {
    return handleError(res, err);
  }
};
