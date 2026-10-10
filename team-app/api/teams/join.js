const { send, readBody, handleError, guard, authenticate, checkEventCode } = require("../_lib/http");
const { readTeams, commitFiles, getUserEmails, inviteCollaborator, buildParticipantsCsv } = require("../_lib/github");
const { hashEmail } = require("../_lib/emailCrypto");

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

    const store = await readTeams();
    const team = store.teams.find((t) => t.slug === slug);
    if (!team) return send(res, 404, { error: "Équipe introuvable." });

    const member = (team.members || []).find((m) => hashes.includes(String(m.email_hash || "")));
    if (!member) {
      return send(res, 403, {
        error: "Ton adresse email ne figure pas dans la liste des membres de cette équipe.",
      });
    }

    member.login = user.login;
    member.joined = true;

    await commitFiles(
      {
        "teams.json": JSON.stringify(store, null, 2) + "\n",
        "participants.csv": buildParticipantsCsv(store),
      },
      `teams: ${user.login} rejoint ${slug}`
    );
    await inviteCollaborator(user.login);

    const publicTeam = {
      ...team,
      members: (team.members || []).map((m) => ({
        email_hash: m.email_hash || "",
        login: m.login || null,
        joined: !!m.joined,
      })),
    };
    return send(res, 200, { team: publicTeam, invited: user.login });
  } catch (err) {
    return handleError(res, err);
  }
};
