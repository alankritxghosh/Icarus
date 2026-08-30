import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir =
  "/Users/alankritghosh/JARVIS /jarvis_engineering/outputs/019fb63b-5805-7fe2-a1a6-090b7a6f0688";
const inputPath = `${outputDir}/geo_candidates_enriched.json`;
const outputPath = `${outputDir}/Icarus_Geography_100_Email_Pipeline.xlsx`;
const snapshotDate = "2026-08-02";
const snapshotYear = 2026;

const existingScheduled = [
  ["ComplyDo", "info@complydo.io", "2026-08-04", "Previously scheduled"],
  ["Zeit AI", "founders@zeit-ai.com", "2026-08-04", "Previously scheduled"],
  ["Alguna", "founders@alguna.io", "2026-08-04", "Previously scheduled"],
  ["Alloy / L2 Labs", "andrew@l2labs.ai", "2026-08-04", "Previously scheduled"],
  ["Civtiq", "ben@civtiq.com", "2026-08-04", "Previously scheduled"],
  ["Delta", "hiring@learndelta.ai", "2026-08-04", "Previously scheduled"],
  ["Revion", "careers@revion.inc", "2026-08-04", "Previously scheduled"],
  ["Eduvero", "info@eduvero.com", "2026-08-04", "Previously scheduled"],
  ["Abacus", "brandon@getabacus.com", "2026-08-04", "Previously scheduled"],
  ["Phaselaw", "hello@phase.law", "2026-08-04", "Previously scheduled"],
  ["Dedalus Labs", "win@dedaluslabs.ai", "2026-08-04", "Previously scheduled"],
  ["PosterChild", "Leandrew@posterchild.ai", "2026-08-04", "Previously scheduled"],
  ["CTGT", "hello@ctgt.ai", "2026-08-04", "Previously scheduled"],
  ["DrSwarm", "jobs@drswarm.com", "2026-08-04", "Previously scheduled"],
  ["AgentMail", "founders@agentmail.cc", "2026-08-04", "Previously scheduled"],
  ["Caro", "info@carohq.com", "2026-08-04", "Previously scheduled"],
  ["Manufact", "luigi@manufact.com", "2026-08-04", "Previously scheduled"],
];

const geographyMatchers = {
  "San Francisco": /san francisco/i,
  "New York": /new york/i,
  London: /london/i,
  Chicago: /chicago/i,
};

const extrasReady = [
  {
    company: "MYLO",
    geography: "Dubai",
    team: 2,
    founded: 2025,
    foundedEvidence: "Official MYLO About page: Founded 2025; HQ Dubai.",
    role: "Lead Engineer, Technical Owner",
    roleUrl: "https://wellfound.com/company/mylo-12/jobs",
    poc: "Acer Jamal",
    pocTitle: "Founder & CEO",
    email: "acer@mrmylo.com",
    emailSource:
      "https://www.linkedin.com/posts/acerjamal_i-made-a-decision-last-week-that-felt-counterintuitive-activity-7445742349327998976-sAJg",
    pocLinkedIn: "https://ae.linkedin.com/in/acerjamal",
    companyLinkedIn: "https://www.linkedin.com/company/mrmylo/",
    website: "https://mrmylo.io/",
    context:
      "MYLO is a Dubai loyalty-intelligence startup that unifies UAE rewards programs and translates balances into AED. Its two-person team is hiring a founding technical owner ahead of its 2026 launch.",
    useCase:
      "Use Icarus to preserve why loyalty integrations, card-ranking logic, privacy masking and partner-specific rules changed. The highest-value question is which product or compliance decision introduced each data-flow constraint.",
    contactType: "Founder direct",
    confidence: "High",
    sources:
      "https://mrmylo.io/about | https://wellfound.com/company/mylo-12/jobs | https://wellfound.com/company/mylo-12/people | https://www.linkedin.com/company/mrmylo/ | https://www.linkedin.com/posts/acerjamal_i-made-a-decision-last-week-that-felt-counterintuitive-activity-7445742349327998976-sAJg",
  },
  {
    company: "Yander",
    geography: "Dubai",
    team: 2,
    founded: 2025,
    foundedEvidence: "Official LinkedIn company page lists 2025 and 2-10 employees.",
    role: "Founding SaaS Engineer",
    roleUrl: "https://wellfound.com/jobs/3826979-founding-saas-engineer",
    poc: "Jordan Hayes",
    pocTitle: "Co-founder",
    email: "jordan@yanderlabs.com",
    emailSource: "https://www.yander.ai/security",
    pocLinkedIn: "https://www.linkedin.com/in/jordan-hayes",
    companyLinkedIn: "https://www.linkedin.com/company/yander",
    website: "https://www.yander.ai/",
    context:
      "Yander is a Dubai-linked two-person startup building an AI recruiting agent and multi-tenant automation platform. Its current founding-engineer role spans retrieval, orchestration, integrations and tenant isolation.",
    useCase:
      "Use Icarus to recover why agent orchestration, retrieval, tenant isolation and data-processing choices changed. It is especially relevant when security and product docs drift from implementation history.",
    contactType: "Founder direct",
    confidence: "High",
    sources:
      "https://wellfound.com/jobs/3826979-founding-saas-engineer | https://www.linkedin.com/company/yander | https://www.yander.ai/security | https://www.yander.ai/dpa",
  },
  {
    company: "akakAI",
    geography: "Dallas, Texas",
    team: 2,
    founded: 2025,
    foundedEvidence: "Official About/FAQ copy says founded 2025 in Dallas.",
    role: "Open call for engineers and researchers",
    roleUrl: "https://akakai.com/",
    poc: "Zayd Malik",
    pocTitle: "Founder & CEO",
    email: "hello@akakai.com",
    emailSource: "https://akakai.com/",
    pocLinkedIn: "",
    companyLinkedIn: "",
    website: "https://akakai.com/",
    context:
      "akakAI is a two-person Dallas research lab shipping autonomous AI workers and a multi-model routing product. Its official site currently invites engineers and researchers to submit work.",
    useCase:
      "Use Icarus to preserve why agent autonomy, model routing, memory and action-governance choices evolved. The best wedge is cited architectural context as the lab moves from two products into a shared runtime.",
    contactType: "Company general",
    confidence: "Medium",
    sources: "https://akakai.com/",
  },
];

