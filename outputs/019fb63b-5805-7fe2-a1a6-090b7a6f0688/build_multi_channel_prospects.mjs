import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir =
  "/Users/alankritghosh/JARVIS /jarvis_engineering/outputs/019fb63b-5805-7fe2-a1a6-090b7a6f0688";
const outputPath = `${outputDir}/Icarus_Multi_Channel_Prospects.xlsx`;
const checkedDate = new Date("2026-07-31T00:00:00Z");
const snapshotYear = 2026;

const prospects = [
  {
    company: "Breezy",
    channel: "South Park Commons",
    discovery: "https://www.southparkcommons.com/companies/breezy",
    team: "4 visible; LinkedIn 2-10",
    founded: 2023,
    ageEvidence: "SPC and LinkedIn both list 2023; LinkedIn currently shows four employees.",
    stage: "SPC-backed; early-stage",
    location: "San Francisco, CA",
    role: "Founding Engineer",
    poc: "Saul Fuhrmann",
    title: "Co-founder / technical founder",
    route: "Founder LinkedIn or apply through the SPC-listed role; no public founder email verified",
    pocLinkedIn: "https://www.linkedin.com/in/saul-fuhrmann-775a0b159",
    companyLinkedIn: "https://www.linkedin.com/company/breezy-app",
    context:
      "Breezy is a 24/7 AI front office for service businesses, handling calls, chat, booking, follow-up, CRM workflows and admin. Its four-person public team is hiring a founding engineer.",
    useCase:
      "Preserve why telephony, CRM and workflow integrations behave the way they do as customer-specific edge cases accumulate. Icarus can surface the GitHub evidence behind routing, retries and automation policies.",
    confidence: "Medium",
    status: "Needs direct email research",
    fit: 4,
    sources:
      "https://www.southparkcommons.com/companies/breezy | https://www.linkedin.com/company/breezy-app | https://www.linkedin.com/in/saul-fuhrmann-775a0b159",
  },
  {
    company: "Corveris",
    channel: "South Park Commons",
    discovery: "https://www.southparkcommons.com/companies/casex/",
    team: "4 visible; LinkedIn 2-10",
    founded: 2024,
    ageEvidence:
      "SPC dates the original CaseX company to 2024; LinkedIn dates the Corveris name to 2025. Age uses the earlier operating start.",
    stage: "Pre-seed; public-safety deployments",
    location: "San Francisco, CA",
    role: "Founding Engineer",
    poc: "Daniel Tatenko",
    title: "Founder",
    route: "Founder LinkedIn or apply through the SPC-listed role; no public founder email verified",
    pocLinkedIn: "https://www.linkedin.com/in/danieltatenko",
    companyLinkedIn: "https://www.linkedin.com/company/corveris",
    context:
      "Corveris builds public-safety infrastructure that interviews citizens, classifies offenses and sends structured reports into agency record systems. The visible team has four people and is hiring a founding engineer.",
    useCase:
      "Create an auditable memory of why classification, multilingual interview, NIBRS and agency-integration decisions were made. Cited GitHub history matters when reliability and policy choices are revisited.",
    confidence: "Medium",
    status: "Needs direct email research",
    fit: 4,
    sources:
      "https://www.southparkcommons.com/companies/casex/ | https://www.linkedin.com/company/corveris | https://www.linkedin.com/in/danieltatenko",
  },
  {
    company: "Modo",
    channel: "Pear VC portfolio",
    discovery: "https://jobs.ashbyhq.com/Pear-VC/dc1969ab-e197-4949-9bb8-a765af2b02c7",
    team: "3 visible; LinkedIn 2-10",
    founded: 2025,
    ageEvidence:
      "StartX F25 is the earliest verified public cohort; exact incorporation date is not published.",
    stage: "Seed; 7-figure committed ARR reported",
    location: "San Francisco Bay Area",
    role: "Founding Engineer",
    poc: "Johnny Chang",
    title: "Co-founder",
    route: "johnny@joinmodo.com",
    pocLinkedIn: "https://www.linkedin.com/in/johnnychang4",
    companyLinkedIn: "https://www.linkedin.com/company/joinmodo",
    context:
      "Modo measures enterprise AI adoption and ROI inside real workflows, then guides teams in the moment. Its two founders are adding a founding engineer across Next.js, Postgres and Electron/Tauri.",
    useCase:
      "Capture why customer feedback changed workflow instrumentation, desktop choices and data models. Icarus can keep those decisions retrievable as pilots turn into a multi-surface enterprise product.",
    confidence: "High",
    status: "Published email",
    fit: 4,
    sources:
      "https://jobs.ashbyhq.com/Pear-VC/dc1969ab-e197-4949-9bb8-a765af2b02c7 | https://www.linkedin.com/company/joinmodo | https://www.linkedin.com/in/johnnychang4",
  },
  {
    company: "Polynomic",
    channel: "Pear VC portfolio",
    discovery: "https://jobs.ashbyhq.com/pear-vc/2751e98a-eadf-43ec-bbaf-bdb478f7102d",
    team: "2 visible; LinkedIn 2-10",
    founded: 2025,
    ageEvidence: "LinkedIn explicitly lists Founded 2025.",
    stage: "Seed; paying consumer-brand customers",
    location: "New York, NY",
    role: "Founding Engineer",
    poc: "Madhav Datt",
    title: "Co-founder",
    route: "Apply through the Pear/Ashby role or contact the founder on LinkedIn",
    pocLinkedIn: "https://www.linkedin.com/in/madhavdatt",
    companyLinkedIn: "https://www.linkedin.com/company/polynomic",
    context:
      "Polynomic is building agentic performance-marketing systems that generate creatives, model attribution and optimize across ad platforms. The two-person public team is hiring a founding engineer.",
    useCase:
      "Record the why behind multi-agent orchestration, attribution logic, experiment design and ad-platform integrations. Icarus can connect later decisions to the PRs and customer evidence that caused them.",
    confidence: "Medium",
    status: "Needs direct email research",
    fit: 5,
    sources:
      "https://jobs.ashbyhq.com/pear-vc/2751e98a-eadf-43ec-bbaf-bdb478f7102d | https://www.linkedin.com/company/polynomic | https://www.linkedin.com/in/madhavdatt",
  },
  {
    company: "Kindroid",
    channel: "Pear VC portfolio",
    discovery: "https://jobs.ashbyhq.com/pear-vc/b89e0761-91be-4d0d-9142-1a53ad922a50",
    team: "5-person team stated in job post",
    founded: 2023,
    ageEvidence:
      "Kindroid's customer story and public product history date the company to 2023.",
    stage: "Profitable; $9M retentive ARR reported",
    location: "San Francisco Bay Area",
    role: "Founding Engineer",
    poc: "Jerry Meng",
    title: "Founder & CEO",
    route: "Apply through the Pear/Ashby role or contact the founder on LinkedIn",
    pocLinkedIn: "https://www.linkedin.com/in/jerrymeng100",
    companyLinkedIn: "https://www.linkedin.com/company/kindroid",
    context:
      "Kindroid makes configurable virtual companions with persistent memory, voice and visual identity. The profitable five-person team is adding a founding engineer across product, engineering and growth.",
    useCase:
      "Preserve model, memory, safety and infrastructure tradeoffs behind long-lived companion behavior. Icarus can help a new engineer retrieve the recorded reason for sensitive changes instead of relying on oral history.",
    confidence: "Medium",
    status: "Needs direct email research",
    fit: 4,
    sources:
      "https://jobs.ashbyhq.com/pear-vc/b89e0761-91be-4d0d-9142-1a53ad922a50 | https://www.linkedin.com/company/kindroid | https://kindroid.ai/docs/article/our-journey/ | https://www.linkedin.com/in/jerrymeng100",
  },
  {
    company: "Blueberry",
    channel: "Pear VC portfolio",
    discovery: "https://jobs.ashbyhq.com/Pear-VC/5b4bdd5f-9418-4d1e-aee7-3b5e0fbd29ea",
    team: "4 visible; LinkedIn 2-10",
    founded: 2025,
    ageEvidence:
      "Pear introduced the company as part of PearX S25; founders publicly described coming out of stealth in 2025.",
    stage: "Early-stage; 10+ brands in first months",
    location: "San Francisco Bay Area",
    role: "Founding Engineer",
    poc: "Sean Rich",
    title: "Co-founder",
    route: "Apply through the Pear/Ashby role or contact the founder on LinkedIn",
    pocLinkedIn: "https://www.linkedin.com/in/sean-rich36",
    companyLinkedIn: "https://www.linkedin.com/company/blue-berry-ai",
    context:
      "Blueberry builds AI marketing agents that research social audiences and send personalized brand conversations. Its small team ships weekly and is hiring its founding engineering team.",
    useCase:
      "Make the why behind social API integrations, audience research, agent policies and telemetry searchable. Icarus can keep rapid weekly product decisions grounded in the commits and discussions that produced them.",
    confidence: "Medium",
    status: "Needs direct email research",
    fit: 4,
    sources:
      "https://jobs.ashbyhq.com/Pear-VC/5b4bdd5f-9418-4d1e-aee7-3b5e0fbd29ea | https://www.linkedin.com/company/blue-berry-ai | https://www.linkedin.com/in/sean-rich36",
  },
  {
    company: "Shiplight AI",
    channel: "Pear VC portfolio",
    discovery: "https://jobs.ashbyhq.com/pear-vc/e681cf11-9b8a-4630-86ac-b995a76a77d7",
    team: "4 visible; LinkedIn 2-10",
    founded: 2025,
    ageEvidence: "LinkedIn explicitly lists Founded 2025.",
    stage: "Early-stage; production customers",
    location: "San Francisco Bay Area",
    role: "Founding AI Engineer",
    poc: "Will Zhao",
    title: "Co-founder & CEO",
    route: "info@shiplight.ai",
    pocLinkedIn: "https://www.linkedin.com/in/will-zhao-57372339",
    companyLinkedIn: "https://www.linkedin.com/company/shiplight",
    context:
      "Shiplight builds agentic end-to-end QA that creates and maintains browser tests as products change. Its four-person public team is hiring a founding AI engineer to deepen agent and automation infrastructure.",
    useCase:
      "Preserve why browser-agent, assertion, self-healing and reliability choices changed across real customer failures. Icarus is especially aligned because Shiplight's product depends on trustworthy engineering history.",
    confidence: "High",
    status: "Published email",
    fit: 5,
    sources:
      "https://jobs.ashbyhq.com/pear-vc/e681cf11-9b8a-4630-86ac-b995a76a77d7 | https://www.linkedin.com/company/shiplight | https://www.shiplight.ai/contact | https://www.linkedin.com/in/will-zhao-57372339",
  },
  {
    company: "Scend",
    channel: "Pear VC portfolio",
    discovery: "https://jobs.ashbyhq.com/pear-vc/328e0c96-4c17-4740-9323-51674c68adc8/",
    team: "3 visible; LinkedIn 2-10",
    founded: 2024,
    ageEvidence: "LinkedIn explicitly lists Founded 2024.",
    stage: "Pre-seed; finance customers",
    location: "New York, NY",
    role: "Founding Engineer",
    poc: "Anirudh Sathya",
    title: "Co-founder & CEO",
    route: "Founder LinkedIn or the Pear/Ashby application; no public founder email verified",
    pocLinkedIn: "https://www.linkedin.com/in/anirudh-sathya",
    companyLinkedIn: "https://www.linkedin.com/company/scendinc",
    context:
      "Scend is an agentic search engine for finance that discovers private companies across many web and data sources. Its three-person public team is hiring a founding engineer for research, crawling and data systems.",
    useCase:
      "Capture why source-selection, crawling, deduplication, ranking and citation choices evolved. Icarus can expose the GitHub evidence behind data-quality tradeoffs as the live-web stack expands.",
    confidence: "Medium",
    status: "Needs direct email research",
    fit: 5,
    sources:
      "https://jobs.ashbyhq.com/pear-vc/328e0c96-4c17-4740-9323-51674c68adc8/ | https://www.linkedin.com/company/scendinc | https://www.linkedin.com/in/anirudh-sathya",
  },
  {
    company: "Onlook",
    channel: "Product Hunt + current careers",
    discovery:
      "https://www.producthunt.com/p/producthunt/hiring-looking-for-work-startup-roles-march-2026",
    team: "4 on YC; official site says 3",
    founded: 2024,
    ageEvidence: "YC explicitly lists Founded 2024.",
    stage: "YC W25; open-source traction",
    location: "San Francisco, CA / Remote US",
    role: "Founding Engineer (Fullstack)",
    poc: "Daniel Farrell",
    title: "Founder",
    route: "Apply through the current YC role or contact the founder on LinkedIn",
    pocLinkedIn: "https://www.linkedin.com/in/danielrfarrell",
    companyLinkedIn: "https://www.linkedin.com/company/onlook-dev",
    context:
      "Onlook is an open-source visual editor that lets designers work directly with production code. The three-to-four-person team supports a large contributor base and is hiring a founding full-stack engineer.",
    useCase:
      "Turn a fast-moving open-source history into cited organizational memory, especially around editor architecture, code generation and contributor decisions. New hires can recover why without interrupting founders.",
    confidence: "Medium",
    status: "Needs direct email research",
    fit: 5,
    sources:
      "https://www.producthunt.com/products/onlook-2 | https://www.ycombinator.com/companies/onlook/jobs | https://www.onlook.ai/about | https://www.linkedin.com/in/danielrfarrell",
  },
  {
    company: "Floto",
    channel: "Product Hunt + current careers",
    discovery:
      "https://www.producthunt.com/p/producthunt/hiring-looking-for-work-startup-roles-october-2025/",
    team: "4 visible; LinkedIn 2-10",
    founded: 2025,
    ageEvidence: "LinkedIn explicitly lists Founded 2025.",
    stage: "Early-stage; global product users",
    location: "Bengaluru / Remote India",
    role: "AI Product Engineer; founding-engineer role previously posted",
    poc: "Rags Vadali",
    title: "Co-founder & CEO",
    route: "Founder LinkedIn or Floto's published role page; no public founder email verified",
    pocLinkedIn: "https://uk.linkedin.com/in/ragsvadali",
    companyLinkedIn: "https://www.linkedin.com/company/floto-ai",
    context:
      "Floto is building an agentic feedback operating system, starting with design critique and QA inside Figma. Its public team has four people and recently advertised an AI product engineering role.",
    useCase:
      "Preserve why agent workflows, Figma integration and feedback-evaluation choices changed across experiments. Icarus can keep design, product and engineering rationale connected to the code that implemented it.",
    confidence: "Medium",
    status: "Needs direct email research",
    fit: 4,
    sources:
      "https://www.producthunt.com/p/producthunt/hiring-looking-for-work-startup-roles-october-2025/ | https://www.linkedin.com/company/floto-ai | https://floto.ai/about | https://uk.linkedin.com/in/ragsvadali",
  },
  {
    company: "Blink.new",
    channel: "Product Hunt + current careers",
    discovery:
      "https://www.producthunt.com/p/producthunt/hiring-looking-for-work-startup-roles-february-2026",
    team: "1 on YC; 10 visible on LinkedIn",
    founded: 2025,
    ageEvidence: "YC and LinkedIn both list Founded 2025.",
    stage: "YC-backed; active hiring",
    location: "San Francisco Bay Area / Remote US",
    role: "Developer Experience Engineer; Full Stack Engineer",
    poc: "Kai Feng",
    title: "Founder",
    route: "Apply through a current YC role or contact the founder on LinkedIn",
    pocLinkedIn: "https://www.linkedin.com/in/kaijiabofeng",
    companyLinkedIn: "https://www.linkedin.com/company/blinkdotnew",
    context:
      "Blink is a full-stack AI app builder with hosted auth, databases, functions and integrations. It remains within the ten-person limit and has multiple current engineering openings.",
    useCase:
      "Make the rationale behind agent behavior, hosting, data primitives and integration boundaries recoverable as the product broadens. Icarus can answer architectural why questions with citations from the repository.",
    confidence: "Medium",
    status: "Needs direct email research",
    fit: 5,
    sources:
      "https://www.producthunt.com/products/blink-21 | https://www.ycombinator.com/companies/blink-new | https://www.linkedin.com/company/blinkdotnew | https://www.linkedin.com/in/kaijiabofeng",
  },
  {
    company: "Floot",
    channel: "Product Hunt + current careers",
    discovery: "https://www.producthunt.com/products/floot",
    team: "4 visible; LinkedIn 2-10",
    founded: 2025,
    ageEvidence: "Product Hunt, YC and LinkedIn all date Floot to 2025.",
    stage: "YC S25; seed; $1M ARR publicly reported",
    location: "San Francisco, CA",
    role: "Founding Full Stack Engineer",
    poc: "Yujian Yao",
    title: "Co-founder",
    route: "hello@floot.com",
    pocLinkedIn: "https://www.linkedin.com/in/yjyao",
    companyLinkedIn: "https://www.linkedin.com/company/floothq",
    context:
      "Floot gives non-coders an integrated AI app-building framework, database and hosting layer. Its four-person public team is hiring a founding full-stack engineer after rapid customer and revenue growth.",
    useCase:
      "Capture why the custom framework, hosting model and database abstractions differ from generic app builders. Icarus can prevent those founding decisions from becoming undocumented lore as engineering expands.",
    confidence: "High",
    status: "Published email",
    fit: 5,
    sources:
      "https://www.producthunt.com/products/floot | https://floot.com/careers | https://www.linkedin.com/company/floothq | https://www.linkedin.com/in/yjyao",
  },
];

