/* Hackathon IA for Impact — formation des équipes */
(function () {
  "use strict";

  const CFG = window.HACK_CONFIG || {};
  const TOKEN_KEY = "hack_token";

  const state = {
    token: localStorage.getItem(TOKEN_KEY) || null,
    user: null,
    teams: [],
    challenges: [],
    upload: { slug: null, name: null },
  };

  const $ = (sel) => document.querySelector(sel);
  const esc = (s) =>
    String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );

  /* ------------------------------ API ------------------------------ */
  async function api(path, { method = "GET", body, auth = true } = {}) {
    if (!CFG.apiBase || CFG.apiBase.includes("REMPLACE")) {
      throw new Error("Le backend n'est pas encore configuré (team-app/front/config.js).");
    }
    const headers = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (auth && state.token) headers["Authorization"] = "Bearer " + state.token;
    if (CFG.eventCode) headers["X-Event-Code"] = CFG.eventCode;

    const res = await fetch(CFG.apiBase.replace(/\/$/, "") + path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    let data = null;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    if (!res.ok) {
      const message = (data && data.error) || `Erreur ${res.status}`;
      if (res.status === 401 && auth) logout(false);
      throw new Error(message);
    }
    return data;
  }

  /* ----------------------------- Toasts ---------------------------- */
  function toast(message, kind) {
    const el = document.createElement("div");
    el.className = "toast" + (kind ? " toast--" + kind : "");
    el.textContent = message;
    $("#toasts").appendChild(el);
    setTimeout(() => el.remove(), 5000);
  }

  /* ----------------------------- Modals ---------------------------- */
  function openModal(id) {
    $("#" + id).classList.remove("hidden");
  }
  function closeModal(id) {
    $("#" + id).classList.add("hidden");
  }
  document.addEventListener("click", (e) => {
    const id = e.target.getAttribute && e.target.getAttribute("data-close");
    if (id) closeModal(id);
  });

  /* --------------------------- Auth (OAuth) ------------------------ */
  function setToken(token) {
    state.token = token;
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  }

  async function refreshUser() {
    try {
      state.user = await api("/api/me");
    } catch {
      state.user = null;
    }
    renderAuth();
  }

  function logout(notify) {
    setToken(null);
    state.user = null;
    renderAuth();
    renderTeams();
    if (notify !== false) toast("Déconnecté.");
  }

  function startLogin() {
    if (!CFG.apiBase) {
      toast("Le backend n'est pas encore configuré.", "error");
      return;
    }
    window.location.href = CFG.apiBase.replace(/\/$/, "") + "/api/auth/login";
  }

  // Récupère le token renvoyé par le callback OAuth dans le fragment d'URL.
  function consumeAuthRedirect() {
    const hash = window.location.hash.replace(/^#/, "");
    if (!hash) return false;
    const params = new URLSearchParams(hash);
    const token = params.get("access_token");
    const error = params.get("error");
    if (!token && !error) return false;
    history.replaceState(null, "", window.location.pathname + window.location.search);
    if (token) {
      setToken(token);
      return true;
    }
    toast("Connexion GitHub échouée : " + error, "error");
    return false;
  }

  /* ----------------------------- Render ---------------------------- */
  function renderAuth() {
    const logged = !!state.user;
    $("#loginBtn").classList.toggle("hidden", logged);
    $("#userChip").classList.toggle("hidden", !logged);
    $("#createTeamBtn").disabled = !logged;
    $("#teamsLoginHint").classList.toggle("hidden", logged);
    if (logged) {
      $("#userAvatar").src = state.user.avatar_url || "";
      $("#userLogin").textContent = state.user.login;
    }
  }

  function renderChallenges() {
    const grid = $("#challengeGrid");
    const select = $("#challengeSelect");
    grid.innerHTML = "";
    select.innerHTML = '<option value="">— Choisir un défi —</option>';
    state.challenges.forEach((c) => {
      const card = document.createElement("article");
      card.className = "card";
      card.innerHTML = `
        <div class="challenge__top">
          <img class="challenge__logo" src="${esc(c.logo)}" alt="${esc(c.company)}" />
          <span class="challenge__company">${esc(c.company)}</span>
        </div>
        <h3 class="challenge__title">${esc(c.title)}</h3>
        <p class="challenge__desc">${esc(c.description)}</p>
        <div class="challenge__footer">
          <a class="btn btn--ghost btn--small" href="${esc(CFG.repoUrl)}/tree/main/${esc(c.path)}" target="_blank" rel="noopener">Voir le défi</a>
          <span class="badge ${c.soon ? "badge--soon" : ""}">${c.soon ? "Bientôt" : "Disponible"}</span>
        </div>`;
      grid.appendChild(card);

      if (!c.soon) {
        const opt = document.createElement("option");
        opt.value = c.slug;
        opt.textContent = c.company + " — " + c.title;
        select.appendChild(opt);
      }
    });
  }

  function shortHash(hash) {
    const s = String(hash || "");
    return s ? s.slice(0, 10) + "…" : "";
  }

  function memberView(m) {
    const pending = !m.joined;
    return `<li>
      <span class="dot ${pending ? "dot--pending" : ""}"></span>
      <span>${m.login ? "@" + esc(m.login) : "en attente"}</span>
      ${m.email_hash ? `<span class="muted hash" title="${esc(m.email_hash)}">${esc(shortHash(m.email_hash))}</span>` : ""}
    </li>`;
  }

  function teamCard(team) {
    const challenge = state.challenges.find((c) => c.slug === team.challenge);
    const myHashes = (state.user && state.user.email_hashes) || [];
    const me = (team.members || []).find((m) => myHashes.includes(String(m.email_hash || "").toLowerCase()));
    const iAmMember = !!me;
    const joined = !!(me && me.joined && me.login);

    const card = document.createElement("article");
    card.className = "card";
    card.dataset.search = (team.name + " " + (team.challenge || "")).toLowerCase();
    card.innerHTML = `
      <div class="team__title">
        <h3 class="team__name">${esc(team.name)}</h3>
      </div>
      ${challenge ? `<span class="team__challenge">${esc(challenge.company)}</span>` : ""}
      <ul class="team__members">${(team.members || []).map(memberView).join("")}</ul>
      <div class="team__actions"></div>`;

    const actions = card.querySelector(".team__actions");
    if (state.user && joined) {
      const uploadBtn = document.createElement("button");
      uploadBtn.className = "btn btn--primary btn--small";
      uploadBtn.textContent = "Déposer un .zip";
      uploadBtn.onclick = () => openUpload(team);
      actions.appendChild(uploadBtn);

      const btn = document.createElement("button");
      btn.className = "btn btn--danger btn--small";
      btn.textContent = "Quitter";
      btn.onclick = () => leaveTeam(team.slug);
      actions.appendChild(btn);
    } else if (state.user && iAmMember) {
      const btn = document.createElement("button");
      btn.className = "btn btn--primary btn--small";
      btn.textContent = "Rejoindre";
      btn.onclick = () => joinTeam(team.slug);
      actions.appendChild(btn);
    } else if (state.user) {
      const span = document.createElement("span");
      span.className = "muted";
      span.textContent = "Ajoute ton email à ce défi pour le rejoindre.";
      actions.appendChild(span);
    }
    return card;
  }

  function renderTeams() {
    const grid = $("#teamGrid");
    const filter = ($("#teamSearch").value || "").toLowerCase();
    grid.innerHTML = "";
    const visible = state.teams.filter((t) => !filter || (t.name + " " + (t.challenge || "")).toLowerCase().includes(filter));
    visible.forEach((t) => grid.appendChild(teamCard(t)));
    $("#teamsEmpty").classList.toggle("hidden", state.teams.length !== 0);
  }

  /* ----------------------------- Data ------------------------------ */
  async function loadChallenges() {
    try {
      const res = await fetch("data/challenges.json", { cache: "no-cache" });
      state.challenges = await res.json();
    } catch {
      state.challenges = [];
    }
    renderChallenges();
  }

  async function loadTeams() {
    try {
      const data = await api("/api/teams");
      state.teams = (data && data.teams) || [];
    } catch (err) {
      state.teams = [];
      console.warn(err.message);
    }
    renderTeams();
  }

  /* --------------------------- Actions ----------------------------- */
  async function createTeam(form) {
    const name = (form.elements.namedItem("name").value || "").trim();
    const challenge = form.elements.namedItem("challenge").value;
    const members = Array.from(form.querySelectorAll('input[name="member"]'))
      .map((i) => i.value.trim())
      .filter(Boolean);

    if (!name) return toast("Donne un nom à ton équipe.", "error");
    const btn = $("#createSubmit");
    btn.disabled = true;
    btn.textContent = "Création…";
    try {
      const { team, invited } = await api("/api/teams", { method: "POST", body: { name, challenge, members } });
      closeModal("createModal");
      form.reset();
      renderEmailInputs([]);
      await loadTeams();
      toast(`Équipe « ${team.name} » créée !`, "success");
      if (!state.user.isCollaborator) {
        toast("Accepte l'invitation GitHub (@" + invited + ") pour déposer ton travail.", "success");
        await refreshUser();
      }
    } catch (err) {
      toast(err.message, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = "Créer l'équipe";
    }
  }

  async function joinTeam(slug) {
    try {
      await api("/api/teams/join", { method: "POST", body: { slug } });
      await loadTeams();
      toast("Tu as rejoint l'équipe !", "success");
      if (!state.user.isCollaborator) {
        toast("Accepte l'invitation GitHub pour déposer ton travail.", "success");
        await refreshUser();
      }
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function leaveTeam(slug) {
    try {
      await api("/api/teams/leave", { method: "POST", body: { slug } });
      await loadTeams();
      toast("Tu as quitté l'équipe.");
    } catch (err) {
      toast(err.message, "error");
    }
  }

  /* --------------------------- Upload .zip ------------------------- */
  const GITHUB_API = "https://api.github.com";

  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  function setUploadProgress(ratio, text) {
    const bar = $("#uploadBar");
    const status = $("#uploadStatus");
    $("#uploadProgress").classList.remove("hidden");
    if (bar) bar.style.width = Math.max(0, Math.min(1, ratio)) * 100 + "%";
    if (status && text) status.textContent = text;
  }

  // Appel direct à l'API GitHub avec le token OAuth de l'utilisateur (rôle `repo`).
  async function ghApi(path, { method = "GET", body } = {}) {
    const headers = {
      Authorization: "Bearer " + state.token,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
    };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const res = await fetch(GITHUB_API + path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    const text = await res.text();
    let data = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = text;
      }
    }
    if (!res.ok) {
      const err = new Error((data && data.message) || `GitHub ${res.status}`);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  function isProtectedError(err) {
    const msg = String((err && err.message) || "");
    return !!(err && err.status === 422 && /protected|status check|pull request/i.test(msg));
  }

  // Nettoie et sécurise un chemin d'entrée d'archive (anti zip-slip).
  function sanitizeZipPath(name) {
    const normalized = String(name).replace(/\\/g, "/").replace(/^\.\//, "");
    const parts = normalized.split("/").filter((s) => s && s !== ".");
    if (!parts.length || parts.some((s) => s === "..")) return null;
    if (parts.includes("__MACOSX")) return null;
    if (parts[0] === ".git" || parts.includes(".git")) return null;
    if (parts[parts.length - 1] === ".DS_Store") return null;
    return parts.join("/");
  }

  // Si tous les fichiers partagent un unique dossier racine, on le retire.
  function stripCommonRoot(paths) {
    if (!paths.length) return paths;
    const root = paths[0].split("/")[0];
    const allInside = paths.every((p) => p.includes("/") && p.split("/")[0] === root);
    if (!allInside) return paths;
    return paths.map((p) => p.slice(root.length + 1));
  }

  async function mapConcurrent(items, limit, fn) {
    let index = 0;
    const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
      while (index < items.length) {
        const i = index++;
        await fn(items[i], i);
      }
    });
    await Promise.all(workers);
  }

  async function createBlobs(files, onProgress) {
    const { owner, repo } = CFG;
    const tree = [];
    let done = 0;
    await mapConcurrent(files, 4, async (file) => {
      const blob = await ghApi(`/repos/${owner}/${repo}/git/blobs`, {
        method: "POST",
        body: { content: file.content, encoding: "base64" },
      });
      tree.push({ path: file.path, mode: "100644", type: "blob", sha: blob.sha });
      done += 1;
      if (onProgress) onProgress(done, files.length);
    });
    return tree;
  }

  async function commitToRef(files, message, refName, onProgress) {
    const { owner, repo } = CFG;
    for (let attempt = 0; ; attempt += 1) {
      try {
        const ref = await ghApi(`/repos/${owner}/${repo}/git/ref/heads/${refName}`);
        const baseCommitSha = ref.object.sha;
        const baseCommit = await ghApi(`/repos/${owner}/${repo}/git/commits/${baseCommitSha}`);
        const tree = await createBlobs(files, onProgress);
        const newTree = await ghApi(`/repos/${owner}/${repo}/git/trees`, {
          method: "POST",
          body: { base_tree: baseCommit.tree.sha, tree },
        });
        const newCommit = await ghApi(`/repos/${owner}/${repo}/git/commits`, {
          method: "POST",
          body: { message, tree: newTree.sha, parents: [baseCommitSha] },
        });
        await ghApi(`/repos/${owner}/${repo}/git/refs/heads/${refName}`, {
          method: "PATCH",
          body: { sha: newCommit.sha, force: false },
        });
        return { commitSha: newCommit.sha, html_url: newCommit.html_url };
      } catch (err) {
        if (err.status === 422 && !isProtectedError(err) && attempt < 3) {
          await sleep(500 * (attempt + 1));
          continue;
        }
        throw err;
      }
    }
  }

  async function pushViaPullRequest(files, message, slug, onProgress) {
    const { owner, repo } = CFG;
    const branch = `depot/${slug}-${Date.now()}`;
    const mainRef = await ghApi(`/repos/${owner}/${repo}/git/ref/heads/main`);
    await ghApi(`/repos/${owner}/${repo}/git/refs`, {
      method: "POST",
      body: { ref: `refs/heads/${branch}`, sha: mainRef.object.sha },
    });
    await commitToRef(files, message, branch, onProgress);
    const pr = await ghApi(`/repos/${owner}/${repo}/pulls`, {
      method: "POST",
      body: {
        title: `Dépôt ${slug} — ${files.length} fichier(s)`,
        head: branch,
        base: "main",
        body:
          `Dépôt automatique du dossier \`submissions/${slug}/\` depuis l'application des équipes ` +
          `(par @${state.user.login}).`,
      },
    });
    return pr.html_url;
  }

  function openUpload(team) {
    state.upload = { slug: team.slug, name: team.name };
    $("#uploadTarget").textContent = `submissions/${team.slug}/`;
    $("#zipInput").value = "";
    $("#uploadSubmit").disabled = true;
    $("#uploadProgress").classList.add("hidden");
    $("#uploadBar").style.width = "0%";
    $("#uploadStatus").textContent = "";
    openModal("uploadModal");
  }

  async function handleUpload() {
    const file = $("#zipInput").files[0];
    const slug = state.upload.slug;
    if (!file || !slug) return;

    const btn = $("#uploadSubmit");
    btn.disabled = true;
    btn.textContent = "Envoi…";
    try {
      if (!window.JSZip) throw new Error("Bibliothèque de décompression indisponible.");
      if (file.size > 150 * 1024 * 1024) {
        throw new Error("Archive trop volumineuse (> 150 Mo). Utilise git pour un dépôt aussi lourd.");
      }

      setUploadProgress(0.02, "Lecture de l'archive…");
      const zip = await window.JSZip.loadAsync(file);

      const entries = [];
      zip.forEach((relativePath, entry) => {
        if (entry.dir) return;
        const clean = sanitizeZipPath(relativePath);
        if (clean) entries.push({ path: clean, entry });
      });
      if (!entries.length) throw new Error("Aucun fichier exploitable dans l'archive.");

      let list = entries;
      if ($("#stripRoot").checked) {
        const stripped = stripCommonRoot(list.map((e) => e.path));
        list = list.map((e, i) => ({ path: stripped[i], entry: e.entry }));
      }

      const files = [];
      const skipped = [];
      for (let i = 0; i < list.length; i += 1) {
        const base64 = await list[i].entry.async("base64");
        const size = Math.floor((base64.length * 3) / 4);
        if (size > 90 * 1024 * 1024) {
          skipped.push(list[i].path);
        } else {
          files.push({ path: `submissions/${slug}/${list[i].path}`, content: base64 });
        }
        setUploadProgress(0.05 + (0.35 * (i + 1)) / list.length, `Décompression… ${i + 1}/${list.length}`);
      }
      if (!files.length) throw new Error("Aucun fichier à déposer (trop volumineux ?).");

      setUploadProgress(0.4, "Création des fichiers sur GitHub…");
      const message = `depot(${slug}): ${files.length} fichier(s) depuis le site`;
      const onProgress = (done, total) =>
        setUploadProgress(0.4 + (0.45 * done) / total, `Envoi… ${done}/${total}`);

      let prUrl = null;
      try {
        await commitToRef(files, message, "main", onProgress);
      } catch (err) {
        if (isProtectedError(err)) {
          setUploadProgress(0.4, "Branche protégée : ouverture d'une Pull Request…");
          prUrl = await pushViaPullRequest(files, message, slug, onProgress);
        } else {
          throw err;
        }
      }

      setUploadProgress(1, "Dépôt terminé.");
      if (skipped.length) {
        toast(`${skipped.length} fichier(s) ignoré(s) car trop volumineux (> 90 Mo).`, "error");
      }
      if (prUrl) {
        toast("Dépôt effectué via une Pull Request : " + prUrl, "success");
      } else {
        toast(`Fichiers déposés dans submissions/${slug}/`, "success");
      }
      setTimeout(() => closeModal("uploadModal"), 800);
    } catch (err) {
      let message = err.message;
      if (err.status === 403 || err.status === 404) {
        message = "Dépôt refusé : accepte l'invitation GitHub au dépôt puis réessaie.";
      }
      $("#uploadStatus").textContent = message;
      toast(message, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = "Déposer";
    }
  }

  /* --------------------- Création : lignes email ------------------- */
  function renderEmailInputs(values) {
    const list = $("#emailList");
    list.innerHTML = "";
    (values && values.length ? values : [""]).forEach((v) => addEmailRow(v));
  }
  function addEmailRow(value) {
    const row = document.createElement("div");
    row.className = "email-row";
    row.innerHTML = `
      <input class="input" type="email" name="member" placeholder="coequipier@exemple.fr" value="${esc(value || "")}" />
      <button type="button" class="btn btn--ghost btn--small" aria-label="Retirer">✕</button>`;
    row.querySelector("button").onclick = () => {
      if ($("#emailList").children.length > 1) row.remove();
      else row.querySelector("input").value = "";
    };
    $("#emailList").appendChild(row);
  }

  /* ----------------------------- Init ------------------------------ */
  function bind() {
    $("#repoLink").href = CFG.repoUrl || "#";
    $("#loginBtn").onclick = startLogin;
    $("#logoutBtn").onclick = () => logout(true);
    $("#createTeamBtn").onclick = () => {
      $("#createModal").classList.remove("hidden");
      renderEmailInputs([]);
    };
    $("#addEmailBtn").onclick = () => addEmailRow("");
    $("#zipInput").onchange = () => {
      $("#uploadSubmit").disabled = !$("#zipInput").files[0];
      $("#uploadStatus").textContent = "";
    };
    $("#uploadSubmit").onclick = handleUpload;
    $("#createForm").onsubmit = (e) => {
      e.preventDefault();
      createTeam(e.target);
    };
    $("#teamSearch").oninput = renderTeams;
  }

  async function init() {
    bind();
    renderEmailInputs([]);
    await loadChallenges();
    const justLogged = consumeAuthRedirect();
    if (state.token) await refreshUser();
    renderAuth();
    await loadTeams();
    if (justLogged && state.user) toast("Bonjour @" + state.user.login + " !", "success");
  }

  init();
})();
