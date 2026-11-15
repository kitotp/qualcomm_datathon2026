// Kangaroo City: language -> grade -> name, then topics and one problem at a time.
// The city lives in its own tab and is loaded only when that tab opens, so a
// student who only practises never downloads or runs the 3D code.
// Talks only to the GET routes in app/math-trainer/python/api.py.

import { UI_LANGUAGES, guessLanguage, itemText, setLanguage, t, topicName, translateError } from "./i18n.js";

const COLORS = ["#f4a6a6", "#f7c98b", "#f3e38a", "#a8dba8", "#9fd3e6", "#a9b8f0", "#c9a8ec", "#b9b9b9"];
const $ = id => document.getElementById(id);
const COIN = $("coins").querySelector("svg").outerHTML;
const DEBUG = new URLSearchParams(location.search).has("debug");

// What each shop item looks like on the map (its name and place are in i18n.js)
const ITEM_ICONS = {
  trees: '<rect x="3" y="22" width="12" height="5" rx="2" fill="#f7b8cf"/><rect x="21" y="18" width="3" height="10" rx="1" fill="#9b7b63"/><circle cx="22.5" cy="14" r="7" fill="#8fd19e"/>',
  rain_tank: '<rect x="9" y="8" width="14" height="19" rx="3" fill="#9ec9e2"/><rect x="7.5" y="5.5" width="17" height="4" rx="2" fill="#6e9fbf"/><path d="M23 22h3v6" stroke="#6e9fbf" stroke-width="2" fill="none" stroke-linecap="round"/><path d="M16 13.5c-1.6 2.2-2.4 3.5-2.4 4.6a2.4 2.4 0 0 0 4.8 0c0-1.1-.8-2.4-2.4-4.6z" fill="#fff"/>',
  roof_garden: '<rect x="4" y="17" width="24" height="12" rx="3" fill="#bccaf5"/><rect x="6" y="13" width="20" height="5" rx="2" fill="#8a6a55"/><circle cx="10.5" cy="12" r="3.5" fill="#8fd19e"/><circle cx="16" cy="10" r="4.2" fill="#6cc283"/><circle cx="21.5" cy="12" r="3.5" fill="#8fd19e"/>',
  solar: '<path d="M8 22v6M22 22v6" stroke="#b8b8b8" stroke-width="2"/><path d="M3 22l6-12h20l-6 12z" fill="#3b4f8f"/><path d="M6 16h20M14 10l-6 12M20.5 10l-6 12" stroke="#8ea2e0" stroke-width="1"/>',
  pool: '<rect x="3" y="9" width="26" height="15" rx="4" fill="#e9edf2"/><rect x="6" y="12" width="20" height="9" rx="2.5" fill="#7fd3f0"/><path d="M8.5 16.5c2-1.5 3 1.5 5 0s3 1.5 5 0 3 1.5 5 0" stroke="#fff" stroke-width="1.3" fill="none" stroke-linecap="round"/>',
  wind: '<path d="M16 13v16" stroke="#b8b8b8" stroke-width="2" stroke-linecap="round"/><path d="M16 11V2.5M16 11l7.5 4.5M16 11l-7.5 4.5" stroke="#cdd3da" stroke-width="3" stroke-linecap="round"/><circle cx="16" cy="11" r="2.2" fill="#9aa0a8"/>',
};

// ---------- remembered between sessions (localStorage can throw in private windows) ----------
const prefs = {
  get(key) { try { return localStorage.getItem("kc-" + key); } catch { return null; } },
  set(key, value) {
    try { value == null ? localStorage.removeItem("kc-" + key) : localStorage.setItem("kc-" + key, value); } catch { /* fine */ }
  },
};

const state = {
  language: prefs.get("language"), languageName: prefs.get("language-name"),
  grade: prefs.get("grade"), student: null, color: COLORS[4],
  topic: null, problem: null, answered: false, me: null, tiers: {}, shop: {}, maxFloors: 15,
  tab: "practice", city: null, CityView: null, quality: null,
};

async function api(...parts) {
  const response = await fetch("/api/" + parts.map(p => encodeURIComponent(p)).join("/"));
  const data = await response.json();
  if (data.error) throw new Error(translateError(data.error));
  return data;
}

