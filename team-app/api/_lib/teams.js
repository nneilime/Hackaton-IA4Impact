const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function cleanEmails(list) {
  if (!Array.isArray(list)) return [];
  return [...new Set(list.map((e) => String(e).trim().toLowerCase()).filter((e) => EMAIL_RE.test(e)))];
}

// Retire toute donnée sensible avant d'exposer l'équipe (profils uniquement).
function publicTeam(team) {
  return {
    ...team,
    members: (team.members || []).map((m) => {
      if (!m || typeof m !== "object") return { login: null, status: "invited", created_at: null };
      const status = m.status || (m.joined ? "joined" : "invited");
      return { login: m.login || null, status, created_at: m.created_at || null };
    }),
  };
}

function findTeamByName(store, name) {
  const target = String(name || "").toLowerCase();
  return ((store && store.teams) || []).find((t) => String(t.name || "").toLowerCase() === target);
}

// Renvoie la ligne de participants (registre des hashes) correspondant à un
// login ou à l'une des empreintes d'email fournies.
function findParticipantRows(rows, { login, hashes } = {}) {
  const loginLc = login ? String(login).toLowerCase() : null;
  const hashSet = new Set((hashes || []).map((h) => String(h || "").toLowerCase()).filter(Boolean));
  return (rows || []).filter((r) => {
    if (loginLc && String(r.login || "").toLowerCase() === loginLc) return true;
    if (hashSet.size && hashSet.has(String(r.email_hash || "").toLowerCase())) return true;
    return false;
  });
}

// Renvoie l'équipe (hors `excludeSlug`) dont un membre confirmé correspond au
// login ou à l'une des empreintes fournies. Sert à la règle « une seule équipe
// active par personne ». Seules les lignes avec un login renseigné comptent :
// un membre simplement invité (login vide) ne bloque pas.
function findActiveMembership(store, participants, { login, hashes }, excludeSlug) {
  const rows = findParticipantRows(participants, { login, hashes }).filter((r) => r.login);
  for (const row of rows) {
    const team = findTeamByName(store, row.team_name);
    if (excludeSlug && team && team.slug === excludeSlug) continue;
    return team || { slug: null, name: row.team_name };
  }
  return null;
}

module.exports = {
  EMAIL_RE,
  cleanEmails,
  publicTeam,
  findTeamByName,
  findParticipantRows,
  findActiveMembership,
};
