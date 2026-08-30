import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir =
  "/Users/alankritghosh/JARVIS /jarvis_engineering/outputs/019fb63b-5805-7fe2-a1a6-090b7a6f0688";
const outputPath = `${outputDir}/Icarus_VC_Accelerator_Batch.xlsx`;
const checkedDate = new Date("2026-07-31T00:00:00Z");
const snapshotYear = 2026;

const qualified = [
  {
    company: "Abacus",
    channel: "Pear VC portfolio",
    discovery: "https://jobs.ashbyhq.com/pear-vc/d8b852b5-f083-4210-8b9b-69a08b9e0236",
    team: "Team of 2 stated in role; LinkedIn 2-10",
    founded: 2024,
    ageEvidence: "New York incorporation record dated 2024-12-11.",
    stage: "Early-stage; hiring first founding engineer",
    location: "New York, NY",
    role: "Founding Engineer",
    poc: "Brandon Sugarman",
    title: "Co-founder & CTO",
    route: "brandon@getabacus.com",
    pocLinkedIn: "https://www.linkedin.com/posts/brandon-sugarman_big-news-abacus-is-officially-out-of-activity-7349120766006710273-UvOZ",
    companyLinkedIn: "https://www.linkedin.com/company/abacusintelligence",
    context:
      "Abacus uses AI agents, OCR and LLMs to automate document extraction and back-office workflows for accounting firms. Its two founders are hiring their first engineer.",
    useCase:
      "Preserve why extraction schemas, accuracy thresholds, evals, fallback paths and human-review rules changed. Icarus can return cited evidence for audit-sensitive accounting workflow decisions.",
    confidence: "High",
    status: "Published founder email",
    fit: 5,
    sources:
      "https://jobs.ashbyhq.com/pear-vc/d8b852b5-f083-4210-8b9b-69a08b9e0236 | https://www.linkedin.com/company/abacusintelligence | https://www.linkedin.com/posts/brandon-sugarman_big-news-abacus-is-officially-out-of-activity-7349120766006710273-UvOZ | https://www.bizprofile.net/ny/new-york/abacus-intelligence-inc-2",
  },
  {
    company: "Phaselaw",
    channel: "Pear VC portfolio",
    discovery: "https://jobs.ashbyhq.com/pear-vc/361caae7-d798-4603-b428-4ca959d0eab8",
    team: "6 visible; LinkedIn 2-10",
    founded: 2023,
    ageEvidence: "Official job and LinkedIn both list 2023.",
    stage: "Early-stage legal technology",
    location: "New York, NY / Remote",
    role: "Founding Product Engineer",
    poc: "Josh Schwartz",
    title: "Co-founder & CEO",
    route: "hello@phase.law",
    pocLinkedIn: "https://www.linkedin.com/in/schwartz-josh",
    companyLinkedIn: "https://www.linkedin.com/company/phaselaw",
    context:
      "Phaselaw builds AI-assisted review and redaction for eDiscovery, DSAR/FOI, investigations and litigation. Its six-person public team is hiring a founding product engineer.",
    useCase:
      "Preserve the rationale behind redaction rules, document pipelines, model-versus-human review, privacy controls and audit behavior. Icarus fits the product's regulatory and customer-trust burden.",
    confidence: "High",
    status: "Published company email",
    fit: 5,
    sources:
      "https://jobs.ashbyhq.com/pear-vc/361caae7-d798-4603-b428-4ca959d0eab8 | https://www.linkedin.com/company/phaselaw | https://www.linkedin.com/in/schwartz-josh",
  },
  {
    company: "Pom Health",
    channel: "Pear VC portfolio",
    discovery: "https://jobs.ashbyhq.com/pear-vc/2de75bf0-c300-483e-b868-f2d8fb920912",
    team: "Team of 5 stated in role",
    founded: 2024,
    ageEvidence: "Healthie customer story states Pom launched in 2024.",
    stage: "Early-stage; hundreds of active patients",
    location: "New York, NY",
    role: "Founding Engineer",
    poc: "Misha Nasrollahzadeh",
    title: "Co-founder & CEO",
    route: "Founder LinkedIn or official Pear/Ashby application; no public email verified",
    pocLinkedIn: "https://www.linkedin.com/posts/mishanasrollahzadeh_i-wasnt-planning-to-post-twice-in-one-week-activity-7404976553677332480-enYS",
    companyLinkedIn: "https://www.linkedin.com/company/pom-health",
    context:
      "Pom is a five-person healthcare team building AI-assisted nutrition support inside clinician and EHR workflows. It is hiring its second engineer while serving hundreds of patients.",
    useCase:
      "Preserve why HIPAA/PHI controls, EHR integrations, patient messaging, model-versus-deterministic logic and audit trails evolved. Icarus can ground sensitive healthcare decisions in repository evidence.",
    confidence: "Medium",
    status: "Verified LinkedIn route",
    fit: 5,
    sources:
      "https://jobs.ashbyhq.com/pear-vc/2de75bf0-c300-483e-b868-f2d8fb920912 | https://www.gethealthie.com/success-stories/pom-health | https://wellfound.com/company/pom-health/people | https://www.linkedin.com/posts/mishanasrollahzadeh_i-wasnt-planning-to-post-twice-in-one-week-activity-7404976553677332480-enYS",
  },
  {
    company: "Kato",
    channel: "Pear VC portfolio",
    discovery: "https://jobs.ashbyhq.com/Pear-VC/214dc247-0778-485b-8a3d-067990aca47c",
    team: "3 visible; LinkedIn 2-10",
    founded: 2024,
    ageEvidence: "Founder post says the company incorporated roughly September 2024.",
    stage: "Early-stage; regulated-finance customers",
    location: "San Francisco, CA",
    role: "Senior Product Engineer; hiring second engineer",
    poc: "Pratik Risbud",
    title: "Co-founder & CEO",
    route: "Founder LinkedIn or official Pear/Ashby application; no public email verified",
    pocLinkedIn: "https://www.linkedin.com/in/pratikrisbud",
    companyLinkedIn: "https://www.linkedin.com/company/katohq",
    context:
      "Kato builds compliance-first voice agents for regulated loan servicing and collections. Its tiny team already serves major fintech customers and is hiring its second engineer.",
    useCase:
      "Preserve why disclosures, scripts, guardrails, multilingual logic, escalation, authorization and audit logging changed. Icarus can make regulatory product history directly recoverable.",
    confidence: "Medium",
    status: "Verified LinkedIn route",
    fit: 5,
    sources:
      "https://jobs.ashbyhq.com/Pear-VC/214dc247-0778-485b-8a3d-067990aca47c | https://www.linkedin.com/company/katohq | https://www.linkedin.com/in/pratikrisbud | https://www.linkedin.com/posts/pratikrisbud_hard-to-believe-its-been-a-year-since-activity-7377420450374754304-n958",
  },
  {
    company: "Keenable",
    channel: "Conviction",
    discovery: "https://keenable.ai/careers/",
    team: "3 public Hugging Face team members",
    founded: 2026,
    ageEvidence: "First verified public launch and Conviction cohort signal are from 2026; incorporation date is not published.",
    stage: "Conviction MoE v6; newly launched",
    location: "San Francisco Bay Area",
    role: "Member of Technical Staff, Engineering",
    poc: "Andrey Styskin",
    title: "Co-founder",
    route: "Official careers/contact route or founder LinkedIn; no public email verified",
    pocLinkedIn: "https://www.linkedin.com/in/andrey-styskin-3025113",
    companyLinkedIn: "Not independently verified",
    context:
      "Keenable is a three-person AI infrastructure team building low-latency search, indexing and retrieval primitives for agents. It is currently hiring engineering MTS roles.",
    useCase:
      "Preserve why indexing, ranking, freshness, fetch, latency, MCP/auth and reliability tradeoffs changed as customers and integrations grow. Icarus can reconnect each decision to its GitHub evidence.",
    confidence: "Medium",
    status: "Verified careers route",
    fit: 5,
    sources:
      "https://keenable.ai/ | https://keenable.ai/careers/ | https://www.conviction.com/moe | https://huggingface.co/keenable-ai | https://www.linkedin.com/in/andrey-styskin-3025113",
  },
  {
    company: "Pascal",
    channel: "Conviction",
    discovery: "https://jobs.ashbyhq.com/teampascal/92273e24-9e9e-4d1a-a808-eb35cf5f0645",
    team: "Wellfound 1-10; role says one of first employees",
    founded: 2026,
    ageEvidence: "Earliest verified founder work-history and public company signals begin in January 2026.",
    stage: "Conviction MoE v6; founding team",
    location: "San Francisco, CA",
    role: "Founding Engineer",
    poc: "Rick Huang",
    title: "Co-founder",
    route: "Official Ashby application or Conviction profile; no public email or independently matched LinkedIn verified",
    pocLinkedIn: "Not independently matched",
    companyLinkedIn: "Not independently verified",
    context:
      "Pascal is a tiny founding team building AI-native finance, sales and operations systems for consumer brands. It is hiring its first employees around agent and data infrastructure.",
    useCase:
      "Preserve why tenant models, terabyte-scale extraction, access policies, agent memory/retrieval and customer-specific deployments evolved. Icarus can keep those founding decisions from becoming oral history.",
    confidence: "Medium",
    status: "Verified application route",
    fit: 5,
    sources:
      "https://jobs.ashbyhq.com/teampascal/92273e24-9e9e-4d1a-a808-eb35cf5f0645 | https://wellfound.com/jobs/4288760-founding-engineer | https://www.conviction.com/moe | https://www.glean.com/authors/rick-huang",
  },
];