let toastTimer;
function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 2400);
}

function show(id, visible = true) { $(id).hidden = !visible; }

// =====================================================================
// Setup: language, grade, name
// =====================================================================
function step(name) {
  closeMenu();
  for (const s of ["language", "grade", "name"]) show("step-" + s, s === name);
  [...$("dots").children].forEach((dot, i) => dot.classList.toggle("on", i === ["language", "grade", "name"].indexOf(name)));
  show("setup"); show("top", false); show("practice", false); show("city", false);
  if (state.city) state.city.setActive(false);
  if (name === "language") renderLanguages();
  if (name === "grade") renderGrades();
  if (name === "name") $("name").focus();
}

async function renderLanguages() {
  // Only the languages the page itself speaks, and only if the problems exist in them
  const { languages } = await api("languages");
  const offered = UI_LANGUAGES.map(code => languages.find(l => l.code === code)).filter(Boolean);
  $("languages").replaceChildren(...offered.map(l => {
    const b = document.createElement("button");
    b.className = "choice" + (l.code === state.language ? " on" : "");
    b.innerHTML = "<span></span><small></small>";
    b.querySelector("span").textContent = l.name;
    b.querySelector("small").textContent = l.name === l.english ? "" : l.english;
    b.onclick = () => {
      state.language = l.code;
      state.languageName = l.name;
      prefs.set("language", l.code);
      prefs.set("language-name", l.name);
      setLanguage(l.code);   // the whole page switches at once
      step("grade");
    };
    return b;
  }));
}

async function renderGrades() {
  const { grades } = await api("grades", state.language);
  $("grades").replaceChildren(...grades.map(g => {
    const b = document.createElement("button");
    b.className = "choice" + (String(g) === state.grade ? " on" : "");
    const [big, small] = t("gradeButton", g);
    b.innerHTML = "<b></b><small></small>";
    b.querySelector("b").textContent = big;
    b.querySelector("small").textContent = small;
    b.onclick = () => {
      state.grade = String(g);
      prefs.set("grade", state.grade);
      // A student who already has a house goes straight to the topics
      if (state.student) enterApp(); else step("name");
    };
    return b;
  }));
}

for (const color of COLORS) {
  const s = document.createElement("button");
  s.className = "swatch" + (color === state.color ? " on" : "");
  s.style.background = color;
  s.title = color;
  s.onclick = () => {
    state.color = color;
    document.querySelectorAll(".swatch").forEach(x => x.classList.toggle("on", x === s));
  };
  $("swatches").append(s);
}
document.querySelectorAll("[data-back]").forEach(b => { b.onclick = () => step(b.dataset.back); });

$("join").onclick = async () => {
  const name = $("name").value.trim();
  if (!name) { $("join-error").textContent = t("typeName"); return; }
  try {
    const { resident } = await api("join", name, state.color.slice(1));
    state.student = resident.student;
    prefs.set("student", state.student);
    enterApp();
  } catch (e) { $("join-error").textContent = e.message; }
};
$("name").addEventListener("keydown", e => { if (e.key === "Enter") $("join").click(); });

// =====================================================================
// The app: top bar, tabs, coins
// =====================================================================
async function enterApp() {
  const data = await api("me", state.student);
  state.me = data.resident;
  state.tiers = data.profile.tiers;
  show("setup", false); show("top");
  $("menu-name").textContent = state.me.student;
  $("menu-prefs").textContent = `${state.languageName || state.language} · ${t("gradeName", state.grade)}`;
  renderCoins();
  openTab("practice");
  showTopics();
}

function renderCoins(earned = 0) {
  $("coin-count").textContent = state.me.coins;
  if (earned) {
    $("coins").classList.remove("pulse");
    void $("coins").offsetWidth;   // restart the animation
    $("coins").classList.add("pulse");
  }
}

document.querySelectorAll(".tab").forEach(t => { t.onclick = () => openTab(t.dataset.tab); });

function openTab(tab) {
  state.tab = tab;
  closeMenu();
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("on", t.dataset.tab === tab));
  show("practice", tab === "practice");
  show("city", tab === "city");
  if (tab === "city") openCity(); else if (state.city) state.city.setActive(false);
}

