const { send, readBody, handleError, guard, authenticate, checkEventCode } = require("../_lib/http");
const {
  readTeams,
  commitFiles,
  slugify,
  getUserEmails,
  inviteCollaborator,
  buildParticipantsCsv,
} = require("../_lib/github");
const { hashEmail, encryptEmail } = require("../_lib/emailCrypto");
const { cleanEmails, publicTeam, findActiveMembership } = require("../_lib/teams");

const CHALLENGES = ["enedis", "sncf", "bpce-si", "lallemand", "action-logement", "imsa"];

function teamReadme(team) {
  const lines = [
    `# ${team.name}`,
    "",
    "## Équipe",
    "",
    `- Défi choisi : \`${team.challenge || "à préciser"}\``,
    `- Propriétaire : ${team.owner || "-"}`,
    "",
    "## Membres",
    "",
    ...team.members.map((m) => {
      const who = m.login ? `@${m.login}` : "en attente de connexion";
      const hash = m.email_hash ? ` — \`${m.email_hash.slice(0, 12)}…\`` : "";
      return `- ${who}${hash}`;
    }),
    "",
    "## Le projet",
    "",
    "Décrivez ici la solution proposée et son impact visé.",
    "",
  ];
  return lines.join("\n");
}

module.exports = async (req, res) => {
  if (guard(req, res)) return;
  try {
    const auth = await authenticate(req);
    if (!auth) return send(res, 401, { error: "Connecte-toi avec GitHub pour continuer." });

    if (req.method === "GET") {
      const store = await readTeams();
      return send(res, 200, { teams: (store.teams || []).map(publicTeam) });
    }

    if (req.method !== "POST") return send(res, 405, { error: "Méthode non autorisée" });
    if (!checkEventCode(req)) return send(res, 403, { error: "Code d'accès invalide." });

    const body = await readBody(req);
    const name = String(body.name || "").trim();
    const challenge = String(body.challenge || "").trim();

    if (name.length < 2) return send(res, 400, { error: "Le nom de l'équipe est trop court." });
    if (challenge && !CHALLENGES.includes(challenge)) {
      return send(res, 400, { error: "Défi inconnu." });
    }

    const slug = slugify(name);
    if (!slug) return send(res, 400, { error: "Nom d'équipe invalide." });

    const store = await readTeams();
    if (store.teams.some((t) => t.slug === slug)) {
      return send(res, 409, { error: `Une équipe "${slug}" existe déjà.` });
    }

    const { user, token } = auth;
    const creatorEmails = await getUserEmails(token);
    if (user.email) creatorEmails.push(user.email.toLowerCase());
    const creatorEmailSet = new Set(creatorEmails);
    const primaryEmail = creatorEmails[0] || `${user.login}@users.noreply.github.com`;
    const primaryHash = hashEmail(primaryEmail);

    const creatorHashes = [...new Set(creatorEmails.map((e) => hashEmail(e)).filter(Boolean))];
    const conflict = findActiveMembership(store, { login: user.login, hashes: creatorHashes });
    if (conflict) {
      return send(res, 409, {
        error: `Tu fais déjà partie de l'équipe "${conflict.name}". Quitte-la avant d'en créer une autre.`,
      });
    }

    const declared = cleanEmails(body.members);
    const members = [];
    const seen = new Set();
    for (const email of declared) {
      const hash = hashEmail(email);
      if (!hash || seen.has(hash)) continue;
      seen.add(hash);
      const isCreator = creatorEmailSet.has(email) || hash === primaryHash;
      members.push({
        email_hash: hash,
        email_enc: encryptEmail(email),
        login: isCreator ? user.login : null,
        joined: isCreator,
      });
    }
    if (!members.some((m) => m.email_hash === primaryHash)) {
      members.unshift({
        email_hash: primaryHash,
        email_enc: encryptEmail(primaryEmail),
        login: user.login,
        joined: true,
      });
    }
    // Le créateur est toujours membre confirmé
    const creatorEntry = members.find((m) => m.email_hash === primaryHash);
    if (creatorEntry) {
      creatorEntry.login = user.login;
      creatorEntry.joined = true;
    }

    const team = {
      slug,
      name,
      challenge: challenge || null,
      owner: user.login,
      members,
      created_at: new Date().toISOString(),
      created_by: user.login,
    };

    store.teams.push(team);
    store.teams.sort((a, b) => a.name.localeCompare(b.name));

    await commitFiles(
      {
        "teams.json": JSON.stringify(store, null, 2) + "\n",
        "participants.csv": buildParticipantsCsv(store),
        [`submissions/${slug}/README.md`]: teamReadme(team),
      },
      `teams: création de ${slug}`
    );

    await inviteCollaborator(user.login);

    return send(res, 201, { team: publicTeam(team), invited: user.login });
  } catch (err) {
    return handleError(res, err);
  }
};