const needsVerification = [
  [
    "Baton AI",
    "Pear VC portfolio",
    "https://jobs.ashbyhq.com/pear-vc/fe28c1f0-c166-4bef-8962-759d0cbf636a",
    "Current product engineering role; LinkedIn 2-10",
    "Mikil Foss",
    "Founder title and operating start are not independently verified.",
    "Confirm founder role and founding year before outreach.",
    "https://www.linkedin.com/company/baton-ai | https://www.linkedin.com/in/mikil-foss",
  ],
  [
    "Manhattan Labs",
    "Pear VC portfolio",
    "https://jobs.ashbyhq.com/pear-vc/f48cecb3-841e-4e38-87db-0ad1115a7a46",
    "Ashby shows a founding AI engineer role",
    "Not yet verified",
    "LinkedIn copy says the role is closed; team and POC could not be reliably matched.",
    "Confirm the role is live and identify the founder plus current headcount.",
    "https://www.linkedin.com/jobs/view/founding-ai-engineer-at-manhattan-labs-4410235252",
  ],
  [
    "Intent Lab",
    "Conviction",
    "https://jobs.ashbyhq.com/intentlab/d5bc6d47-bd37-44c5-922a-de7de3334399/",
    "Multiple current technical roles",
    "Yangqing Jia / Xiang Li / Junjie Bai / Casber Wang",
    "Four founders are named, but exact current headcount is not public.",
    "Verify current team is still 1-10 before selecting the best POC.",
    "https://www.conviction.com/moe | https://jobs.ashbyhq.com/intentlab/d80ff994-d28f-4a71-ba44-edf89801e418",
  ],
  [
    "Ephemeral Intel",
    "HF0",
    "https://www.hf0.com/",
    "Recent HF0 investment/public signal",
    "Not yet verified",
    "No source-backed current role, exact headcount and founder route were verified together.",
    "Find an official current engineering opening before adding.",
    "https://www.hf0.com/",
  ],
];

