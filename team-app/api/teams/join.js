const { send, readBody, handleError, guard, authenticate, checkEventCode } = require("../_lib/http");
const { readTeams, commitFiles, getUserEmails, inviteCollaborator, buildParticipantsCsv } = require("../_lib/github");
const { hashEmail, encryptEmail } = require("../_lib/emailCrypto");
const { publicTeam, findActiveMembership } = require("../_lib/teams");

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
      (m) =>
        m &&
        typeof m === "object" &&
        m.joined &&
        ((m.login && String(m.login).toLowerCase() === loginLc) ||
          hashes.includes(String(m.email_hash || "").toLowerCase()))
    );
    if (alreadyJoined) {
      await inviteCollaborator(user.login);
      return send(res, 200, { team: publicTeam(team), invited: user.login });
    }

    const conflict = findActiveMembership(store, { login: user.login, hashes }, slug);
    if (conflict) {
      return send(res, 409, {
        error: `Tu fais déjà partie de l'équipe "${conflict.name}". Quitte-la avant d'en rejoindre une autre.`,
      });
    }

    // Membre déclaré correspondant à l'un des emails : on confirme l'adhésion.
    const member = (team.members || []).find(
      (m) =>
        m &&
        typeof m === "object" &&
        hashes.includes(String(m.email_hash || "").toLowerCase())
    );
    if (member) {
      member.login = user.login;
      member.joined = true;
    } else {
      // Rejoindre librement : on ajoute le nouveau membre.
      const primaryEmail = uniqueEmails[0] || `${user.login}@users.noreply.github.com`;
      team.members = team.members || [];
      team.members.push({
        email_hash: hashEmail(primaryEmail),
        email_enc: encryptEmail(primaryEmail),
        login: user.login,
        joined: true,
      });
    }

    await commitFiles(
      {
        "teams.json": JSON.stringify(store, null, 2) + "\n",
        "participants.csv": buildParticipantsCsv(store),
      },
      `teams: ${user.login} rejoint ${slug}`
    );
    await inviteCollaborator(user.login);

    return send(res, 200, { team: publicTeam(team), invited: user.login });
  } catch (err) {
    return handleError(res, err);
  }
};