const extrasNeeds = [
  [
    "Alka",
    "Dallas, Texas",
    "1-10",
    "Senior AI Frontend Engineer; Staff Infrastructure Engineer",
    "https://wellfound.com/company/alka-intelligence/jobs",
    "Ivo Stranic (Head of Engineering)",
    "team@alka.ai",
    "Named founder is not publicly identified; POC is senior technical leadership, not founder-level.",
    "Identify a founder-level POC before outreach.",
    "https://www.alka.ai/ | https://wellfound.com/company/alka-intelligence/people",
  ],
  [
    "Paddox Technologies",
    "Dallas, Texas",
    "1-10",
    "Software Engineer",
    "https://wellfound.com/jobs/4417556-software-engineer",
    "Veer Waje (Founder)",
    "hello@paddoxtechnologies.com",
    "Founding year is not independently published.",
    "Verify the incorporation or founding year.",
    "https://wellfound.com/company/paddox-technologies | https://paddoxtechnologies.com/",
  ],
  [
    "Corvara / Certamen",
    "Dallas, Texas",
    "1-10",
    "Unreal Engine Engineer / Developer",
    "https://wellfound.com/jobs/4403098-unreal-engine-engineer-developer",
    "David Gross (Founder)",
    "",
    "No published email and no independently verified founding year.",
    "Verify age and obtain a published contact route.",
    "https://wellfound.com/jobs/4403098-unreal-engine-engineer-developer | https://www.certamenlife.com",
  ],
  [
    "Luxira",
    "Dallas, Texas",
    "1-10",
    "Founding Senior Firmware and IoT Engineer",
    "https://wellfound.com/company/luxira",
    "Kelechi Amadi (Founder)",
    "info@luxira.io",
    "Founding year is not independently published.",
    "Verify the incorporation or founding year.",
    "https://wellfound.com/company/luxira | https://luxira.io/",
  ],
  [
    "Rizzly",
    "Chicago",
    "1-10",
    "Founding Engineer",
    "https://wellfound.com/jobs/4295726-founding-engineer-for-profitable-start-up-full-time-or-contract",
    "David Kim (Founder)",
    "",
    "No published email and no independently verified founding year.",
    "Verify age and obtain a published contact route.",
    "https://wellfound.com/jobs/4295726-founding-engineer-for-profitable-start-up-full-time-or-contract | https://www.rizzly.io/",
  ],
  [
    "ChronoCraft",
    "Houston",
    "1-10",
    "Engine Software Engineer; Graphics Software Engineer",
    "https://wellfound.com/jobs/3313029-engine-software-engineer",
    "Kurt G (Founder/CEO)",
    "",
    "Founding year is verified as 2020, but no current published contact email was found.",
    "Obtain a published founder or company contact route.",
    "https://wellfound.com/company/chronocraft-1/people | https://chronocraftgame.com/conditions",
  ],
];