// =====================================================================
// Settings menu
// =====================================================================
function openMenu() {
  show("menu");
  $("menu-button").setAttribute("aria-expanded", "true");
  renderQuality();
}
function closeMenu() {
  show("menu", false);
  show("pin-form", false);
  $("pin").value = "";
  $("pin-error").textContent = "";
  $("menu-button").setAttribute("aria-expanded", "false");
}
$("menu-button").onclick = e => { e.stopPropagation(); $("menu").hidden ? openMenu() : closeMenu(); };
$("menu").addEventListener("click", e => e.stopPropagation());
document.addEventListener("click", closeMenu);
document.addEventListener("keydown", e => { if (e.key === "Escape") closeMenu(); });

$("menu-language").onclick = () => step("language");
$("menu-switch").onclick = () => {
  prefs.set("student", null);
  location.href = location.pathname;
};

// Start over: the server checks the teacher's PIN, the page never knows it
$("menu-reset").onclick = () => { show("pin-form", $("pin-form").hidden); $("pin").focus(); };
$("pin-form").onsubmit = async e => {
  e.preventDefault();
  try {
    await api("reset", state.student, $("pin").value.trim() || "-");
    prefs.set("student", null);
    location.href = location.pathname;
  } catch (error) {
    $("pin-error").textContent = error.message;
    $("pin").select();
  }
};

async function quality() {
  if (!state.quality) {
    const { preferredQuality } = await import("./city.js");
    state.quality = preferredQuality();
  }
  return state.quality;
}
async function renderQuality() {
  const q = await quality();
  document.querySelectorAll("#quality button").forEach(b => b.classList.toggle("on", b.dataset.quality === q));
}
document.querySelectorAll("#quality button").forEach(b => {
  b.onclick = async () => {
    if (b.dataset.quality === await quality()) return;
    state.quality = b.dataset.quality;
    prefs.set("quality", state.quality);
    renderQuality();
    if (state.city) {
      // A fresh canvas: a WebGL context keeps the antialiasing it was created with
      state.city.dispose();
      const canvas = $("city-canvas").cloneNode(false);
      $("city-canvas").replaceWith(canvas);
      state.city = new state.CityView(canvas, state.quality);
      $("find-me").onclick = () => state.city.focusMe();
      if (state.tab === "city") { state.city.setActive(true); refreshCity(); }
    }
  };
});

// =====================================================================
// Practice
// =====================================================================
async function showTopics() {
  show("topics-view"); show("problem-view", false); show("empty", false);
  const { topics } = await api("topics", state.language, state.grade);
  $("topics").replaceChildren(...topics.map(topic => {
    const b = document.createElement("button");
    b.className = "topic";
    const tier = state.tiers[topic.name] || 1;
    b.innerHTML = `<b></b><small><span class="tier">${[1, 2, 3].map(i => `<i class="${i <= tier ? "on" : ""}"></i>`).join("")}</span>${t("level", tier)} · ${t("problems", topic.count)}</small>`;
    b.querySelector("b").textContent = topicName(topic.name);
    b.onclick = () => { state.topic = topic.name; nextProblem(); };
    return b;
  }));
}
$("back-topics").onclick = showTopics;
$("empty-back").onclick = showTopics;

async function nextProblem() {
  const { problem } = await api("next", state.student, state.language, state.grade, state.topic);
  showProblem(problem);
  refreshMatrix();
}

function showProblem(problem) {
  state.problem = problem;
  state.answered = false;
  show("topics-view", false);
  show("problem-view", Boolean(problem));
  show("empty", !problem);
  if (!problem) return;
  show("feedback", false);
  $("actions").replaceChildren();
  $("problem-meta").textContent = `${topicName(problem.topic)} · ${t("level", problem.tier)}`;
  $("problem-text").textContent = problem.text;
  $("options").replaceChildren(...Object.entries(problem.options).map(([letter, value]) => {
    const b = document.createElement("button");
    b.className = "option";
    b.dataset.letter = letter;
    b.innerHTML = `<b>${letter}</b><span></span>`;
    b.querySelector("span").textContent = value;
    b.onclick = () => answer(letter, b);
    return b;
  }));
  window.scrollTo({ top: 0 });
}