const channelRows = [
  [
    "South Park Commons",
    "https://www.southparkcommons.com/jobs",
    "Founder identity + live portfolio role",
    "High",
    "Good, but verify current visible headcount because several companies have crossed 10",
    null,
    "Run weekly; prioritize founding-engineer roles added in the last 30 days",
  ],
  [
    "Pear VC portfolio",
    "https://jobs.ashbyhq.com/pear-vc",
    "Named company + founder-stage engineering role",
    "High",
    "Best current yield for 1-10 technical teams",
    null,
    "Run weekly; search Founding Engineer and verify LinkedIn headcount",
  ],
  [
    "Product Hunt + current careers",
    "https://www.producthunt.com/p/producthunt",
    "Founder-posted role or curated role",
    "Medium",
    "Useful only when a current official careers page still confirms the opening",
    null,
    "Run monthly; cross-check every role before adding",
  ],
  [
    "Product Hunt launches",
    "https://www.producthunt.com/",
    "Maker identity + recent technical launch",
    "High",
    "Strong POC discovery, weak hiring signal by itself",
    null,
    "Use as discovery; require a second live hiring source",
  ],
  [
    "Direct ATS / Ashby",
    "https://jobs.ashbyhq.com/",
    "Current role with detailed stack and team narrative",
    "Medium",
    "High hiring confidence; anonymous recruiter listings must be discarded",
    null,
    "Search weekly for named Founding Engineer roles",
  ],
  [
    "YC Jobs",
    "https://www.ycombinator.com/jobs",
    "Current jobs + explicit team size",
    "High",
    "Very efficient verification, but overlaps the existing Work at YC source",
    null,
    "Use only as a verifier for non-YC discovery channels in this batch",
  ],
  [
    "TinySeed Jobs",
    "https://jobs.tinyseed.com/",
    "Bootstrapped SaaS portfolio roles",
    "Medium",
    "Current engineering yield was effectively zero at check time",
    null,
    "Recheck monthly; do not spend weekly sourcing time here yet",
  ],
];