const extrasExcluded = [
  [
    "SecRecon",
    "Houston",
    "Wellfound currently shows zero jobs; an older co-founder listing is no longer live.",
    "Recheck only after a new engineering role is published.",
    "https://wellfound.com/company/secrecon",
  ],
  [
    "Popcorn AI",
    "Dubai",
    "The engineering listing surfaced in search is roughly ten months old and could not be confirmed as current.",
    "Require a fresh engineering role before outreach.",
    "https://wellfound.com/jobs/3256030-senior-software-engineer",
  ],
  [
    "Volis",
    "Dallas, Texas",
    "Current LinkedIn headcount is 11-50.",
    "Hold for a future 11-50 campaign.",
    "https://www.linkedin.com/company/volis-technology",
  ],
];

function cleanSentence(text) {
  return String(text || "")
    .replace(/\s+/g, " ")
    .trim();
}

function companyContext(row) {
  const one = cleanSentence(row.oneLiner).replace(/[.]+$/, "");
  const long = cleanSentence(row.longDescription);
  const firstLong = (long.split(/(?<=[.!?])\s+/)[0] || "").replace(/[.]+$/, "");
  const hiring = row.roles?.[0]?.title || "an engineering role";
  const first = one ? `${row.name}: ${one}.` : `${row.name} is an early-stage technology company.`;
  const secondBase =
    firstLong && one && !firstLong.toLowerCase().includes(one.toLowerCase())
      ? `${firstLong}.`
      : `Its ${row.teamSize}-person team is hiring ${hiring}.`;
  return `${first} ${secondBase}`.slice(0, 460);
}

function icarusUseCase(row) {
  const text = `${row.oneLiner} ${row.longDescription} ${row.roles?.map((r) => r.title).join(" ")}`.toLowerCase();
  if (/health|clinical|patient|medical|care/.test(text)) {
    return "Preserve why clinical workflow, privacy, integration, model-versus-deterministic and audit decisions changed. Icarus can answer those questions with cited GitHub evidence instead of relying on founder memory.";
  }
  if (/finance|fintech|account|payment|insurance|compliance/.test(text)) {
    return "Preserve why compliance, data-model, risk, reconciliation and integration decisions changed. Icarus can ground audit-sensitive product history in exact commits and code evidence.";
  }
  if (/robot|hardware|quantum|optic|sensor|firmware/.test(text)) {
    return "Preserve why hardware-software interfaces, calibration, simulation, evaluation and reliability tradeoffs changed. Icarus can reconnect implementation choices to the evidence that originally justified them.";
  }
  if (/agent|ai|model|llm|retriev|inference/.test(text)) {
    return "Preserve why orchestration, retrieval, eval, model, guardrail and customer-integration decisions changed. Icarus gives the growing team cited architectural context rather than another generic code explainer.";
  }
  return "Preserve the recorded why behind architecture, integrations and customer-specific tradeoffs as the first engineering team grows. Icarus can return a cited answer or an honest unknown from GitHub history.";
}

function contactType(email) {
  const local = String(email).split("@")[0].toLowerCase();
  if (["founders", "founder"].includes(local)) return "Founders alias";
  if (["hello", "hi", "team", "contact", "info"].includes(local)) return "Company general";
  if (["careers", "recruiting", "jobs", "hiring"].includes(local)) return "Recruiting / careers";
  return "Founder / named direct";
}

function locationPass(row) {
  const matcher = geographyMatchers[row.discoveryGeography];
  return matcher ? matcher.test(row.location || "") : false;
}

function readyFromYc(row) {
  return (
    locationPass(row) &&
    row.teamSize >= 1 &&
    row.teamSize <= 10 &&
    row.foundedYear &&
    row.founders?.[0]?.name &&
    row.preferredEmail &&
    !row.duplicateCompany &&
    !row.duplicateRecipient
  );
}

function strictMatrix(row) {
  const founder = row.founders[0];
  return {
    company: row.name,
    geography: row.discoveryGeography,
    team: row.teamSize,
    founded: row.foundedYear,
    foundedEvidence: `Y Combinator company profile lists founded ${row.foundedYear}.`,
    role: row.roles[0]?.title || "",
    roleUrl: row.roles[0]?.url || row.ycUrl,
    poc: founder.name,
    pocTitle: founder.title || "Founder",
    email: row.preferredEmail,
    emailSource: row.emailSource,
    pocLinkedIn: founder.linkedin || "",
    companyLinkedIn: row.companyLinkedIn || "",
    website: row.website || "",
    context: companyContext(row),
    useCase: icarusUseCase(row),
    contactType: contactType(row.preferredEmail),
    confidence: ["Founder / named direct", "Founders alias"].includes(contactType(row.preferredEmail))
      ? "High"
      : "Medium",
    sources: [row.ycUrl, row.roles[0]?.url, row.emailSource, row.companyLinkedIn]
      .filter(Boolean)
      .join(" | "),
  };
}

