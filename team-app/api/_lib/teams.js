const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function cleanEmails(list) {
  if (!Array.isArray(list)) return [];
  return [...new Set(list.map((e) => String(e).trim().toLowerCase()).filter((e) => EMAIL_RE.test(e)))];
}

// Retire les valeurs chiffrées avant d'exposer l'équipe.
function publicTeam(team) {
  return {
    ...team,
    members: (team.members || []).map((m) => {
      if (!m || typeof m !== "object") return { email_hash: "", login: null, joined: false };
      return { email_hash: m.email_hash || "", login: m.login || null, joined: !!m.joined };
    }),
  };
}

// Renvoie l'équipe (hors `excludeSlug`) dont un membre confirmé correspond au
// login ou à l'une des empreintes d'email fournies. Sert à la règle « une seule
// équipe active par personne ».
function findActiveMembership(store, { login, hashes }, excludeSlug) {
  const loginLc = login ? String(login).toLowerCase() : null;
  const hashSet = new Set((hashes || []).map((h) => String(h || "").toLowerCase()).filter(Boolean));
  for (const team of (store && store.teams) || []) {
    if (excludeSlug && team.slug === excludeSlug) continue;
    for (const m of team.members || []) {
      if (!m || typeof m !== "object" || !m.joined) continue;
      if (loginLc && m.login && String(m.login).toLowerCase() === loginLc) return team;
      if (hashSet.size && hashSet.has(String(m.email_hash || "").toLowerCase())) return team;
    }
  }
  return null;
}

module.exports = {
  EMAIL_RE,
  cleanEmails,
  publicTeam,
  findActiveMembership,
};