const holdRows = [
  [
    "Noto",
    "South Park Commons",
    "LinkedIn now lists 11-50 and exposes 25 employee profiles.",
    "Hold for 11-50 batch",
    "https://www.linkedin.com/company/noto-technologies",
  ],
  [
    "Foam",
    "South Park Commons",
    "LinkedIn size band still says 2-10, but the page exposes 14 employee profiles.",
    "Recheck before outreach",
    "https://www.linkedin.com/company/foamai",
  ],
  [
    "Benbase",
    "South Park Commons",
    "LinkedIn now explicitly lists 11-50 employees.",
    "Hold for 11-50 batch",
    "https://www.linkedin.com/company/benbase",
  ],
  [
    "Andy AI",
    "South Park Commons",
    "LinkedIn size band says 2-10, but the page exposes 16 employee profiles.",
    "Recheck before outreach",
    "https://www.linkedin.com/company/with-andy",
  ],
  [
    "AI Frontdesk",
    "Pear VC portfolio",
    "The role describes a 12-person remote team plus a new NYC hub.",
    "Hold for 11-50 batch",
    "https://jobs.ashbyhq.com/pear-vc/2778fc7a-5c61-4dbd-b862-d5277e4b9c57",
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

function toProspectMatrix(rows) {
  return rows.map((row) => [
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

function buildProspectSheet(workbook) {
  const sheet = workbook.worksheets.add("Qualified Prospects");
  sheet.showGridLines = false;
  const lastRow = 5 + prospects.length;

  sheet.getRange("A1:W1").merge();
  sheet.getRange("A1").values = [["Icarus Multi-Channel Prospect Batch"]];
  sheet.getRange("A1:W1").format = {
    fill: "#0F172A",
    font: { bold: true, color: "#FFFFFF", size: 18 },
    verticalAlignment: "center",
  };
  sheet.getRange("A1:W1").format.rowHeight = 34;

  sheet.getRange("A2:W2").merge();
  sheet.getRange("A2").values = [[
    "Strict 1-10-person batch. Every company has a current engineering hiring signal, a named founder-level POC and a source-backed Icarus use case. No guessed email addresses are included.",
  ]];
  sheet.getRange("A2:W2").format = {
    fill: "#E2E8F0",
    font: { color: "#334155", italic: true, size: 10 },
    verticalAlignment: "center",
    wrapText: true,
  };
  sheet.getRange("A2:W2").format.rowHeight = 30;

  sheet.getRange("A3").values = [["Qualified"]];
  sheet.getRange("B3").formulas = [[`=COUNTA(A6:A${lastRow})`]];
  sheet.getRange("D3").values = [["Published emails"]];
  sheet.getRange("E3").formulas = [[`=COUNTIF(T6:T${lastRow},"Published email")`]];
  sheet.getRange("G3").values = [["P1 fits"]];
  sheet.getRange("H3").formulas = [[`=COUNTIF(V6:V${lastRow},"P1")`]];
  sheet.getRange("J3").values = [["Checked"]];
  sheet.getRange("K3").values = [[checkedDate]];
  sheet.getRange("M3").values = [["Team rule"]];
  sheet.getRange("N3:P3").merge();
  sheet.getRange("N3").values = [["1-10; current headcount drift excluded"]];
  sheet.getRange("A3:P3").format = {
    fill: "#F8FAFC",
    font: { color: "#334155", size: 10 },
    verticalAlignment: "center",
    borders: { preset: "outside", style: "thin", color: "#CBD5E1" },
  };
  for (const cell of ["A3", "D3", "G3", "J3", "M3"]) {
    sheet.getRange(cell).format.font = { bold: true, color: "#0F766E", size: 10 };
  }
  for (const cell of ["B3", "E3", "H3"]) {
    sheet.getRange(cell).format.font = { bold: true, color: "#0F172A", size: 11 };
  }
  sheet.getRange("K3").setNumberFormat("yyyy-mm-dd");
  sheet.getRange("A3:P3").format.rowHeight = 24;

  sheet.getRange("A5:W5").values = [prospectColumns];
  sheet.getRange(`A6:W${lastRow}`).values = toProspectMatrix(prospects);
  sheet.getRange("G6").formulas = [['=IF(F6="","",$Y$3-F6)']];
  sheet.getRange(`G6:G${lastRow}`).fillDown();
  sheet.getRange("V6").formulas = [['=IF(U6>=5,CHAR(80)&"1",IF(U6>=4,CHAR(80)&"2",CHAR(80)&"3"))']];
  sheet.getRange(`V6:V${lastRow}`).fillDown();
  sheet.getRange("Y3").values = [[snapshotYear]];
  sheet.getRange("Y3").format.font = { color: "#FFFFFF", size: 1 };
  sheet.getRange(`D6:D${lastRow}`).setNumberFormat("yyyy-mm-dd");
  sheet.getRange(`F6:G${lastRow}`).setNumberFormat("0");
  sheet.getRange(`U6:U${lastRow}`).setNumberFormat("0");

  const dataArea = sheet.getRange(`A5:W${lastRow}`);
  dataArea.format = {
    font: { color: "#172033", size: 9 },
    verticalAlignment: "top",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: "#D8DEE9" },
  };
  sheet.getRange("A5:W5").format = {
    fill: "#0F766E",
    font: { bold: true, color: "#FFFFFF", size: 9 },
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: "#FFFFFF" },
  };
  sheet.getRange("A5:W5").format.rowHeight = 44;
  sheet.getRange(`A6:W${lastRow}`).format.rowHeight = 82;
  sheet.getRange(`A6:A${lastRow}`).format.font = {
    bold: true,
    color: "#0F172A",
    size: 10,
  };
  sheet.getRange(`G6:G${lastRow}`).format.fill = "#ECFDF5";
  sheet.getRange(`U6:V${lastRow}`).format.font = {
    bold: true,
    color: "#0F172A",
    size: 9,
  };

  const table = sheet.tables.add(`A5:W${lastRow}`, true, "QualifiedProspects");
  table.style = "TableStyleMedium4";
  table.showBandedColumns = false;
  table.showFilterButton = true;
  sheet.getRange("A5:W5").format.fill = "#0F766E";
  sheet.getRange("A5:W5").format.font = {
    bold: true,
    color: "#FFFFFF",
    size: 9,
  };

  sheet.getRange(`S6:S${lastRow}`).conditionalFormats.add("containsText", {
    text: "High",
    format: { fill: "#DCFCE7", font: { color: "#166534", bold: true } },
  });
  sheet.getRange(`S6:S${lastRow}`).conditionalFormats.add("containsText", {
    text: "Medium",
    format: { fill: "#FEF3C7", font: { color: "#92400E", bold: true } },
  });
  sheet.getRange(`T6:T${lastRow}`).conditionalFormats.add("containsText", {
    text: "Published email",
    format: { fill: "#DCFCE7", font: { color: "#166534", bold: true } },
  });
  sheet.getRange(`T6:T${lastRow}`).conditionalFormats.add("containsText", {
    text: "Needs direct email research",
    format: { fill: "#FEF3C7", font: { color: "#92400E", bold: true } },
  });
  sheet.getRange(`V6:V${lastRow}`).conditionalFormats.add("containsText", {
    text: "P1",
    format: { fill: "#CCFBF1", font: { color: "#115E59", bold: true } },
  });
  sheet.getRange(`V6:V${lastRow}`).conditionalFormats.add("containsText", {
    text: "P2",
    format: { fill: "#DBEAFE", font: { color: "#1E40AF", bold: true } },
  });
  sheet.getRange(`T6:T${lastRow}`).dataValidation = {
    rule: {
      type: "list",
      values: [
        "Published email",
        "Needs direct email research",
        "Draft approved",
        "Scheduled",
        "Sent",
        "Replied",
        "Closed",
      ],
    },
  };

  const widths = [
    18, 24, 34, 12, 24, 12, 12, 38, 28, 25, 34, 20,
    22, 42, 32, 32, 52, 56, 16, 27, 13, 10, 48,
  ];
  widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, lastRow, 1).format.columnWidth = width;
  });
  sheet.getRange("Y:Y").format.columnWidth = 2;
  sheet.freezePanes.freezeRows(5);
  sheet.freezePanes.freezeColumns(2);
}