const held = [
  ["Atrix AI", "Pear VC portfolio", "LinkedIn currently lists 11-50.", "Hold for 11-50 batch"],
  ["FlowGen Labs", "Pear VC portfolio", "LinkedIn currently lists 11-50.", "Hold for 11-50 batch"],
  ["Zango", "South Park Commons", "LinkedIn currently lists 11-50.", "Hold for 11-50 batch"],
  ["Alien", "HF0", "Live engineering signal, but LinkedIn currently lists 11-50.", "Hold for 11-50 batch"],
  ["Hamilton AI", "HF0", "Multiple live roles, but LinkedIn currently lists 11-50.", "Hold for 11-50 batch"],
  ["Town", "Conviction", "Public team is roughly 25 people.", "Hold for 11-50 batch"],
  ["Limelight", "Soma Capital", "Soma labels it 1-10, but LinkedIn currently lists 11-50.", "Hold for 11-50 batch"],
  ["RunSybil", "Conviction", "LinkedIn currently lists 11-50.", "Hold for 11-50 batch"],
  ["Sola", "Conviction", "LinkedIn currently lists 11-50.", "Hold for 11-50 batch"],
  ["Onyx AI", "Conviction", "LinkedIn currently lists 11-50.", "Hold for 11-50 batch"],
  ["Sunday", "Conviction", "LinkedIn currently lists 51-200.", "Exclude from founder-stage campaign"],
  ["Corridor", "Conviction", "LinkedIn currently lists 11-50.", "Hold for 11-50 batch"],
];

