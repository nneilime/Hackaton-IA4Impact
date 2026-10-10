const { send, readBody, handleError, guard, authenticate, checkEventCode } = require("../_lib/http");
const {
  readTeams,
  readParticipants,
  serializeParticipants,
  commitFiles,
} = require("../_lib/github");
const { hashEmail, encryptEmail } = require("../_lib/emailCrypto");
const { cleanEmails, publicTeam, findActiveMembership } = require("../_lib/teams");

module.exports = async (req, res) => {
  if (guard(req, res)) return;
  try {
    if (req.method !== "POST") return send(res, 405, { error: "Méthode non autorisée" });

    const auth = await authenticate(req);
    if (!auth) return send(res, 401, { error: "Connecte-toi avec GitHub pour continuer." });
    if (!checkEventCode(req)) return send(res, 403, { error: "Code d'accès invalide." });

    const { slug, emails } = await readBody(req);
    if (!slug) return send(res, 400, { error: "slug manquant" });

    const store = await readTeams();
    const team = store.teams.find((t) => t.slug === slug);
    if (!team) return send(res, 404, { error: "Équipe introuvable." });

    const { user } = auth;
    if (!team.owner || String(team.owner).toLowerCase() !== user.login.toLowerCase()) {
      return send(res, 403, { error: "Seul le créateur de l'équipe peut ajouter des membres." });
    }

    const list = cleanEmails(emails);
    if (!list.length) return send(res, 400, { error: "Aucune adresse email valide." });

    const participants = await readParticipants();
    const teamNameLc = String(team.name || "").toLowerCase();
    team.members = team.members || [];
    const existing = new Set(
      participants.rows
        .filter((r) => String(r.team_name || "").toLowerCase() === teamNameLc)
        .map((r) => String(r.email_hash || "").toLowerCase())
        .filter(Boolean)
    );
    const created_at = new Date().toISOString();
    const added = [];
    const skipped = [];
    for (const email of list) {
      const hash = hashEmail(email);
      if (!hash || existing.has(hash.toLowerCase())) continue;
      const conflict = findActiveMembership(store, participants.rows, { hashes: [hash] }, slug);
      if (conflict) {
        skipped.push({ email, team: conflict.name });
        continue;
      }
      existing.add(hash.toLowerCase());
      participants.rows.push({
        email_hash: hash,
        email_enc: encryptEmail(email),
        login: "",
        team_name: team.name,
      });
      team.members.push({ login: null, status: "invited", created_at });
      added.push(email);
    }

    if (added.length) {
      await commitFiles(
        {
          "teams.json": JSON.stringify(store, null, 2) + "\n",
          "participants.csv": serializeParticipants(participants.rows),
        },
        `teams: ${user.login} ajoute ${added.length} membre(s) à ${slug}`
      );
    }

    return send(res, 200, { team: publicTeam(team), added: added.length, skipped });
  } catch (err) {
    return handleError(res, err);
  }
};