function titleBlock(sheet, range, title, subtitle, color, pale) {
  sheet.showGridLines = false;
  sheet.getRange(range).merge();
  const firstCell = range.split(":")[0];
  sheet.getRange(firstCell).values = [[title]];
  sheet.getRange(range).format = {
    fill: color,
    font: { bold: true, color: "#FFFFFF", size: 17 },
    verticalAlignment: "center",
  };
  sheet.getRange(range).format.rowHeight = 36;
  const startCol = range.split(":")[0].replace(/[0-9]/g, "");
  const endCol = range.split(":")[1].replace(/[0-9]/g, "");
  const subtitleRange = `${startCol}2:${endCol}2`;
  sheet.getRange(subtitleRange).merge();
  sheet.getRange(`${startCol}2`).values = [[subtitle]];
  sheet.getRange(subtitleRange).format = {
    fill: pale,
    font: { color, italic: true, size: 10 },
    verticalAlignment: "center",
    wrapText: true,
  };
  sheet.getRange(subtitleRange).format.rowHeight = 34;
}

function styleTable(sheet, range, headerRange, bodyRange, headerColor, tableName, style) {
  sheet.getRange(range).format = {
    font: { color: "#172033", size: 9 },
    verticalAlignment: "top",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: "#D8DEE9" },
  };
  sheet.getRange(headerRange).format = {
    fill: headerColor,
    font: { bold: true, color: "#FFFFFF", size: 9 },
    verticalAlignment: "center",
    wrapText: true,
  };
  sheet.getRange(headerRange).format.rowHeight = 44;
  sheet.getRange(bodyRange).format.rowHeight = 80;
  const table = sheet.tables.add(range, true, tableName);
  table.style = style;
  table.showFilterButton = true;
  sheet.getRange(headerRange).format.fill = headerColor;
}

const ycRows = JSON.parse(await fs.readFile(inputPath, "utf8"));
const ready = [...ycRows.filter(readyFromYc).map(strictMatrix), ...extrasReady].sort((a, b) =>
  `${a.geography}|${a.company}`.localeCompare(`${b.geography}|${b.company}`),
);

const needsYc = ycRows
  .filter(
    (row) =>
      !readyFromYc(row) &&
      !row.duplicateCompany &&
      !row.duplicateRecipient &&
      locationPass(row) &&
      row.teamSize >= 1 &&
      row.teamSize <= 10,
  )
  .map((row) => {
    const gaps = [];
    if (!row.foundedYear) gaps.push("founding year");
    if (!row.founders?.[0]?.name) gaps.push("founder POC");
    if (!row.preferredEmail) gaps.push("published email");
    return [
      row.name,
      row.discoveryGeography,
      `Team ${row.teamSize}`,
      row.roles?.[0]?.title || "",
      row.roles?.[0]?.url || row.ycUrl,
      row.founders?.[0]?.name
        ? `${row.founders[0].name} (${row.founders[0].title || "Founder"})`
        : "",
      row.preferredEmail || "",
      `Missing ${gaps.join(", ")}.`,
      gaps.includes("published email")
        ? "Find a published founder or company email; do not infer the address."
        : "Complete the missing verification before outreach.",
      [row.ycUrl, row.emailSource].filter(Boolean).join(" | "),
    ];
  });
const needs = [...needsYc, ...extrasNeeds];

const excludedYc = ycRows
  .filter(
    (row) =>
      row.duplicateCompany ||
      row.duplicateRecipient ||
      !locationPass(row) ||
      !(row.teamSize >= 1 && row.teamSize <= 10),
  )
  .map((row) => {
    let reason = "";
    let next = "";
    if (row.duplicateCompany || row.duplicateRecipient) {
      reason = "Already present in the prior campaign or scheduled Gmail batch.";
      next = "Do not contact again in this campaign.";
    } else if (!locationPass(row)) {
      reason = `The role appeared in the geography search, but the company base is ${row.location || "not verified"}.`;
      next = "Reassign only if the requested geography is confirmed as the company base.";
    } else {
      reason = `Current public team size is ${row.teamSize || "not verified"}, outside the strict 1-10 gate.`;
      next = "Hold until the headcount returns to the requested range.";
    }
    return [row.name, row.discoveryGeography, reason, next, row.ycUrl];
  });