const channels = [
  [
    "Pear VC portfolio",
    "https://jobs.ashbyhq.com/pear-vc",
    "88 current positions audited; founding/product engineering roles cross-checked against headcount.",
    null,
    null,
    "6 earlier qualified Pear companies omitted as duplicates.",
    "Best current yield. Re-run weekly and verify visible team count.",
  ],
  [
    "South Park Commons",
    "https://www.southparkcommons.com/jobs",
    "Indexed company and role pages audited.",
    null,
    null,
    "Breezy and Corveris already qualified; Noto, Foam and Andy AI already held.",
    "No new strict 1-10 additions in this pass.",
  ],
  [
    "Neo",
    "https://neo.com/",
    "Public portfolio and current residency signal audited; recruiting access is member-gated.",
    null,
    null,
    "No new company had public role, headcount and founder evidence together.",
    "Use only with member access or a second official careers source.",
  ],
  [
    "HF0",
    "https://www.hf0.com/",
    "Current cohort/investment signals cross-checked with public hiring evidence.",
    null,
    null,
    "Alien and Hamilton AI exceed 10; Ephemeral Intel needs verification.",
    "Recheck cohort companies monthly; require a live company role.",
  ],
  [
    "Conviction",
    "https://www.conviction.com/moe",
    "Current Mixture of Experts cohort and official role pages audited.",
    null,
    null,
    "Several strong companies exceed 10 people; Intent Lab needs a headcount check.",
    "Good technical fit. Re-run on every new MoE cohort.",
  ],
  [
    "Contrary",
    "https://jobs.contrary.com/jobs",
    "823 current jobs audited; no Founding Engineer result and visible engineer roles skewed larger.",
    null,
    null,
    "No strict 1-10 company met the complete evidence bar.",
    "Low priority until a small-team filter or new early-stage cohort appears.",
  ],
  [
    "Soma Capital",
    "https://jobs.somacap.com/jobs",
    "1,543-job board audited with 1-10 and founding-engineer filters.",
    null,
    null,
    "Board size metadata drifted; Limelight is now 11-50 on LinkedIn.",
    "Treat Getro headcount as discovery only; independently verify every team.",
  ],
];

const prospectColumns = [
  "Company",
  "Channel",
  "Discovery URL",
  "Checked Date",
  "Public Team Size",
  "Founded Year",
  "Age (Calendar Years)",
  "Age Evidence / Caveat",
  "Stage / Signal",
  "Location",
  "Live Engineering Hiring Signal",
  "POC",
  "POC Title",
  "Published Email / Contact Route",
  "POC LinkedIn",
  "Company LinkedIn",
  "Company Context",
  "Ideal Icarus Use Case",
  "Contact Confidence",
  "Outreach Status",
  "Icarus Fit (1-5)",
  "Priority",
  "Verification Sources",
];

