const { send, readBody, handleError, guard, authenticate, checkEventCode } = require("../_lib/http");
const {
  readTeams,
  readParticipants,
  serializeParticipants,
  commitFiles,
  getUserEmails,
  inviteCollaborator,
} = require("../_lib/github");
const { hashEmail, encryptEmail } = require("../_lib/emailCrypto");
const { publicTeam, findActiveMembership } = require("../_lib/teams");

function promoteOrAddMember(team, login, created_at) {
  team.members = team.members || [];
  const existing = team.members.find(
    (m) => m && m.login && String(m.login).toLowerCase() === login.toLowerCase()
  );
  if (existing) {
    existing.status = "joined";
    return;
  }
  const invited = team.members.find((m) => m && !m.login && (m.status || "invited") !== "joined");
  if (invited) {
    invited.login = login;
    invited.status = "joined";
    return;
  }
  team.members.push({ login, status: "joined", created_at });
}

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
    const uniqueEmails = [...new Set(emails.filter(Boolean))];
    const hashes = [...new Set(uniqueEmails.map((e) => hashEmail(e)).filter(Boolean))];
    const loginLc = user.login.toLowerCase();

    const store = await readTeams();
    const team = store.teams.find((t) => t.slug === slug);
    if (!team) return send(res, 404, { error: "Équipe introuvable." });

    // Déjà membre confirmé de cette équipe : opération idempotente.
    const alreadyJoined = (team.members || []).some(
      (m) => m && m.login && String(m.login).toLowerCase() === loginLc && (m.status || "joined") === "joined"
    );
    if (alreadyJoined) {
      await inviteCollaborator(user.login);
      return send(res, 200, { team: publicTeam(team), invited: user.login });
    }

    const participants = await readParticipants();
    const conflict = findActiveMembership(store, participants.rows, { login: user.login, hashes }, slug);
    if (conflict) {
      return send(res, 409, {
        error: `Tu fais déjà partie de l'équipe "${conflict.name}". Quitte-la avant d'en rejoindre une autre.`,
      });
    }

    const created_at = new Date().toISOString();
    // Membre déclaré correspondant à l'un des emails : on confirme l'adhésion.
    const declaredRow = participants.rows.find(
      (r) =>
        String(r.team_name || "").toLowerCase() === String(team.name || "").toLowerCase() &&
        hashes.includes(String(r.email_hash || "").toLowerCase())
    );
    if (declaredRow) {
      declaredRow.login = user.login;
    } else {
      // Rejoindre librement : on ajoute le nouveau participant.
      const primaryEmail = uniqueEmails[0] || `${user.login}@users.noreply.github.com`;
      participants.rows.push({
        email_hash: hashEmail(primaryEmail),
        email_enc: encryptEmail(primaryEmail),
        login: user.login,
        team_name: team.name,
      });
    }
    promoteOrAddMember(team, user.login, created_at);

    await commitFiles(
      {
        "teams.json": JSON.stringify(store, null, 2) + "\n",
        "participants.csv": serializeParticipants(participants.rows),
      },
      `teams: ${user.login} rejoint ${slug}`
    );
    await inviteCollaborator(user.login);

    return send(res, 200, { team: publicTeam(team), invited: user.login });
  } catch (err) {
    return handleError(res, err);
  }
};
