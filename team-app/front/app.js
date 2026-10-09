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

  /* --------------------------- Auth (device flow) ------------------ */
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

  async function startLogin() {
    openModal("loginModal");
    $("#loginStep1").classList.remove("hidden");
    $("#loginStepDone").classList.add("hidden");
    $("#deviceCode").textContent = "…";
    $("#loginStatus").textContent = "Demande du code…";
    try {
      const data = await api("/api/device/code", { method: "POST", auth: false });
      if (data.error) throw new Error(data.error_description || data.error);
      $("#deviceCode").textContent = data.user_code;
      $("#deviceLink").href = data.verification_uri || "https://github.com/login/device";
      $("#loginStatus").textContent = "En attente de l'autorisation…";
      pollToken(data.device_code, data.interval || 5);
    } catch (err) {
      $("#loginStatus").textContent = err.message;
      toast(err.message, "error");
    }
  }

  async function pollToken(deviceCode, interval) {
    let wait = interval;
    const loop = async () => {
      let data;
      try {
        data = await api("/api/device/token", { method: "POST", auth: false, body: { device_code: deviceCode } });
      } catch {
        setTimeout(loop, wait * 1000);
        return;
      }
      if (data.access_token) {
        setToken(data.access_token);
        $("#loginStep1").classList.add("hidden");
        $("#loginStepDone").classList.remove("hidden");
        await refreshUser();
        await loadTeams();
        setTimeout(() => closeModal("loginModal"), 600);
        toast("Bonjour @" + state.user.login + " !", "success");
        return;
      }
      if (data.error === "slow_down") wait += 5;
      if (data.error && data.error !== "authorization_pending" && data.error !== "slow_down") {
        $("#loginStatus").textContent = "Erreur : " + data.error;
        return;
      }
      setTimeout(loop, wait * 1000);
    };
    loop();
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

  function memberView(m) {
    const pending = !m.joined;
    return `<li>
      <span class="dot ${pending ? "dot--pending" : ""}"></span>
      <span>${esc(m.email)}</span>
      ${m.login ? `<span class="muted">@${esc(m.login)}</span>` : '<span class="muted">en attente</span>'}
    </li>`;
  }

  function teamCard(team) {
    const challenge = state.challenges.find((c) => c.slug === team.challenge);
    const myEmails = (state.user && state.user.emails) || [];
    const me = (team.members || []).find((m) => myEmails.includes(String(m.email).toLowerCase()));
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
    if (state.token) await refreshUser();
    renderAuth();
    await loadTeams();
  }

  init();
})();
