const { send, readBody, handleError, guard, authenticate, checkEventCode } = require("../_lib/http");
const {
  readTeams,
  commitFiles,
  slugify,
  getUserEmails,
  inviteCollaborator,
} = require("../_lib/github");

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const CHALLENGES = ["enedis", "sncf", "bpce-si", "lallemand", "action-logement", "imsa"];

function cleanEmails(list) {
  if (!Array.isArray(list)) return [];
  return [...new Set(list.map((e) => String(e).trim().toLowerCase()).filter((e) => EMAIL_RE.test(e)))];
}

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
    ...team.members.map((m) => `- ${m.email}${m.login ? ` (@${m.login})` : " (en attente de connexion)"}`),
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
      return send(res, 200, store);
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
    const primaryEmail =
      (user.email && user.email.toLowerCase()) || creatorEmails[0] || `${user.login}@users.noreply.github.com`;

    const declared = cleanEmails(body.members);
    const members = [];
    const seen = new Set();
    for (const email of declared) {
      if (seen.has(email)) continue;
      seen.add(email);
      const isCreator = creatorEmails.includes(email) || email === primaryEmail;
      members.push({ email, login: isCreator ? user.login : null, joined: isCreator });
    }
    if (!members.some((m) => m.email === primaryEmail)) {
      members.unshift({ email: primaryEmail, login: user.login, joined: true });
    }
    // Le créateur est toujours membre confirmé
    const creatorEntry = members.find((m) => m.email === primaryEmail);
    if (creatorEntry) {
      creatorEntry.login = user.login;
      creatorEntry.joined = true;
    }

    const team = {
      slug,
      name,
      challenge: challenge || null,
      owner: primaryEmail,
      members,
      created_at: new Date().toISOString(),
      created_by: user.login,
    };

    store.teams.push(team);
    store.teams.sort((a, b) => a.name.localeCompare(b.name));

    await commitFiles(
      {
        "teams.json": JSON.stringify(store, null, 2) + "\n",
        [`submissions/${slug}/README.md`]: teamReadme(team),
      },
      `teams: création de ${slug}`
    );

    await inviteCollaborator(user.login);

    return send(res, 201, { team, invited: user.login });
  } catch (err) {
    return handleError(res, err);
  }
};
