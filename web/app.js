const API = "/api/v1";
const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const MONTHS = [
  "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
];
const TYPE_LABEL = {
  lecture: "Лекция",
  practice: "Практика",
  lab: "Лабораторная",
  exam: "Экзамен",
  other: "Другое",
};
const TYPE_COLOR = {
  lecture: "var(--lecture)",
  practice: "var(--practice)",
  lab: "var(--lab)",
  exam: "var(--exam)",
  other: "var(--other)",
};

const state = {
  token: localStorage.getItem("calendai_token"),
  user: JSON.parse(localStorage.getItem("calendai_user") || "null"),
  events: [],
  focused: startOfMonth(new Date()),
  selected: startOfDay(new Date()),
  lastSync: localStorage.getItem("calendai_last_sync"),
  parsed: [],
  mode: "login",
};

function startOfDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}
function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}
function pad(n) {
  return String(n).padStart(2, "0");
}
function isoWithOffset(date) {
  const offsetMin = -date.getTimezoneOffset();
  const sign = offsetMin >= 0 ? "+" : "-";
  const abs = Math.abs(offsetMin);
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:00${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`;
}
function toast(text) {
  const el = document.getElementById("toast");
  el.hidden = false;
  el.textContent = text;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.hidden = true; }, 2800);
}

async function api(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && state.token) headers.Authorization = `Bearer ${state.token}`;
  const res = await fetch(`${API}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail;
    const msg = typeof detail === "string" ? detail : JSON.stringify(detail || res.status);
    throw new Error(msg);
  }
  return data;
}

function showApp(on) {
  document.getElementById("auth").hidden = on;
  document.getElementById("app").hidden = !on;
}

function setAuthError(text) {
  const el = document.getElementById("auth-error");
  el.hidden = !text;
  el.textContent = text || "";
}

async function submitAuth() {
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;
  setAuthError("");
  try {
    const path = state.mode === "register" ? "/auth/register" : "/auth/login";
    const data = await api(path, { method: "POST", body: { email, password }, auth: false });
    state.token = data.access_token;
    state.user = data.user;
    localStorage.setItem("calendai_token", state.token);
    localStorage.setItem("calendai_user", JSON.stringify(state.user));
    await bootApp();
  } catch (err) {
    setAuthError(err.message);
  }
}

async function bootApp() {
  showApp(true);
  document.getElementById("who").textContent = state.user?.email || "аккаунт";
  await loadEvents();
  render();
}

async function loadEvents() {
  state.events = await api("/events");
}

function eventsOnDay(day) {
  const start = startOfDay(day).getTime();
  const end = start + 86400000;
  return state.events
    .filter((ev) => {
      const a = new Date(ev.start_time).getTime();
      const b = new Date(ev.end_time).getTime();
      return a < end && b > start;
    })
    .sort((a, b) => new Date(a.start_time) - new Date(b.start_time));
}

function daysWithEvents() {
  const set = new Set();
  for (const ev of state.events) {
    const d = new Date(ev.start_time);
    if (d.getFullYear() === state.focused.getFullYear() && d.getMonth() === state.focused.getMonth()) {
      set.add(d.getDate());
    }
  }
  return set;
}

function render() {
  document.getElementById("month-title").textContent =
    `${MONTHS[state.focused.getMonth()]} ${state.focused.getFullYear()}`;
  document.getElementById("weekdays").innerHTML = WEEKDAYS.map((d) => `<span>${d}</span>`).join("");

  const first = startOfMonth(state.focused);
  const leading = (first.getDay() + 6) % 7;
  const days = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate();
  const marked = daysWithEvents();
  const today = startOfDay(new Date());
  const cells = [];
  for (let i = 0; i < leading; i += 1) cells.push(`<span></span>`);
  for (let day = 1; day <= days; day += 1) {
    const date = new Date(first.getFullYear(), first.getMonth(), day);
    const selected = date.getTime() === state.selected.getTime();
    const isToday = date.getTime() === today.getTime();
    cells.push(`
      <button type="button" class="cell ${selected ? "selected" : ""} ${isToday ? "today" : ""}" data-day="${day}">
        <span>${day}</span>
        ${marked.has(day) ? '<span class="dot"></span>' : ""}
      </button>
    `);
  }
  document.getElementById("grid").innerHTML = cells.join("");

  const title = document.getElementById("day-title");
  title.textContent = `${pad(state.selected.getDate())}.${pad(state.selected.getMonth() + 1)}.${state.selected.getFullYear()}`;
  const list = eventsOnDay(state.selected);
  const box = document.getElementById("day-events");
  if (!list.length) {
    box.innerHTML = `<p class="muted">Нет занятий на этот день</p>`;
    return;
  }
  box.innerHTML = list.map((ev) => {
    const start = new Date(ev.start_time);
    const end = new Date(ev.end_time);
    const meta = [
      `${pad(start.getHours())}:${pad(start.getMinutes())} – ${pad(end.getHours())}:${pad(end.getMinutes())}`,
      ev.location,
      ev.teacher,
    ].filter(Boolean).join(" · ");
    return `
      <article class="event">
        <div class="swatch" style="background:${TYPE_COLOR[ev.event_type] || TYPE_COLOR.other}"></div>
        <div>
          <div>${ev.title}</div>
          <small>${meta}</small>
        </div>
        <span class="chip">${TYPE_LABEL[ev.event_type] || ev.event_type}</span>
      </article>
    `;
  }).join("");
}