function prospectMatrix() {
  return qualified.map((row) => [
    row.company,
    row.channel,
    row.discovery,
    checkedDate,
    row.team,
    row.founded,
    null,
    row.ageEvidence,
    row.stage,
    row.location,
    row.role,
    row.poc,
    row.title,
    row.route,
    row.pocLinkedIn,
    row.companyLinkedIn,
    row.context,
    row.useCase,
    row.confidence,
    row.status,
    row.fit,
    null,
    row.sources,
  ]);
}

function titleBlock(sheet, range, title, subtitle, color, pale) {
  sheet.showGridLines = false;
  sheet.getRange(range.replace(/1$/, "1")).merge();
  const firstCell = range.split(":")[0];
  sheet.getRange(firstCell).values = [[title]];
  sheet.getRange(range.replace(/1$/, "1")).format = {
    fill: color,
    font: { bold: true, color: "#FFFFFF", size: 17 },
    verticalAlignment: "center",
  };
  sheet.getRange(range.replace(/1$/, "1")).format.rowHeight = 34;
  const row2 = range.replaceAll("1", "2");
  sheet.getRange(row2).merge();
  sheet.getRange(row2.split(":")[0]).values = [[subtitle]];
  sheet.getRange(row2).format = {
    fill: pale,
    font: { color, italic: true, size: 10 },
    verticalAlignment: "center",
    wrapText: true,
  };
  sheet.getRange(row2).format.rowHeight = 32;
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
  sheet.getRange(headerRange).format.rowHeight = 42;
  sheet.getRange(bodyRange).format.rowHeight = 78;
  const table = sheet.tables.add(range, true, tableName);
  table.style = style;
  table.showFilterButton = true;
  sheet.getRange(headerRange).format.fill = headerColor;
}