function buildChannelSheet(workbook) {
  const sheet = workbook.worksheets.add("Channel Guide");
  sheet.showGridLines = false;
  sheet.getRange("A1:G1").merge();
  sheet.getRange("A1").values = [["Where to source the next 1-10-person batch"]];
  sheet.getRange("A1:G1").format = {
    fill: "#1D4ED8",
    font: { bold: true, color: "#FFFFFF", size: 17 },
    verticalAlignment: "center",
  };
  sheet.getRange("A1:G1").format.rowHeight = 34;
  sheet.getRange("A2:G2").merge();
  sheet.getRange("A2").values = [[
    "Channel quality matters more than raw row count. The yield column is calculated from the qualified prospect sheet; the notes show where future sourcing time is likely to pay off.",
  ]];
  sheet.getRange("A2:G2").format = {
    fill: "#DBEAFE",
    font: { color: "#1E3A8A", italic: true, size: 10 },
    wrapText: true,
    verticalAlignment: "center",
  };
  sheet.getRange("A2:G2").format.rowHeight = 30;

  const headers = [
    "Channel",
    "URL",
    "Best Qualification Signal",
    "POC Discoverability",
    "Current Assessment",
    "Qualified Yield",
    "Recommended Cadence",
  ];
  sheet.getRange("A4:G4").values = [headers];
  sheet.getRange("A5:G11").values = channelRows;
  sheet.getRange("F5").formulas = [[
    '=COUNTIF(\'Qualified Prospects\'!B:B,A5)',
  ]];
  sheet.getRange("F5:F11").fillDown();
  sheet.getRange("A4:G11").format = {
    font: { color: "#172033", size: 9 },
    verticalAlignment: "top",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: "#D8DEE9" },
  };
  sheet.getRange("A4:G4").format = {
    fill: "#1D4ED8",
    font: { bold: true, color: "#FFFFFF", size: 9 },
    verticalAlignment: "center",
    wrapText: true,
  };
  sheet.getRange("A4:G4").format.rowHeight = 38;
  sheet.getRange("A5:G11").format.rowHeight = 62;
  sheet.getRange("A5:A11").format.font = {
    bold: true,
    color: "#0F172A",
    size: 10,
  };
  sheet.getRange("F5:F11").format = {
    fill: "#EFF6FF",
    font: { bold: true, color: "#1D4ED8", size: 11 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
  const table = sheet.tables.add("A4:G11", true, "ChannelGuide");
  table.style = "TableStyleMedium2";
  table.showFilterButton = true;
  sheet.getRange("A4:G4").format.fill = "#1D4ED8";
  const widths = [25, 36, 36, 20, 50, 15, 42];
  widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, 11, 1).format.columnWidth = width;
  });
  sheet.freezePanes.freezeRows(4);
}