function floorHint(me) {
  if (me.next_floor_in == null) return t("allFloors", me.max_floors);
  return t("toNextFloor", me.next_floor_in, me.floors + 1);
}

async function answer(letter, button) {
  if (state.answered) return;
  state.answered = true;
  let result;
  try {
    result = await api("submit", state.student, state.language, state.grade, state.problem.id, letter);
  } catch (e) { state.answered = false; toast(e.message); return; }

  // Only the chosen option is colored: the page never learns the right letter
  for (const b of document.querySelectorAll(".option")) {
    b.disabled = true;
    if (b === button) b.classList.add(result.correct ? "right" : "wrong");
  }
  state.tiers[state.problem.topic] = result.tier;
  state.me = result.reward.resident;
  if (DEBUG) drawMatrix(result.frame);

  const fb = $("feedback");
  fb.hidden = false;
  fb.className = "feedback " + (result.correct ? "good" : "bad");
  fb.replaceChildren();
  const title = document.createElement("strong");
  const body = document.createElement("span");
  if (result.correct) {
    title.textContent = t("right");
    // The coins won, right under the answer
    const earned = document.createElement("div");
    earned.className = "earned";
    earned.innerHTML = `${COIN} ${t("coinsEarned", result.reward.coins_earned)}`;
    body.textContent = result.reward.new_floor
      ? t("houseGrew", result.reward.resident.floors)
      : floorHint(state.me);
    fb.append(title, earned, body);
    flyCoins(earned, result.reward.coins_earned);
  } else {
    title.textContent = t("wrong");
    body.textContent = result.trap || t("noTrap");
    fb.append(title, body);
    renderCoins();
    // The AI coach: one guiding question from the language model, only on request (it is slow on the board)
    const coach = document.createElement("button");
    coach.className = "ghost";
    coach.textContent = t("coach");
    const problemId = state.problem.id;
    coach.onclick = async () => {
      coach.disabled = true;
      coach.textContent = t("coachThinking");
      try {
        const reply = await api("coach", state.language, state.grade, problemId, letter);
        const hint = document.createElement("p");
        hint.className = "coach-hint";
        hint.textContent = reply.hint;
        fb.append(hint);
        coach.remove();
      } catch (e) { coach.disabled = false; coach.textContent = t("coach"); toast(e.message); }
    };
    $("actions").append(coach);
  }

  const actions = $("actions");
  if (result.easier_problem) {
    const easier = document.createElement("button");
    easier.className = "ghost";
    easier.textContent = t("easier");
    easier.onclick = () => { showProblem(result.easier_problem); refreshMatrix(); };
    actions.append(easier);
  }
  const next = document.createElement("button");
  next.className = "primary";
  next.textContent = t("next");
  next.onclick = nextProblem;
  actions.append(next);
  next.focus({ preventScroll: true });
}

// A coin flies from the reward to the counter in the corner
function flyCoins(from, amount) {
  const start = from.getBoundingClientRect();
  const end = $("coins").getBoundingClientRect();
  const el = document.createElement("div");
  el.className = "flying";
  el.innerHTML = COIN;
  el.style.left = start.left + 8 + "px";
  el.style.top = start.top + 4 + "px";
  document.body.append(el);
  requestAnimationFrame(() => requestAnimationFrame(() => {
    el.style.transform = `translate(${end.left - start.left}px, ${end.top - start.top}px) scale(.9)`;
    el.style.opacity = "0.3";
  }));
  setTimeout(() => { el.remove(); renderCoins(amount); }, 800);
}

// Keyboard: A to E answer
document.addEventListener("keydown", e => {
  if (state.tab !== "practice" || $("problem-view").hidden || e.target.tagName === "INPUT") return;
  const button = document.querySelector(`.option[data-letter="${e.key.toUpperCase()}"]`);
  if (button && !state.answered) button.click();
});