function buildQualified(workbook) {
  const sheet = workbook.worksheets.add("Qualified Prospects");
  const lastRow = qualified.length + 5;
  titleBlock(
    sheet,
    "A1:W1",
    "Icarus VC & Accelerator Prospect Batch",
    "Strictly additive to the prior workbook: current engineering signal, 1-10 people, named founder POC, company age and source-backed Icarus use case. No guessed email addresses.",
    "#0F766E",
    "#CCFBF1",
  );
  sheet.getRange("A3").values = [["New qualified"]];
  sheet.getRange("B3").formulas = [[`=COUNTA(A6:A${lastRow})`]];
  sheet.getRange("D3").values = [["Published emails"]];
  sheet.getRange("E3").formulas = [[
    `=COUNTIF(T6:T${lastRow},"Published founder email")+COUNTIF(T6:T${lastRow},"Published company email")`,
  ]];
  sheet.getRange("G3").values = [["P1 fits"]];
  sheet.getRange("H3").formulas = [[`=COUNTIF(V6:V${lastRow},"P1")`]];
  sheet.getRange("J3").values = [["Prior qualified"]];
  sheet.getRange("K3").values = [[12]];
  sheet.getRange("M3").values = [["Total pipeline"]];
  sheet.getRange("N3").formulas = [["=B3+K3"]];
  sheet.getRange("A3:N3").format = {
    fill: "#F8FAFC",
    font: { color: "#334155", size: 10 },
    verticalAlignment: "center",
    borders: { preset: "outside", style: "thin", color: "#CBD5E1" },
  };
  for (const cell of ["A3", "D3", "G3", "J3", "M3"]) {
    sheet.getRange(cell).format.font = { bold: true, color: "#0F766E", size: 10 };
  }
  for (const cell of ["B3", "E3", "H3", "K3", "N3"]) {
    sheet.getRange(cell).format.font = { bold: true, color: "#0F172A", size: 11 };
  }
  sheet.getRange("A5:W5").values = [prospectColumns];
  sheet.getRange(`A6:W${lastRow}`).values = prospectMatrix();
  sheet.getRange("G6").formulas = [['=IF(F6="","",$Y$3-F6)']];
  sheet.getRange(`G6:G${lastRow}`).fillDown();
  sheet.getRange("V6").formulas = [['=IF(U6>=5,CHAR(80)&"1",IF(U6>=4,CHAR(80)&"2",CHAR(80)&"3"))']];
  sheet.getRange(`V6:V${lastRow}`).fillDown();
  sheet.getRange("Y3").values = [[snapshotYear]];
  sheet.getRange("Y3").format.font = { color: "#FFFFFF", size: 1 };
  sheet.getRange(`D6:D${lastRow}`).setNumberFormat("yyyy-mm-dd");
  sheet.getRange(`F6:G${lastRow}`).setNumberFormat("0");
  styleTable(
    sheet,
    `A5:W${lastRow}`,
    "A5:W5",
    `A6:W${lastRow}`,
    "#0F766E",
    "VCQualified",
    "TableStyleMedium4",
  );
  sheet.getRange(`A6:A${lastRow}`).format.font = { bold: true, color: "#0F172A", size: 10 };
  sheet.getRange(`G6:G${lastRow}`).format.fill = "#ECFDF5";
  sheet.getRange(`S6:S${lastRow}`).conditionalFormats.add("containsText", {
    text: "High",
    format: { fill: "#DCFCE7", font: { color: "#166534", bold: true } },
  });
  sheet.getRange(`S6:S${lastRow}`).conditionalFormats.add("containsText", {
    text: "Medium",
    format: { fill: "#FEF3C7", font: { color: "#92400E", bold: true } },
  });
  sheet.getRange(`V6:V${lastRow}`).conditionalFormats.add("containsText", {
    text: "P1",
    format: { fill: "#CCFBF1", font: { color: "#115E59", bold: true } },
  });
  const widths = [
    18, 22, 35, 12, 27, 12, 12, 36, 28, 24, 34, 22, 22, 43, 35, 32, 50, 54, 16,
    26, 13, 10, 52,
  ];
  widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, lastRow, 1).format.columnWidth = width;
  });
  sheet.getRange("Y:Y").format.columnWidth = 2;
  sheet.freezePanes.freezeRows(5);
  sheet.freezePanes.freezeColumns(2);
}

function buildNeedsVerification(workbook) {
  const sheet = workbook.worksheets.add("Needs Verification");
  const lastRow = needsVerification.length + 4;
  titleBlock(
    sheet,
    "A1:H1",
    "Promising companies that are not yet outreach-ready",
    "These rows are intentionally outside the qualified count. Each is missing one load-bearing fact, so no email should be drafted or sent until the next action is complete.",
    "#B45309",
    "#FEF3C7",
  );
  sheet.getRange("A4:H4").values = [[
    "Company",
    "Channel",
    "Discovery URL",
    "Current Signal",
    "Candidate POC",
    "Verification Gap",
    "Next Action",
    "Sources",
  ]];
  sheet.getRange(`A5:H${lastRow}`).values = needsVerification;
  styleTable(
    sheet,
    `A4:H${lastRow}`,
    "A4:H4",
    `A5:H${lastRow}`,
    "#B45309",
    "VCNeedsVerification",
    "TableStyleMedium7",
  );
  sheet.getRange(`A5:A${lastRow}`).format.font = { bold: true, color: "#0F172A", size: 10 };
  [20, 22, 38, 34, 25, 52, 42, 54].forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, lastRow, 1).format.columnWidth = width;
  });
  sheet.freezePanes.freezeRows(4);
}