function buildHoldSheet(workbook) {
  const sheet = workbook.worksheets.add("Held Outside 1-10");
  sheet.showGridLines = false;
  sheet.getRange("A1:E1").merge();
  sheet.getRange("A1").values = [["Companies intentionally excluded from this batch"]];
  sheet.getRange("A1:E1").format = {
    fill: "#7C2D12",
    font: { bold: true, color: "#FFFFFF", size: 17 },
    verticalAlignment: "center",
  };
  sheet.getRange("A1:E1").format.rowHeight = 34;
  sheet.getRange("A2:E2").merge();
  sheet.getRange("A2").values = [[
    "These companies looked attractive in source listings but failed the strict current 1-10-person check. Keeping them here prevents accidental re-addition and makes a later 11-50 batch easy.",
  ]];
  sheet.getRange("A2:E2").format = {
    fill: "#FFEDD5",
    font: { color: "#7C2D12", italic: true, size: 10 },
    wrapText: true,
    verticalAlignment: "center",
  };
  sheet.getRange("A2:E2").format.rowHeight = 30;
  sheet.getRange("A4:E4").values = [[
    "Company",
    "Discovery Channel",
    "Why Excluded",
    "Next Action",
    "Verification Source",
  ]];
  sheet.getRange("A5:E9").values = holdRows;
  sheet.getRange("A4:E9").format = {
    font: { color: "#172033", size: 9 },
    verticalAlignment: "top",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: "#D8DEE9" },
  };
  sheet.getRange("A4:E4").format = {
    fill: "#9A3412",
    font: { bold: true, color: "#FFFFFF", size: 9 },
    verticalAlignment: "center",
  };
  sheet.getRange("A4:E4").format.rowHeight = 34;
  sheet.getRange("A5:E9").format.rowHeight = 52;
  sheet.getRange("A5:A9").format.font = {
    bold: true,
    color: "#0F172A",
    size: 10,
  };
  const table = sheet.tables.add("A4:E9", true, "HeldCompanies");
  table.style = "TableStyleMedium9";
  table.showFilterButton = true;
  sheet.getRange("A4:E4").format.fill = "#9A3412";
  const widths = [22, 26, 58, 26, 46];
  widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, 9, 1).format.columnWidth = width;
  });
  sheet.freezePanes.freezeRows(4);
}

await fs.mkdir(outputDir, { recursive: true });
const workbook = Workbook.create();
workbook.comments.setSelf({ displayName: "Alankrit" });
buildProspectSheet(workbook);
buildChannelSheet(workbook);
buildHoldSheet(workbook);

for (const [name, range] of [
  ["Qualified Prospects", "A1:W17"],
  ["Channel Guide", "A1:G11"],
  ["Held Outside 1-10", "A1:E9"],
]) {
  const check = await workbook.inspect({
    kind: "table",
    range: `'${name}'!${range}`,
    include: "values,formulas",
    tableMaxRows: 20,
    tableMaxCols: 24,
    maxChars: 12000,
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
  ["Qualified Prospects", "A1:W17", "multi_channel_prospects_preview.png"],
  ["Channel Guide", "A1:G11", "channel_guide_preview.png"],
  ["Held Outside 1-10", "A1:E9", "held_outside_1_10_preview.png"],
]) {
  const preview = await workbook.render({
    sheetName,
    range,
    scale: 1,
    format: "png",
  });
  const bytes = new Uint8Array(await preview.arrayBuffer());
  await fs.writeFile(`${outputDir}/${fileStem}`, bytes);
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(`OUTPUT ${outputPath}`);