// =====================================================================
// City (loaded on first use)
// =====================================================================
let cityTimer;
async function openCity() {
  if (!state.city) {
    const { CityView } = await import("./city.js");
    state.CityView = CityView;
    state.city = new CityView($("city-canvas"), await quality());
  }
  state.city.setActive(true);
  $("find-me").onclick = () => state.city.focusMe();
  renderHouse();
  renderShop();
  await refreshCity();
  clearInterval(cityTimer);
  // Classmates' houses grow too: look again every few seconds, only while the tab is open
  cityTimer = setInterval(() => {
    if (state.tab === "city") refreshCity().catch(() => {}); else clearInterval(cityTimer);
  }, 4000);
}

async function refreshCity() {
  const { residents } = await api("city");
  const mine = residents.find(r => r.student === state.student);
  if (mine) { state.me = mine; renderCoins(); renderHouse(); renderShop(); }
  $("city-count").textContent = t("houses", residents.length);
  state.city.setResidents(residents, state.student);
}

function renderHouse() {
  const me = state.me;
  $("house-name").textContent = me.student;
  $("house-stats").textContent = t("houseStats", me.floors, me.max_floors, me.correct);
  const done = me.next_floor_in == null ? 1 : (me.floor_step - me.next_floor_in) / me.floor_step;
  $("house-progress").style.width = `${Math.round(100 * done)}%`;
  $("house-next").textContent = floorHint(me);
}

function renderShop() {
  $("shop").replaceChildren(...Object.entries(state.shop).map(([id, item]) => {
    const icon = ITEM_ICONS[id] || "";
    const [label, where] = itemText(id, item.label);
    const row = document.createElement("div");
    row.className = "item";
    row.innerHTML = `<span class="item-icon"><svg viewBox="0 0 32 32" aria-hidden="true">${icon}</svg></span>
      <span class="item-name"><span class="label"></span><small></small></span>`;
    row.querySelector(".label").textContent = label;
    row.querySelector("small").textContent = where;

    const owned = state.me.items.includes(id);
    const buy = document.createElement("button");
    buy.className = "price" + (owned ? " owned" : "");
    if (owned) {
      buy.textContent = t("owned");
      buy.disabled = true;
    } else {
      // The price is always visible, even when the student can't afford it yet
      buy.innerHTML = `${COIN} ${item.price}`;
      buy.disabled = state.me.coins < item.price;
      buy.title = buy.disabled ? t("needMore", item.price - state.me.coins) : t("buyFor", item.price);
      buy.onclick = async () => {
        try {
          state.me = (await api("buy", state.student, id)).resident;
          renderCoins(); renderShop();
          await refreshCity();
          state.city.celebrate(state.student);
        } catch (e) { toast(e.message); }
      };
    }
    row.append(buy);
    return row;
  }));
}

// =====================================================================
// Debug: the LED matrix emulator (open the page with ?debug)
// =====================================================================
const leds = [];
if (DEBUG) {
  show("matrix");
  for (let i = 0; i < 8 * 13; i++) {
    const led = document.createElement("div");
    led.className = "led";
    $("matrix").append(led);
    leds.push(led);
  }
}
function drawMatrix(frame) {
  frame.flat().forEach((v, i) => { leds[i].style.background = v ? `rgba(255, 74, 58, ${0.3 + v * 0.1})` : ""; });
}
async function refreshMatrix() {
  if (DEBUG) drawMatrix((await api("matrix")).frame);
}

// =====================================================================
// Start
// =====================================================================
(async () => {
  // A language from an older version of the page (not English or Catalan) is asked again
  if (state.language && !UI_LANGUAGES.includes(state.language)) state.language = null;
  setLanguage(state.language || guessLanguage());
  const shop = await api("shop");
  state.shop = shop.items;
  state.maxFloors = shop.max_floors;
  // ?student=anna opens the page as Anna (handy for demos); otherwise whoever was here last
  const name = new URLSearchParams(location.search).get("student") || prefs.get("student");
  if (name) {
    const { resident } = await api("me", name).catch(() => ({}));
    if (resident) state.student = resident.student; else prefs.set("student", null);
  }
  if (!state.language) return step("language");
  const { grades } = await api("grades", state.language).catch(() => ({ grades: [] }));
  if (!grades.length) return step("language");
  if (!state.grade || !grades.includes(Number(state.grade))) return step("grade");
  if (!state.student) return step("name");
  refreshMatrix();
  enterApp();
})();