function buildHeld(workbook) {
  const sheet = workbook.worksheets.add("Held Outside 1-10");
  const lastRow = held.length + 4;
  titleBlock(
    sheet,
    "A1:D1",
    "Companies intentionally excluded by the current size rule",
    "These companies may be good Icarus prospects later, but adding them now would violate the strict 1-10-person campaign. The list also prevents repeated research.",
    "#9A3412",
    "#FFEDD5",
  );
  sheet.getRange("A4:D4").values = [["Company", "Channel", "Why Excluded", "Next Action"]];
  sheet.getRange(`A5:D${lastRow}`).values = held;
  styleTable(
    sheet,
    `A4:D${lastRow}`,
    "A4:D4",
    `A5:D${lastRow}`,
    "#9A3412",
    "VCHeld",
    "TableStyleMedium9",
  );
  sheet.getRange(`A5:A${lastRow}`).format.font = { bold: true, color: "#0F172A", size: 10 };
  [22, 24, 64, 30].forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, lastRow, 1).format.columnWidth = width;
  });
  sheet.freezePanes.freezeRows(4);
}

function buildAudit(workbook) {
  const sheet = workbook.worksheets.add("Channel Audit");
  const lastRow = channels.length + 4;
  titleBlock(
    sheet,
    "A1:G1",
    "Seven-channel sourcing audit",
    "Yield is formula-linked to the qualified and verification sheets. Zero is a valid result: weak or oversized companies are not promoted merely to increase volume.",
    "#1D4ED8",
    "#DBEAFE",
  );
  sheet.getRange("A4:G4").values = [[
    "Channel",
    "URL",
    "Scope Assessed",
    "Qualified Yield",
    "Needs Verification",
    "Duplicates / Exclusions",
    "Next Recommendation",
  ]];
  sheet.getRange(`A5:G${lastRow}`).values = channels;
  sheet.getRange("D5").formulas = [['=COUNTIF(\'Qualified Prospects\'!B:B,A5)']];
  sheet.getRange(`D5:D${lastRow}`).fillDown();
  sheet.getRange("E5").formulas = [['=COUNTIF(\'Needs Verification\'!B:B,A5)']];
  sheet.getRange(`E5:E${lastRow}`).fillDown();
  styleTable(
    sheet,
    `A4:G${lastRow}`,
    "A4:G4",
    `A5:G${lastRow}`,
    "#1D4ED8",
    "VCChannelAudit",
    "TableStyleMedium2",
  );
  sheet.getRange(`A5:A${lastRow}`).format.font = { bold: true, color: "#0F172A", size: 10 };
  sheet.getRange(`D5:E${lastRow}`).format = {
    fill: "#EFF6FF",
    font: { bold: true, color: "#1D4ED8", size: 11 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
  [24, 36, 54, 16, 18, 58, 46].forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, lastRow, 1).format.columnWidth = width;
  });
  sheet.freezePanes.freezeRows(4);
}

await fs.mkdir(outputDir, { recursive: true });
const workbook = Workbook.create();
workbook.comments.setSelf({ displayName: "Alankrit" });
buildQualified(workbook);
buildNeedsVerification(workbook);
buildHeld(workbook);
buildAudit(workbook);

for (const [name, range] of [
  ["Qualified Prospects", "A1:W11"],
  ["Needs Verification", "A1:H8"],
  ["Held Outside 1-10", "A1:D16"],
  ["Channel Audit", "A1:G11"],
]) {
  const check = await workbook.inspect({
    kind: "table",
    range: `'${name}'!${range}`,
    include: "values,formulas",
    tableMaxRows: 20,
    tableMaxCols: 24,
    maxChars: 16000,
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
  ["Qualified Prospects", "A1:W11", "vc_qualified_preview.png"],
  ["Needs Verification", "A1:H8", "vc_needs_verification_preview.png"],
  ["Held Outside 1-10", "A1:D16", "vc_held_preview.png"],
  ["Channel Audit", "A1:G11", "vc_channel_audit_preview.png"],
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  const bytes = new Uint8Array(await preview.arrayBuffer());
  await fs.writeFile(`${outputDir}/${fileStem}`, bytes);
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(`OUTPUT ${outputPath}`);