const excluded = [...excludedYc, ...extrasExcluded];

function buildReady(workbook) {
  const sheet = workbook.worksheets.add("Email Ready");
  const lastRow = ready.length + 5;
  titleBlock(
    sheet,
    "A1:V1",
    "Icarus Geography Prospect Batch — Email Ready",
    "Every row passes the original gate: company based in a requested city, 1-10 people, live engineering signal, named founder POC, verified founding year and a published email. Generic/recruiting mailboxes are clearly labeled; no address was guessed.",
    "#0F766E",
    "#CCFBF1",
  );
  sheet.getRange("A3").values = [["Net-new ready"]];
  sheet.getRange("B3").formulas = [[`=COUNTA(A6:A${lastRow})`]];
  sheet.getRange("D3").values = [["Founder/direct aliases"]];
  sheet.getRange("E3").formulas = [[
    `=COUNTIF(P6:P${lastRow},"Founder / named direct")+COUNTIF(P6:P${lastRow},"Founder direct")+COUNTIF(P6:P${lastRow},"Founders alias")`,
  ]];
  sheet.getRange("G3").values = [["General/recruiting routes"]];
  sheet.getRange("H3").formulas = [[`=B3-E3`]];
  sheet.getRange("J3").values = [["Checked"]];
  sheet.getRange("K3").values = [[snapshotDate]];
  sheet.getRange("A3:K3").format = {
    fill: "#F8FAFC",
    font: { color: "#334155", size: 10 },
    verticalAlignment: "center",
    borders: { preset: "outside", style: "thin", color: "#CBD5E1" },
  };
  for (const cell of ["A3", "D3", "G3", "J3"]) {
    sheet.getRange(cell).format.font = { bold: true, color: "#0F766E", size: 10 };
  }
  for (const cell of ["B3", "E3", "H3", "K3"]) {
    sheet.getRange(cell).format.font = { bold: true, color: "#0F172A", size: 11 };
  }
  const headers = [
    "Company",
    "Geography",
    "Team Size",
    "Founded",
    "Age (approx.)",
    "Founding Evidence",
    "Live Engineering Signal",
    "Role URL",
    "POC",
    "POC Title",
    "Published Email",
    "Email Source",
    "POC LinkedIn",
    "Company LinkedIn",
    "Website",
    "Contact Type",
    "Company Context (2-3 lines)",
    "Ideal Icarus Use Case",
    "Confidence",
    "Status",
    "Checked Date",
    "Verification Sources",
  ];
  sheet.getRange("A5:V5").values = [headers];
  const matrix = ready.map((row) => [
    row.company,
    row.geography,
    row.team,
    row.founded,
    null,
    row.foundedEvidence,
    row.role,
    row.roleUrl,
    row.poc,
    row.pocTitle,
    row.email,
    row.emailSource,
    row.pocLinkedIn,
    row.companyLinkedIn,
    row.website,
    row.contactType,
    row.context,
    row.useCase,
    row.confidence,
    "Email ready — not drafted or scheduled",
    snapshotDate,
    row.sources,
  ]);
  sheet.getRange(`A6:V${lastRow}`).values = matrix;
  sheet.getRange("E6").formulas = [['=IF(D6="","",$X$3-D6)']];
  sheet.getRange(`E6:E${lastRow}`).fillDown();
  sheet.getRange("X3").values = [[snapshotYear]];
  sheet.getRange("X3").format.font = { color: "#FFFFFF", size: 1 };
  styleTable(
    sheet,
    `A5:V${lastRow}`,
    "A5:V5",
    `A6:V${lastRow}`,
    "#0F766E",
    "GeoEmailReady",
    "TableStyleMedium4",
  );
  sheet.getRange(`A6:A${lastRow}`).format.font = { bold: true, color: "#0F172A", size: 10 };
  sheet.getRange(`E6:E${lastRow}`).format.fill = "#ECFDF5";
  sheet.getRange(`P6:P${lastRow}`).conditionalFormats.add("containsText", {
    text: "direct",
    format: { fill: "#DCFCE7", font: { color: "#166534", bold: true } },
  });
  sheet.getRange(`P6:P${lastRow}`).conditionalFormats.add("containsText", {
    text: "Recruiting",
    format: { fill: "#FEF3C7", font: { color: "#92400E", bold: true } },
  });
  const widths = [
    23, 18, 12, 11, 13, 34, 32, 38, 24, 24, 30, 38, 34, 34, 30, 22, 52, 56, 14, 30, 14, 58,
  ];
  widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, lastRow, 1).format.columnWidth = width;
  });
  sheet.getRange("X:X").format.columnWidth = 2;
  sheet.freezePanes.freezeRows(5);
  sheet.freezePanes.freezeColumns(2);
}