async function createEvent(event) {
  event.preventDefault();
  const err = document.getElementById("ev-error");
  err.hidden = true;
  const title = document.getElementById("ev-title").value.trim();
  const [sh, sm] = document.getElementById("ev-start").value.split(":").map(Number);
  const [eh, em] = document.getElementById("ev-end").value.split(":").map(Number);
  const start = new Date(state.selected.getFullYear(), state.selected.getMonth(), state.selected.getDate(), sh, sm);
  const end = new Date(state.selected.getFullYear(), state.selected.getMonth(), state.selected.getDate(), eh, em);
  if (!end.getTime() || end <= start) {
    err.hidden = false;
    err.textContent = "Конец должен быть позже начала";
    return;
  }
  try {
    await api("/events", {
      method: "POST",
      body: {
        title,
        event_type: document.getElementById("ev-type").value,
        start_time: isoWithOffset(start),
        end_time: isoWithOffset(end),
        location: document.getElementById("ev-location").value.trim() || null,
      },
    });
    document.getElementById("event-dialog").close();
    await loadEvents();
    render();
    toast("Занятие сохранено");
  } catch (e) {
    err.hidden = false;
    err.textContent = e.message;
  }
}

async function runSync() {
  try {
    const data = await api("/sync", {
      method: "POST",
      body: {
        last_sync_timestamp: state.lastSync,
        client_changes: [],
      },
    });
    state.lastSync = data.sync_timestamp;
    localStorage.setItem("calendai_last_sync", state.lastSync);
    await loadEvents();
    render();
    toast(`Синк: пришло ${data.server_changes.length} изменений`);
  } catch (e) {
    toast(e.message);
  }
}

async function parseText() {
  const text = document.getElementById("ai-text").value.trim();
  if (!text) return;
  try {
    const data = await api("/ai/parse-text", { method: "POST", body: { text } });
    state.parsed = data.events || [];
    const preview = document.getElementById("ai-preview");
    preview.hidden = false;
    preview.textContent = state.parsed.length
      ? state.parsed.map((ev) => `${ev.title} [${ev.event_type}]\n${ev.start_time} → ${ev.end_time}\n${ev.location || "—"}`).join("\n\n")
      : "Ничего не распознано";
    document.getElementById("btn-confirm").disabled = !state.parsed.length;
    toast("Распознавание готово");
  } catch (e) {
    toast(e.message);
  }
}

async function confirmParsed() {
  if (!state.parsed.length) return;
  try {
    const created = await api("/ai/confirm", { method: "POST", body: { events: state.parsed } });
    state.parsed = [];
    document.getElementById("btn-confirm").disabled = true;
    await loadEvents();
    render();
    toast(`Добавлено: ${created.length}`);
  } catch (e) {
    toast(e.message);
  }
}

function logout() {
  state.token = null;
  state.user = null;
  localStorage.removeItem("calendai_token");
  localStorage.removeItem("calendai_user");
  showApp(false);
}

document.getElementById("tab-login").onclick = () => {
  state.mode = "login";
  document.getElementById("tab-login").classList.add("on");
  document.getElementById("tab-register").classList.remove("on");
  document.getElementById("auth-submit").textContent = "Войти";
};
document.getElementById("tab-register").onclick = () => {
  state.mode = "register";
  document.getElementById("tab-register").classList.add("on");
  document.getElementById("tab-login").classList.remove("on");
  document.getElementById("auth-submit").textContent = "Создать аккаунт";
};
document.getElementById("auth-submit").onclick = submitAuth;
document.getElementById("btn-logout").onclick = logout;
document.getElementById("btn-sync").onclick = runSync;
document.getElementById("prev-month").onclick = () => {
  state.focused = new Date(state.focused.getFullYear(), state.focused.getMonth() - 1, 1);
  state.selected = state.focused;
  render();
};
document.getElementById("next-month").onclick = () => {
  state.focused = new Date(state.focused.getFullYear(), state.focused.getMonth() + 1, 1);
  state.selected = state.focused;
  render();
};
document.getElementById("grid").addEventListener("click", (event) => {
  const btn = event.target.closest("[data-day]");
  if (!btn) return;
  state.selected = new Date(state.focused.getFullYear(), state.focused.getMonth(), Number(btn.dataset.day));
  render();
});
document.getElementById("btn-add").onclick = () => {
  document.getElementById("ev-error").hidden = true;
  document.getElementById("event-dialog").showModal();
};
document.getElementById("ev-cancel").onclick = () => document.getElementById("event-dialog").close();
document.getElementById("event-form").onsubmit = createEvent;
document.getElementById("btn-parse").onclick = parseText;
document.getElementById("btn-confirm").onclick = confirmParsed;

if (state.token) bootApp().catch(() => logout());
