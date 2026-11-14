// The page's own text in the two languages the trainer offers: English and
// Catalan, the two languages our M3Kang copy has in full. The language a
// student picks sets both this text and the language of the problems.
// A string is either text with {0}, {1}... or a function, for plurals.

export const UI_LANGUAGES = ["eng", "cat"];

const s = (one, many) => n => (n === 1 ? one : many).replace("{n}", n);

// Catalan school years: grade 5 is "5è de primària", grade 7 is "1r d'ESO"
const CAT_YEARS = { 5: ["5è", "primària"], 6: ["6è", "primària"], 7: ["1r", "ESO"], 8: ["2n", "ESO"],
  9: ["3r", "ESO"], 10: ["4t", "ESO"], 11: ["1r", "Batxillerat"], 12: ["2n", "Batxillerat"] };
const catYear = g => CAT_YEARS[g] || [`${g}è`, ""];

const STRINGS = {
  eng: {
    appName: "Kangaroo City",
    chooseLanguage: "Choose a language",
    gradeTitle: "Which grade are you in?",
    gradeSub: "The problems follow your grade.",
    gradeButton: g => [String(g), "grade"],
    gradeName: g => `Grade ${g}`,
    back: "Back",
    nameTitle: "What's your name?",
    namePlaceholder: "Your name",
    colorSub: "Pick a color for your house",
    start: "Start",
    typeName: "Type your name first.",
    practice: "Practice",
    city: "City",
    yourCoins: "Your coins",
    settings: "Settings",
    menuLanguage: "Language and grade",
    menuSwitch: "Switch student",
    graphics: "Graphics",
    high: "High",
    highNote: "Soft shadows and rounded blocks",
    light: "Light",
    lightNote: "Faster on slower computers",
    startOver: "Start over",
    pinNote: "Only your teacher can erase your house, coins and levels.",
    pinPlaceholder: "Teacher PIN",
    erase: "Erase my progress",
    topicsTitle: "What do you want to practise?",
    backTopics: "← Topics",
    emptyTitle: "You've done every problem here",
    emptySub: "Pick another topic.",
    topics: "Topics",
    goHome: "Go to my house",
    myHouse: "My house",
    shop: "Shop",
    level: "level {0}",
    problems: s("{n} problem", "{n} problems"),
    allFloors: "Your house has all {0} floors. Spend your coins in the shop!",
    toNextFloor: (n, floor) => `${s("{n} more right answer", "{n} more right answers")(n)} to floor ${floor}.`,
    right: "Right!",
    coinsEarned: s("+{n} coin", "+{n} coins"),
    houseGrew: "Your house grew to {0} floors. Have a look in the city!",
    wrong: "Not this one",
    noTrap: "Read the question again and check each step.",
    easier: "Try an easier one",
    next: "Next problem",
    houses: n => `${s("{n} house", "{n} houses")(n)} · up to 50`,
    houseStats: (floor, max, right) => `Floor ${floor} of ${max} · ${s("{n} right answer", "{n} right answers")(right)}`,
    owned: "✓ Yours",
    needMore: s("{n} more coin needed", "{n} more coins needed"),
    buyFor: "Buy for {0} coins",
    topic: {
      arithmetic: "Arithmetic", numbers: "Numbers", geometry: "Geometry", spatial: "Spatial thinking",
      counting: "Counting", logic: "Logic", patterns: "Patterns", measurement: "Measurement",
    },
    item: {
      trees: ["Trees", "Next to your door"],
      rain_tank: ["Rainwater tank", "Saves rain for the garden"],
      roof_garden: ["Roof garden", "Plants on your roof"],
      solar: ["Solar panels", "Clean energy from the sun"],
      pool: ["Swimming pool", "A pool on your roof"],
      wind: ["Wind turbine", "Clean energy from the wind"],
    },
  },
  cat: {
    appName: "Ciutat Cangur",
    chooseLanguage: "Tria una llengua",
    gradeTitle: "A quin curs vas?",
    gradeSub: "Els problemes s'adapten al teu curs.",
    gradeButton: g => catYear(g),
    gradeName: g => {
      const [year, stage] = catYear(g);
      return stage ? `${year} ${stage === "ESO" ? "d'" : "de "}${stage}` : year;
    },
    back: "Enrere",
    nameTitle: "Com et dius?",
    namePlaceholder: "El teu nom",
    colorSub: "Tria un color per a la teva casa",
    start: "Comença",
    typeName: "Primer escriu el teu nom.",
    practice: "Practica",
    city: "Ciutat",
    yourCoins: "Les teves monedes",
    settings: "Configuració",
    menuLanguage: "Llengua i curs",
    menuSwitch: "Canvia d'alumne",
    graphics: "Gràfics",
    high: "Alta",
    highNote: "Ombres suaus i blocs arrodonits",
    light: "Lleugera",
    lightNote: "Més ràpida en ordinadors lents",
    startOver: "Torna a començar",
    pinNote: "Només el professorat pot esborrar la teva casa, les monedes i els nivells.",
    pinPlaceholder: "PIN del professorat",
    erase: "Esborra el meu progrés",
    topicsTitle: "Què vols practicar?",
    backTopics: "← Temes",
    emptyTitle: "Ja has fet tots els problemes d'aquest tema",
    emptySub: "Tria un altre tema.",
    topics: "Temes",
    goHome: "Vés a la meva casa",
    myHouse: "La meva casa",
    shop: "Botiga",
    level: "nivell {0}",
    problems: s("{n} problema", "{n} problemes"),
    allFloors: "La teva casa ja té les {0} plantes. Gasta les monedes a la botiga!",
    toNextFloor: (n, floor) =>
      `${s("Et falta {n} resposta correcta", "Et falten {n} respostes correctes")(n)} per a la planta ${floor}.`,
    right: "Correcte!",
    coinsEarned: s("+{n} moneda", "+{n} monedes"),
    houseGrew: "La teva casa ara té {0} plantes. Mira-la a la ciutat!",
    wrong: "Aquesta no és",
    noTrap: "Torna a llegir l'enunciat i revisa cada pas.",
    easier: "Prova'n un de més fàcil",
    next: "Següent problema",
    houses: n => `${s("{n} casa", "{n} cases")(n)} · fins a 50`,
    houseStats: (floor, max, right) =>
      `Planta ${floor} de ${max} · ${s("{n} resposta correcta", "{n} respostes correctes")(right)}`,
    owned: "✓ Ja ho tens",
    needMore: s("Et falta {n} moneda", "Et falten {n} monedes"),
    buyFor: "Compra per {0} monedes",
    topic: {
      arithmetic: "Aritmètica", numbers: "Nombres", geometry: "Geometria", spatial: "Visió espacial",
      counting: "Comptatge", logic: "Lògica", patterns: "Patrons", measurement: "Mesura",
    },
    item: {
      trees: ["Arbres", "Al costat de la porta"],
      rain_tank: ["Dipòsit d'aigua de pluja", "Guarda la pluja per al jardí"],
      roof_garden: ["Jardí al terrat", "Plantes al teu terrat"],
      solar: ["Plaques solars", "Energia neta del sol"],
      pool: ["Piscina", "Una piscina al terrat"],
      wind: ["Aerogenerador", "Energia neta del vent"],
    },
  },
};