function buildNeeds(workbook) {
  const sheet = workbook.worksheets.add("Needs Verification");
  const lastRow = needs.length + 4;
  titleBlock(
    sheet,
    "A1:J1",
    "Promising but not email-ready",
    "These companies have a live engineering signal and public 1-10 headcount, but at least one load-bearing fact is missing. They do not count toward the 100-email target.",
    "#B45309",
    "#FEF3C7",
  );
  sheet.getRange("A4:J4").values = [[
    "Company",
    "Geography",
    "Team Evidence",
    "Engineering Signal",
    "Role URL",
    "Candidate POC",
    "Published Email",
    "Verification Gap",
    "Next Action",
    "Sources",
  ]];
  sheet.getRange(`A5:J${lastRow}`).values = needs;
  styleTable(
    sheet,
    `A4:J${lastRow}`,
    "A4:J4",
    `A5:J${lastRow}`,
    "#B45309",
    "GeoNeedsVerification",
    "TableStyleMedium7",
  );
  sheet.getRange(`A5:A${lastRow}`).format.font = { bold: true, color: "#0F172A", size: 10 };
  [24, 18, 16, 34, 40, 30, 30, 48, 46, 56].forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, lastRow, 1).format.columnWidth = width;
  });
  sheet.freezePanes.freezeRows(4);
}

function buildExcluded(workbook) {
  const sheet = workbook.worksheets.add("Excluded & Duplicates");
  const lastRow = excluded.length + 4;
  titleBlock(
    sheet,
    "A1:E1",
    "Excluded and duplicate companies",
    "This audit trail prevents accidental double-contacting and records why a superficially attractive listing failed the requested geography, team-size or current-hiring gate.",
    "#9A3412",
    "#FFEDD5",
  );
  sheet.getRange("A4:E4").values = [["Company", "Search Geography", "Why Excluded", "Next Action", "Source"]];
  sheet.getRange(`A5:E${lastRow}`).values = excluded;
  styleTable(
    sheet,
    `A4:E${lastRow}`,
    "A4:E4",
    `A5:E${lastRow}`,
    "#9A3412",
    "GeoExcluded",
    "TableStyleMedium9",
  );
  sheet.getRange(`A5:A${lastRow}`).format.font = { bold: true, color: "#0F172A", size: 10 };
  [25, 20, 64, 45, 52].forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, lastRow, 1).format.columnWidth = width;
  });
  sheet.freezePanes.freezeRows(4);
}

function buildCapacity(workbook) {
  const sheet = workbook.worksheets.add("Capacity Plan");
  titleBlock(
    sheet,
    "A1:H1",
    "August 3-7 capacity against the 100-founder target",
    "The target is treated as 100 total sends, inclusive of the 17 already scheduled. New research is counted only from the Email Ready sheet; no Gmail mutation was made in this research step.",
    "#1D4ED8",
    "#DBEAFE",
  );
  sheet.getRange("A4:B9").values = [
    ["Metric", "Count"],
    ["Target sends", 100],
    ["Already scheduled", existingScheduled.length],
    ["Net-new email ready", null],
    ["Total defensible capacity", null],
    ["Remaining gap", null],
  ];
  sheet.getRange("B7").formulas = [["=COUNTA('Email Ready'!A6:A200)"]];
  sheet.getRange("B8").formulas = [["=B6+B7"]];
  sheet.getRange("B9").formulas = [["=MAX(0,B5-B8)"]];
  styleTable(sheet, "A4:B9", "A4:B4", "A5:B9", "#1D4ED8", "GeoCapacity", "TableStyleMedium2");
  sheet.getRange("B5:B9").format = {
    fill: "#EFF6FF",
    font: { bold: true, color: "#1D4ED8", size: 12 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
  sheet.getRange("D4:H4").values = [[
    "Date",
    "Target",
    "Already Scheduled",
    "Suggested New Allocation",
    "Unfilled Capacity",
  ]];
  sheet.getRange("D5:H9").values = [
    ["2026-08-03", 20, 0, 7, null],
    ["2026-08-04", 20, 17, 3, null],
    ["2026-08-05", 20, 0, 6, null],
    ["2026-08-06", 20, 0, 6, null],
    ["2026-08-07", 20, 0, 6, null],
  ];
  sheet.getRange("H5").formulas = [["=MAX(0,E5-F5-G5)"]];
  sheet.getRange("H5:H9").fillDown();
  styleTable(sheet, "D4:H9", "D4:H4", "D5:H9", "#1D4ED8", "GeoDailyPlan", "TableStyleMedium2");
  sheet.getRange("D12:H12").values = [[
    "Geography",
    "Preferred Local Window",
    "Equivalent IST in August",
    "Ready Count",
    "Note",
  ]];
  sheet.getRange("D13:H19").values = [
    ["London", "09:00-10:30 BST", "13:30-15:00 IST", null, "Morning inbox window"],
    ["New York", "09:00-10:30 EDT", "18:30-20:00 IST", null, "Morning inbox window"],
    ["San Francisco", "09:00-10:30 PDT", "21:30-23:00 IST", null, "Morning inbox window"],
    ["Chicago", "09:00-10:30 CDT", "19:30-21:00 IST", null, "No email-ready rows yet"],
    ["Dubai", "09:00-10:30 GST", "10:30-12:00 IST", null, "Morning inbox window"],
    ["Houston", "09:00-10:30 CDT", "19:30-21:00 IST", null, "No email-ready rows yet"],
    ["Dallas, Texas", "09:00-10:30 CDT", "19:30-21:00 IST", null, "Morning inbox window"],
  ];
  sheet.getRange("G13").formulas = [['=COUNTIF(\'Email Ready\'!B:B,D13)']];
  sheet.getRange("G13:G19").fillDown();
  styleTable(sheet, "D12:H19", "D12:H12", "D13:H19", "#1D4ED8", "GeoTiming", "TableStyleMedium2");
  sheet.getRange("A12:B16").values = [
    ["Decision", "Recommendation"],
    ["Can the seven-city batch reach 100?", "No, not without weakening the original quality gate."],
    ["What should count now?", "Only the 17 scheduled plus rows on Email Ready."],
    ["What closes the gap?", "Add more geographies/channels or verify public emails for the Needs Verification sheet."],
    ["What should not happen?", "Do not infer email patterns, count stale jobs, or re-contact existing recipients."],
  ];
  styleTable(sheet, "A12:B16", "A12:B12", "A13:B16", "#334155", "GeoDecision", "TableStyleMedium3");
  [26, 22, 3, 17, 14, 18, 20, 24].forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, 20, 1).format.columnWidth = width;
  });
  sheet.getRange("B:B").format.columnWidth = 62;
  sheet.getRange("H:H").format.columnWidth = 32;
  sheet.freezePanes.freezeRows(3);
}

function buildScheduled(workbook) {
  const sheet = workbook.worksheets.add("Existing Scheduled");
  const lastRow = existingScheduled.length + 4;
  titleBlock(
    sheet,
    "A1:D1",
    "Existing Gmail schedule used for deduplication",
    "Read-only snapshot of scheduled messages for August 3-7, checked on August 2. These 17 count toward the 100 total and are not repeated in Email Ready.",
    "#475569",
    "#E2E8F0",
  );
  sheet.getRange("A4:D4").values = [["Company", "Recipient", "Scheduled Date", "Status"]];
  sheet.getRange(`A5:D${lastRow}`).values = existingScheduled;
  styleTable(
    sheet,
    `A4:D${lastRow}`,
    "A4:D4",
    `A5:D${lastRow}`,
    "#475569",
    "GeoExistingScheduled",
    "TableStyleMedium3",
  );
  sheet.getRange(`A5:A${lastRow}`).format.font = { bold: true, color: "#0F172A", size: 10 };
  [28, 36, 20, 28].forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, lastRow, 1).format.columnWidth = width;
  });
  sheet.freezePanes.freezeRows(4);
}