// The server answers errors in English; the page shows them in the student's language
const CAT_ERRORS = [
  [/^No problems for this language and grade/, "No hi ha problemes per a aquesta llengua i aquest curs"],
  [/^Unknown problem/, "Problema desconegut"],
  [/^Choose A to E/, "Tria una opció de la A a la E"],
  [/^Starting over is off/, "No es pot tornar a començar: el professorat ha de posar un PIN al servidor"],
  [/^Wrong teacher PIN/, "El PIN no és correcte"],
  [/^A house color/, "Aquest color no és vàlid"],
  [/^The city is full/, "La ciutat és plena: com a màxim 50 cases"],
  [/^You already have it/, "Ja ho tens"],
  [/^Not enough coins/, "Encara no tens prou monedes"],
  [/^A student name needs 1 to (\d+)/, "El nom ha de tenir entre 1 i $1 caràcters"],
  [/^Unknown item/, "Aquest article no existeix"],
];

let current = "eng";

// Before a student picks, follow the browser: Catalan for a Catalan browser, else English
export function guessLanguage() {
  return /^ca\b/i.test(navigator.language || "") ? "cat" : "eng";
}

export function setLanguage(code) {
  current = STRINGS[code] ? code : "eng";
  document.documentElement.lang = current === "cat" ? "ca" : "en";
  document.title = t("appName");
  // Static text in index.html: data-i18n (text), data-i18n-title (title and aria-label), data-i18n-placeholder
  for (const el of document.querySelectorAll("[data-i18n]")) el.textContent = t(el.dataset.i18n);
  for (const el of document.querySelectorAll("[data-i18n-title]")) {
    el.title = t(el.dataset.i18nTitle);
    el.setAttribute("aria-label", el.title);
  }
  for (const el of document.querySelectorAll("[data-i18n-placeholder]")) el.placeholder = t(el.dataset.i18nPlaceholder);
}

export function t(key, ...args) {
  const value = STRINGS[current][key] ?? STRINGS.eng[key] ?? key;
  if (typeof value === "function") return value(...args);
  return typeof value === "string" ? value.replace(/\{(\d)\}/g, (_, i) => args[i]) : value;
}

export const topicName = topic => STRINGS[current].topic[topic] || topic;
export const itemText = (id, fallback) => STRINGS[current].item[id] || [fallback, ""];

export function translateError(message) {
  if (current !== "cat") return message;
  for (const [pattern, text] of CAT_ERRORS) {
    const match = message.match(pattern);
    if (match) return text.replace("$1", match[1]);
  }
  return message;
}