function buildAudit(workbook) {
  const sheet = workbook.worksheets.add("Source Audit");
  const sources = [
    ["Work at YC", "London", 24, "Strict 1-10 + Engineering filters; company base rechecked", 6, 7, "https://www.workatastartup.com/companies"],
    ["Work at YC", "New York", 106, "Strict 1-10 + Engineering filters; company base rechecked", 11, 10, "https://www.workatastartup.com/companies"],
    ["Work at YC", "San Francisco", 339, "Strict 1-10 + Engineering filters; company base rechecked", 8, 17, "https://www.workatastartup.com/companies"],
    ["Work at YC", "Chicago", 2, "Strict 1-10 + Engineering filters", 0, 1, "https://www.workatastartup.com/companies"],
    ["Work at YC", "Dubai", 0, "No matching startup cards", 0, 0, "https://www.workatastartup.com/companies"],
    ["Work at YC", "Houston", 2, "No usable current company card in result set", 0, 0, "https://www.workatastartup.com/companies"],
    ["Work at YC", "Dallas, Texas", 1, "No usable current company card in result set", 0, 0, "https://www.workatastartup.com/companies"],
    ["Wellfound + official sites", "Chicago", null, "Current 1-10 engineering listings and founder/company evidence", 0, 1, "https://wellfound.com/location/chicago"],
    ["Wellfound + official sites", "Dubai", 181, "Current 1-10 engineering listings and founder/company evidence", 2, 0, "https://wellfound.com/location/dubai"],
    ["Wellfound + official sites", "Houston", null, "Current 1-10 engineering listings and founder/company evidence", 0, 1, "https://wellfound.com/location/houston"],
    ["Wellfound + official sites", "Dallas, Texas", null, "Current 1-10 engineering listings and founder/company evidence", 1, 4, "https://wellfound.com/location/dallas"],
  ];
  const lastRow = sources.length + 4;
  titleBlock(
    sheet,
    "A1:G1",
    "Discovery and verification audit",
    "Discovery counts are top-of-funnel search results, not qualified leads. Channel-specific yields reconcile to the Email Ready and Needs Verification sheets.",
    "#7C3AED",
    "#EDE9FE",
  );
  sheet.getRange("A4:G4").values = [[
    "Channel",
    "Geography",
    "Discovery Count",
    "Scope / Gate",
    "Email Ready",
    "Needs Verification",
    "Source",
  ]];
  sheet.getRange(`A5:G${lastRow}`).values = sources;
  styleTable(
    sheet,
    `A4:G${lastRow}`,
    "A4:G4",
    `A5:G${lastRow}`,
    "#7C3AED",
    "GeoSourceAudit",
    "TableStyleMedium5",
  );
  sheet.getRange(`E5:F${lastRow}`).format = {
    fill: "#F5F3FF",
    font: { bold: true, color: "#6D28D9", size: 11 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
  [30, 20, 18, 56, 16, 20, 48].forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, lastRow, 1).format.columnWidth = width;
  });
  sheet.freezePanes.freezeRows(4);
}

await fs.mkdir(outputDir, { recursive: true });
const workbook = Workbook.create();
workbook.comments.setSelf({ displayName: "Alankrit" });
buildReady(workbook);
buildNeeds(workbook);
buildExcluded(workbook);
buildCapacity(workbook);
buildScheduled(workbook);
buildAudit(workbook);

console.log(JSON.stringify({ ready: ready.length, needs: needs.length, excluded: excluded.length }, null, 2));

for (const [name, range] of [
  ["Email Ready", `A1:V${Math.min(ready.length + 5, 40)}`],
  ["Needs Verification", `A1:J${Math.min(needs.length + 4, 40)}`],
  ["Excluded & Duplicates", `A1:E${Math.min(excluded.length + 4, 40)}`],
  ["Capacity Plan", "A1:H19"],
  ["Existing Scheduled", "A1:D21"],
  ["Source Audit", "A1:G15"],
]) {
  const check = await workbook.inspect({
    kind: "table",
    range: `'${name}'!${range}`,
    include: "values,formulas",
    tableMaxRows: 42,
    tableMaxCols: 24,
    maxChars: 18000,
  });
  console.log(`${name.toUpperCase().replaceAll(" ", "_")}_CHECK`);
  console.log(check.ndjson);
}

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
console.log("ERROR_SCAN");
console.log(errors.ndjson);

for (const [sheetName, range, fileStem] of [
  ["Email Ready", `A1:V${ready.length + 5}`, "geo_email_ready_preview.png"],
  ["Needs Verification", `A1:J${needs.length + 4}`, "geo_needs_preview.png"],
  ["Excluded & Duplicates", `A1:E${excluded.length + 4}`, "geo_excluded_preview.png"],
  ["Capacity Plan", "A1:H19", "geo_capacity_preview.png"],
  ["Existing Scheduled", "A1:D21", "geo_scheduled_preview.png"],
  ["Source Audit", "A1:G15", "geo_source_audit_preview.png"],
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  const bytes = new Uint8Array(await preview.arrayBuffer());
  await fs.writeFile(`${outputDir}/${fileStem}`, bytes);
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(`OUTPUT ${outputPath}`);
