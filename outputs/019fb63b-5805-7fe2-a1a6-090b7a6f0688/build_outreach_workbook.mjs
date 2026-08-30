import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir =
  "/Users/alankritghosh/JARVIS /jarvis_engineering/outputs/019fb63b-5805-7fe2-a1a6-090b7a6f0688";
const outputPath = `${outputDir}/Icarus_HN_Wellfound_Prospects.xlsx`;
const checkedDate = new Date("2026-07-31T00:00:00Z");
const discoveryDate = checkedDate;
const hnSource = "https://news.ycombinator.com/item?id=48747976";

const columns = [
  "Company",
  "Website",
  "Discovery Source",
  "Checked Date",
  "Team Size",
  "Founded Year",
  "Age (Years)",
  "Age Evidence / Caveat",
  "Stage",
  "Location",
  "Open Engineering Role",
  "POC",
  "POC Title",
  "Verified Email / Contact Route",
  "POC LinkedIn",
  "Company Context",
  "Ideal Icarus Use Case",
  "Contact Confidence",
  "Outreach Status",
  "Verification Sources",
];

const hackerNewsRows = [
  {
    company: "Lumen Labs",
    website: "https://lumenresearch.ai",
    source: hnSource,
    checked: discoveryDate,
    team: "2 now; hire would be #3",
    founded: 2026,
    ageEvidence:
      "Founder post shows a two-person pre-seed team in 2026. Legal incorporation date is not public.",
    stage: "Pre-seed; seed planned in 2026",
    location: "Remote US/Canada; SF onsite from fall 2026",
    role: "Simulation / RL Integration Engineer",
    poc: "Founding team",
    title: "Co-founders",
    email: "hi@lumenresearch.co",
    linkedin: "Not publicly verified",
    context:
      "Building the cognitive layer for physical AI by testing model architectures across robotics simulations. The two-person team has runway into 2027 and is preparing for a seed raise.",
    icarus:
      "Capture why behind simulator adapters, evaluation harnesses and model-versus-simulation tradeoffs before hire #3 expands the oral-history bottleneck. Let engineers retrieve the PR and experiment evidence behind each decision.",
    confidence: "High",
    status: "Ready to draft",
    verification:
      "https://lumenresearch.co | https://lumenresearch.co/paper | " + hnSource,
  },
  {
    company: "Trinsic",
    website: "https://trinsic.id",
    source: hnSource,
    checked: discoveryDate,
    team: "4 now; role is #5",
    founded: 2019,
    ageEvidence:
      "Streetcred launched products in Aug 2019 and later became Trinsic; LinkedIn lists 2-10 employees.",
    stage: "Early growth; revenue surging",
    location: "Remote Europe / North America",
    role: "Senior Product Engineer",
    poc: "Jan-Pieter George",
    title: "CTO",
    email: "Apply via Trinsic careers; direct email not publicly verified",
    linkedin: "https://www.linkedin.com/in/jp-george",
    context:
      "Identity acceptance network that lets businesses accept reusable digital IDs. A tiny privacy and security-focused team is adding a high-ownership backend/platform engineer as its fifth member.",
    icarus:
      "Preserve the rationale behind identity, privacy, data-security and cloud decisions as regulation and customer requirements shift. A cited engineering memory would reduce repeated debate when a five-person team revisits old tradeoffs.",
    confidence: "Medium",
    status: "Contact via platform",
    verification:
      "https://www.linkedin.com/company/trinsic-id | https://trinsic.id/introducing-trinsic/ | " +
      hnSource,
  },
  {
    company: "DrSwarm",
    website: "https://drswarm.com",
    source: hnSource,
    checked: discoveryDate,
    team: "2 visible; LinkedIn 2-10",
    founded: 2026,
    ageEvidence: "LinkedIn explicitly lists Founded 2026.",
    stage: "0-to-1 / early stage",
    location: "Remote US or LATAM; Pacific overlap",
    role: "Founding Engineer, Full-Stack",
    poc: "Michael Nusimow",
    title: "Founder & CEO",
    email: "jobs@drswarm.com",
    linkedin: "https://www.linkedin.com/in/mnusimow",
    context:
      "AI workflow automation for ambulatory clinics and health systems, layered over EHR and revenue-cycle systems. The product handles scheduling, billing, patient operations and other exception-heavy workflows.",
    icarus:
      "Keep a cited record of why HIPAA-aware integrations, retry logic, human escalation and reliability controls were designed a certain way. That memory becomes critical as the first engineer expands a regulated, exception-heavy stack.",
    confidence: "High",
    status: "Ready to draft",
    verification:
      "https://www.linkedin.com/company/drswarm | https://www.linkedin.com/in/mnusimow | " +
      hnSource,
  },
  {
    company: "Delta AI",
    website: "https://learndelta.ai",
    source: hnSource,
    checked: discoveryDate,
    team: "LinkedIn 2-10",
    founded: null,
    ageEvidence:
      "Founding year is not disclosed. Public company activity and the website were visible by 2025.",
    stage: "Seed round in progress",
    location: "SF Bay Area; onsite / local",
    role: "Full-Stack / AI Founding Engineer",
    poc: "Mark Buonforte",
    title: "Co-founder & CEO",
    email: "hiring@learndelta.ai",
    linkedin: "https://www.linkedin.com/in/mark-buonforte",
    context:
      "Scenario-based conversational AI training for high-stakes sales, negotiation, leadership and government exercises. The dual-use team is raising seed funding and hiring a founding engineer to shape the full stack.",
    icarus:
      "Capture why speech, evaluation, observability and dual-use product constraints led to specific architecture choices. New engineers could retrieve the evidence behind model behavior and government-versus-commercial tradeoffs.",
    confidence: "High",
    status: "Ready to draft",
    verification:
      "https://www.linkedin.com/company/learn-delta | https://learndelta.ai | " + hnSource,
  },
  {
    company: "Kiloforge",
    website: "https://kiloforge.com",
    source: hnSource,
    checked: discoveryDate,
    team: "Small founding team; exact count undisclosed",
    founded: 2026,
    ageEvidence:
      "Current founders describe starting Kiloforge in 2026; legal incorporation date is not public.",
    stage: "Seed; $5M+ raised",
    location: "San Francisco; onsite",
    role: "Founding Engineer",
    poc: "Nate Tucker",
    title: "Founder",
    email: "DM @kiloforgeai on X; no application email published",
    linkedin: "https://www.linkedin.com/in/nate-tucker-543b4872",
    context:
      "Building an autonomous app factory that discovers niches, validates ideas, ships software and operates a portfolio of micro-apps. Its own agents already sweep company systems to produce engineering logs and operational messages.",
    icarus:
      "Ground the 'why' behind shared scaffolding, app templates, agent orchestration and portfolio experiments in GitHub evidence. Icarus can distinguish durable decisions from agent-written summaries as dozens of products reuse the same foundations.",
    confidence: "Medium",
    status: "Contact via platform",
    verification:
      "https://kiloforge.com/careers/ | https://www.linkedin.com/in/nate-tucker-543b4872 | " +
      hnSource,
  },
  {
    company: "FanShares",
    website: "https://www.fansharesapp.com",
    source: hnSource,
    checked: discoveryDate,
    team: "2 visible; LinkedIn 2-10",
    founded: 2025,
    ageEvidence: "LinkedIn explicitly lists Founded 2025.",
    stage: "Pre-seed; seed opening",
    location: "Remote USA",
    role: "Founding Engineer / CTO",
    poc: "Leon Tash",
    title: "Co-founder",
    email: "leon@fansharesapp.com",
    linkedin: "https://www.linkedin.com/in/leontash",
    context:
      "A regulated peer-to-peer exchange where fans trade positions in individual athletes. The beta handled about 1,000 users and 21,000 trades, while the technical build still needs an owner.",
    icarus:
      "Preserve the reasoning behind matching, settlement, ledger, custody and on-chain-versus-off-chain choices. In a correctness-critical system, cited decision history helps future engineers and regulators understand why invariants exist.",
    confidence: "High",
    status: "Ready to draft",
    verification:
      "https://www.linkedin.com/company/fansharesapp | https://www.linkedin.com/in/leontash | " +
      hnSource,
  },
  {
    company: "CivTiq",
    website: "https://www.civtiq.com",
    source: hnSource,
    checked: discoveryDate,
    team: "Founder + first technical lead; exact count undisclosed",
    founded: 2026,
    ageEvidence:
      "A municipal pilot was being discussed by March 2026; legal incorporation date is not public.",
    stage: "Pre-seed / pilot stage",
    location: "Toronto; onsite",
    role: "Lead Software Engineer",
    poc: "Ben (surname not public)",
    title: "Founder",
    email: "ben@civtiq.com",
    linkedin: "Not publicly verified",
    context:
      "White-label reporting infrastructure for North American municipal governments. The first technical lead will own multi-tenant architecture, Canadian data residency and public-sector compliance.",
    icarus:
      "Record the evidence behind tenancy, residency, SOC 2, PIPEDA and municipal-procurement decisions. That creates an auditable engineering memory when government evaluators ask why the platform works the way it does.",
    confidence: "Medium",
    status: "Verify team size",
    verification:
      "https://www.civtiq.com | https://hnhiring.com/locations/toronto | " + hnSource,
  },
  {
    company: "Tabula Bio",
    website: "https://www.tabulabio.com",
    source: hnSource,
    checked: discoveryDate,
    team: "6 staff listed on official site",
    founded: 2026,
    ageEvidence:
      "Official site says the company began treating patients six months after starting; current public launch is 2026.",
    stage: "Early stage; investor-backed",
    location: "San Francisco; onsite",
    role: "Founding Machine Learning Scientist",
    poc: "Ammon Bartram",
    title: "Member of Biological Staff",
    email: "ammon@tabulabio.com",
    linkedin: "https://www.linkedin.com/in/ammon-bartram-2aaa6712",
    context:
      "Uses generative ML to design bacteriophages against antibiotic-resistant infections. The team treats genome design as a software-speed learning problem and is already working with real patients.",
    icarus:
      "Preserve why model, dataset, evaluation and genome-design decisions changed across experiments. Cited GitHub history can help ML and biology collaborators separate recorded evidence from assumptions in a high-stakes research workflow.",
    confidence: "High",
    status: "Ready to draft",
    verification:
      "https://www.tabulabio.com | https://www.linkedin.com/in/ammon-bartram-2aaa6712 | " +
      hnSource,
  },
  {
    company: "Tetherline",
    website: "https://www.tetherline.dev",
    source: hnSource,
    checked: discoveryDate,
    team: "Small technical team; exact count undisclosed",
    founded: 2026,
    ageEvidence:
      "Stealth company and public hiring page appeared in 2026; legal incorporation date is not public.",
    stage: "Stealth; well-funded; design partners",
    location: "New York City; onsite",
    role: "Founding Engineer",
    poc: "Founding team",
    title: "Founders (names not public)",
    email: "contact@tetherline.dev",
    linkedin: "Not publicly verified",
    context:
      "Building the execution layer that lets AI agents operate proprietary scientific instruments. The work spans low-level systems, lab hardware, agent runtimes and ML infrastructure.",
    icarus:
      "Capture why each instrument adapter, safety boundary and agent-runtime decision exists as the first engineers bridge proprietary lab systems. The highest value is preventing hardware knowledge from staying only in founders' heads.",
    confidence: "Medium",
    status: "Needs POC identity",
    verification: "https://www.tetherline.dev | " + hnSource,
  },
  {
    company: "PostSilo",
    website: "https://postsilo.ai",
    source: hnSource,
    checked: discoveryDate,
    team: "Founding-engineer stage; exact count undisclosed",
    founded: 2026,
    ageEvidence:
      "USPTO record shows first commercial use and filing in April 2026.",
    stage: "Early stage; initial customers",
    location: "Remote USA",
    role: "Founding Engineers, Data/Retrieval and AI/Infrastructure",
    poc: "Founding team",
    title: "Founders (names not public)",
    email: "Apply via postsilo.ai/resources; direct email not public",
    linkedin: "Not publicly verified",
    context:
      "Privacy-first AI automation and retrieval for professional-services firms handling sensitive client work. The product is moving from initial customers toward hundreds of firms.",
    icarus:
      "Preserve why privacy boundaries, retrieval architecture, model choices and customer-specific integrations were selected. Icarus fits their own trust posture by giving engineers evidence-backed answers instead of unsupported model memory.",
    confidence: "Medium",
    status: "Needs POC/email verification",
    verification:
      "https://postsilo.ai/resources/ | https://trademarks.justia.com/997/51/postsilo-99751322.html | " +
      hnSource,
  },
];

const wellfoundRows = [
  {
    company: "Deepgrids",
    website: "https://www.deepgrids.com",
    source: "https://wellfound.com/jobs/3651461-founding-engineer",
    checked: checkedDate,
    team: "1-10 (Wellfound); LinkedIn 2-10",
    founded: 2026,
    ageEvidence: "LinkedIn explicitly lists Founded 2026.",
    stage: "Early stage",
    location: "Remote USA",
    role: "Founding Engineer",
    poc: "Matthew Jeanty",
    title: "Founder & CEO",
    email: "Apply on Wellfound or LinkedIn DM; no public email verified",
    linkedin: "https://www.linkedin.com/in/matthew-jeanty-a42bbb328",
    context:
      "Coordination infrastructure for enterprise deal execution across approvals, legal, security and finance. Its product uses temporal knowledge graphs and bounded AI agents to maintain process state.",
    icarus:
      "Capture why the team modeled deal state, graph relationships and agent boundaries in particular ways. A cited engineering memory would help a founding engineer change enterprise workflows without losing the rationale behind them.",
    confidence: "Medium",
    status: "Contact via platform",
    verification:
      "https://www.linkedin.com/company/deepgrids | https://wellfound.com/company/deepgrids/people",
  },
  {
    company: "PosterChild.ai",
    website: "https://www.posterchild.ai",
    source: "https://wellfound.com/jobs/4121787-founding-engineer",
    checked: checkedDate,
    team: "1-10 (Wellfound); LinkedIn 2-10",
    founded: 2024,
    ageEvidence: "LinkedIn explicitly lists Founded 2024.",
    stage: "Pre-seed; $3M raised",
    location: "Berkeley / Bay Area; hybrid or remote",
    role: "Founding Engineer",
    poc: "Leandrew Robinson",
    title: "Founder",
    email: "Leandrew@posterchild.ai",
    linkedin: "https://www.linkedin.com/in/leandrew-robinson-b679079",
    context:
      "AI storytelling and fundraising platform for nonprofits, with 38+ customers and a $3M pre-seed round. The team is moving from a fast-shipping product to a more rigorous engineering foundation.",
    icarus:
      "Turn the existing GitHub history into onboarding memory for the founding engineer, including why fundraising-agent and story workflows evolved. Their public note of 1,724 commits suggests enough history for Icarus to deliver immediate value.",
    confidence: "High",
    status: "Ready to draft",
    verification:
      "https://www.linkedin.com/company/posterchildai | https://www.linkedin.com/in/leandrew-robinson-b679079",
  },
  {
    company: "LocalRoute.ai",
    website: "https://wellfound.com/jobs/3708543-founding-engineer",
    source: "https://wellfound.com/jobs/3708543-founding-engineer",
    checked: checkedDate,
    team: "1-10 (Wellfound)",
    founded: 2026,
    ageEvidence:
      "The listing describes a pre-launch company preparing for YC Summer 2026; incorporation date is not disclosed.",
    stage: "Pre-seed / pre-launch",
    location: "San Francisco / Manhattan / remote",
    role: "Founding Engineer",
    poc: "Jessica Hunsucker",
    title: "Founder",
    email: "Apply on Wellfound; direct email not publicly verified",
    linkedin: "Not publicly verified",
    context:
      "Privacy-aware AI infrastructure for on-prem and hybrid deployments. The company is pre-launch and wants its first engineer to shape security, extensibility and core systems from day one.",
    icarus:
      "Record why on-prem, hybrid, isolation and deployment choices were made while the architecture is still fluid. Icarus can make the early security rationale discoverable once the team grows beyond its founders.",
    confidence: "Medium",
    status: "Contact via platform",
    verification: "https://wellfound.com/jobs/3708543-founding-engineer",
  },
  {
    company: "Caro",
    website: "https://carohq.com",
    source: "https://wellfound.com/jobs/3252043-founding-engineer",
    checked: checkedDate,
    team: "1-10 (Wellfound); LinkedIn 2-10",
    founded: 2023,
    ageEvidence: "LinkedIn explicitly lists Founded 2023.",
    stage: "Seed; $5M raised",
    location: "Palo Alto; in office",
    role: "Founding Engineer",
    poc: "Roopak Venkatakrishnan",
    title: "Co-founder",
    email: "info@carohq.com",
    linkedin: "https://www.linkedin.com/in/roopakv",
    context:
      "Governed workforce planning that connects HRIS, ATS and FP&A systems with auditable headcount changes. The seed-backed team already serves recognizable technology customers.",
    icarus:
      "Preserve why integration semantics, data definitions and audit rules were chosen across Workday, Greenhouse/Ashby and finance workflows. That helps a small team answer customer-specific questions without re-litigating old design decisions.",
    confidence: "High",
    status: "Ready to draft",
    verification:
      "https://www.linkedin.com/company/carohq | https://carohq.com",
  },
  {
    company: "AMS AI",
    website: "https://www.amshealth.ai",
    source: "https://wellfound.com/jobs/4262898-founding-software-engineer",
    checked: checkedDate,
    team: "1-10 (Wellfound); LinkedIn 2-10",
    founded: 2025,
    ageEvidence:
      "Public founder activity describes building and customer discovery through 2025; legal founding date is not disclosed.",
    stage: "Seed; $1M raised",
    location: "Remote USA; NYC / Washington DC",
    role: "Founding Software Engineer",
    poc: "Roy Malkin",
    title: "Founder & CEO",
    email: "Apply on Wellfound or LinkedIn DM; no public email verified",
    linkedin: "https://www.linkedin.com/in/roymalkin",
    context:
      "Agentic procurement automation for hospital supply chains, layered over legacy systems and contracts. Early pilots target savings, shortage reduction and human-in-the-loop purchasing decisions.",
    icarus:
      "Capture why regulated integrations, approval gates, scoring and auditability work the way they do. Cited engineering history would help the founding engineer explain high-stakes decisions to hospitals and future teammates.",
    confidence: "Medium",
    status: "Contact via platform",
    verification:
      "https://www.linkedin.com/company/ams-ai-healthcare | https://www.linkedin.com/in/roymalkin",
  },
  {
    company: "Inference",
    website: "https://launchinference.com",
    source: "https://wellfound.com/jobs/4322382-founding-engineer",
    checked: checkedDate,
    team: "1-10 (Wellfound)",
    founded: 2026,
    ageEvidence: "Pre-seed funding closed in May 2026 and founder joined in 2026.",
    stage: "Pre-seed; $500K raised",
    location: "San Francisco / Berkeley; hybrid",
    role: "Founding Engineer",
    poc: "Ed White",
    title: "Founder",
    email: "Apply on Wellfound or LinkedIn DM; no public email verified",
    linkedin: "https://www.linkedin.com/in/edwhitesf",
    context:
      "AI-native business operations and analytics with three committed customers. The first engineer will own frontend, backend, APIs, data model and third-party integrations.",
    icarus:
      "Create the durable record for the first architecture, data model and integration decisions before more engineers arrive. Icarus is most valuable here as the bridge between founder context and the next technical hires.",
    confidence: "Medium",
    status: "Contact via platform",
    verification:
      "https://wellfound.com/company/inference-8 | https://www.linkedin.com/in/edwhitesf",
  },
  {
    company: "Zunesha Labs",
    website: "https://www.zunesha.ai",
    source: "https://wellfound.com/jobs/4220289-founding-engineer",
    checked: checkedDate,
    team: "1-10 (Wellfound); two-person founding team",
    founded: 2026,
    ageEvidence:
      "The listing describes a two-person, pre-launch founding team in 2026; incorporation date is not disclosed.",
    stage: "Pre-seed / pre-launch",
    location: "Austin / Toronto / remote",
    role: "Founding Engineer",
    poc: "Omar Alani",
    title: "Founder & CEO",
    email: "Apply on Wellfound; direct email not publicly verified",
    linkedin: "https://wellfound.com/company/zunesha-labs/people",
    context:
      "Purpose-built runtime infrastructure for long-running, stateful AI agents. The platform focuses on isolation, networking, storage and lifecycle management without Kubernetes-level complexity.",
    icarus:
      "Preserve the why behind runtime isolation, networking, storage and lifecycle primitives as they become foundational contracts. Those decisions will be difficult and expensive to reconstruct after the founding team expands.",
    confidence: "Medium",
    status: "Contact via platform",
    verification:
      "https://wellfound.com/company/zunesha-labs/people | https://wellfound.com/jobs/4220289-founding-engineer",
  },
  {
    company: "L2 Labs",
    website: "https://www.l2labs.ai",
    source: "https://wellfound.com/jobs/3822971-founding-software-engineer",
    checked: checkedDate,
    team: "1-10 (Wellfound); 4 people on official site",
    founded: 2025,
    ageEvidence:
      "Wellfound lists the founder at one year and current company activity in 2025-2026.",
    stage: "Pre-seed; $875K raised",
    location: "New York City; hybrid",
    role: "Founding Software Engineer",
    poc: "Andrew Bell",
    title: "Founder & CEO",
    email: "me@andrewbell.io",
    linkedin: "https://wellfound.com/company/l2-labs/people",
    context:
      "Applied AI lab for schema matching, entity resolution and enterprise data interoperability, starting with EDI. It turns partner integration artifacts into mappings with expert review.",
    icarus:
      "Capture the link between research hypotheses, production mappings, evaluation results and code changes. A cited decision memory would help researchers and engineers understand why a model or integration path won.",
    confidence: "High",
    status: "Ready to draft",
    verification:
      "https://www.l2labs.ai | https://andrewbell.io | https://wellfound.com/company/l2-labs/people",
  },
  {
    company: "Good Shout",
    website: "https://wellfound.com/jobs/3708532-founding-engineer",
    source: "https://wellfound.com/jobs/3708532-founding-engineer",
    checked: checkedDate,
    team: "1-10 (Wellfound)",
    founded: 2026,
    ageEvidence:
      "The listing describes an MVP-stage founder-led company in 2026; incorporation date is not disclosed.",
    stage: "Pre-seed / MVP",
    location: "California / San Francisco / Orange County",
    role: "Founding Engineer",
    poc: "Cyrus Janssen",
    title: "Founder",
    email: "Apply on Wellfound; direct email not publicly verified",
    linkedin: "https://www.linkedin.com/in/cyrus-janssen",
    context:
      "AI-powered personalized discovery for food, music and experiences. The founding engineer will turn early design work into the first production mobile product.",
    icarus:
      "Start capturing why product and mobile-architecture decisions change during MVP testing so later hires inherit the user-learning behind the code. The value will rise as its GitHub history accumulates.",
    confidence: "Medium",
    status: "Contact via platform",
    verification:
      "https://www.linkedin.com/in/cyrus-janssen | https://wellfound.com/jobs/3708532-founding-engineer",
  },
  {
    company: "Eduvero",
    website: "https://www.eduvero.com",
    source: "https://wellfound.com/jobs/3626383-founding-engineer",
    checked: checkedDate,
    team: "1-10 (Wellfound); LinkedIn 2-10",
    founded: 2023,
    ageEvidence: "LinkedIn explicitly lists Founded 2023.",
    stage: "Friends & family; $90K raised",
    location: "Atlanta / remote; company in Boston",
    role: "Founding Engineer",
    poc: "Elizabeth Hackett",
    title: "Founder / educator",
    email: "info@eduvero.com",
    linkedin: "https://www.linkedin.com/in/elizabeth-hackett-54604ab9",
    context:
      "Teacher-first mobile AI that turns classroom signals into real-time instructional strategies and lesson support. The live MVP emphasizes teacher judgment rather than automated decision-making.",
    icarus:
      "Preserve why student-data, privacy, recommendation and teacher-control boundaries were chosen. Icarus can help future engineers retrieve the product and evidence rationale behind sensitive education workflows.",
    confidence: "High",
    status: "Ready to draft",
    verification:
      "https://www.linkedin.com/company/eduvero | https://www.eduvero.com | https://www.linkedin.com/in/elizabeth-hackett-54604ab9",
  },
];

function toMatrix(rows) {
  return rows.map((row) => [
    row.company,
    row.website,
    row.source,
    row.checked,
    row.team,
    row.founded,
    null,
    row.ageEvidence,
    row.stage,
    row.location,
    row.role,
    row.poc,
    row.title,
    row.email,
    row.linkedin,
    row.context,
    row.icarus,
    row.confidence,
    row.status,
    row.verification,
  ]);
}

function buildSheet(workbook, name, subtitle, rows, accent, tableName) {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;

  sheet.getRange("A1:T1").merge();
  sheet.getRange("A1").values = [[name + " Prospect List"]];
  sheet.getRange("A1:T1").format = {
    fill: "#0F172A",
    font: { bold: true, color: "#FFFFFF", size: 18 },
    verticalAlignment: "center",
  };
  sheet.getRange("A1:T1").format.rowHeight = 34;

  sheet.getRange("A2:T2").merge();
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange("A2:T2").format = {
    fill: "#E2E8F0",
    font: { color: "#334155", italic: true, size: 10 },
    verticalAlignment: "center",
    wrapText: true,
  };
  sheet.getRange("A2:T2").format.rowHeight = 30;

  sheet.getRange("A3").values = [["Qualified companies"]];
  sheet.getRange("B3").values = [[rows.length]];
  sheet.getRange("D3").values = [["Checked"]];
  sheet.getRange("E3").values = [[checkedDate]];
  sheet.getRange("H3").values = [["Snapshot year"]];
  sheet.getRange("I3").values = [[2026]];
  sheet.getRange("K3").values = [["Team rule"]];
  sheet.getRange("L3:N3").merge();
  sheet.getRange("L3").values = [["1-10 employees; uncertainties flagged"]];
  sheet.getRange("A3:N3").format = {
    fill: "#F8FAFC",
    font: { color: "#334155", size: 10 },
    verticalAlignment: "center",
  };
  sheet.getRange("A3:N3").format.borders = {
    preset: "outside",
    style: "thin",
    color: "#CBD5E1",
  };
  for (const cell of ["A3", "D3", "H3", "K3"]) {
    sheet.getRange(cell).format.font = { bold: true, color: accent, size: 10 };
  }
  sheet.getRange("B3").format.font = { bold: true, color: "#0F172A", size: 11 };
  sheet.getRange("E3").setNumberFormat("yyyy-mm-dd");
  sheet.getRange("A3:N3").format.rowHeight = 24;

  sheet.getRange("A5:T5").values = [columns];
  sheet.getRange("A6:T15").values = toMatrix(rows);
  sheet.getRange("G6").formulas = [['=IF(F6="","",$I$3-F6)']];
  sheet.getRange("G6:G15").fillDown();
  sheet.getRange("D6:D15").setNumberFormat("yyyy-mm-dd");
  sheet.getRange("F6:G15").setNumberFormat("0");

  const dataArea = sheet.getRange("A5:T15");
  dataArea.format = {
    font: { color: "#172033", size: 9 },
    verticalAlignment: "top",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: "#D8DEE9" },
  };
  sheet.getRange("A5:T5").format = {
    fill: accent,
    font: { bold: true, color: "#FFFFFF", size: 9 },
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: "#FFFFFF" },
  };
  sheet.getRange("A5:T5").format.rowHeight = 42;
  sheet.getRange("A6:T15").format.rowHeight = 78;
  sheet.getRange("A6:A15").format.font = { bold: true, color: "#0F172A", size: 10 };
  sheet.getRange("G6:G15").format.fill = "#EFF6FF";
  sheet.getRange("R6:R15").format.font = { bold: true, color: "#0F172A", size: 9 };
  sheet.getRange("S6:S15").format.font = { bold: true, color: "#0F172A", size: 9 };

  const table = sheet.tables.add("A5:T15", true, tableName);
  table.style = "TableStyleMedium2";
  table.showBandedColumns = false;
  table.showFilterButton = true;
  sheet.getRange("A5:T5").format.fill = accent;
  sheet.getRange("A5:T5").format.font = { bold: true, color: "#FFFFFF", size: 9 };

  sheet.getRange("R6:R15").conditionalFormats.add("containsText", {
    text: "High",
    format: { fill: "#DCFCE7", font: { color: "#166534", bold: true } },
  });
  sheet.getRange("R6:R15").conditionalFormats.add("containsText", {
    text: "Medium",
    format: { fill: "#FEF3C7", font: { color: "#92400E", bold: true } },
  });
  sheet.getRange("S6:S15").conditionalFormats.add("containsText", {
    text: "Ready to draft",
    format: { fill: "#DCFCE7", font: { color: "#166534", bold: true } },
  });
  sheet.getRange("S6:S15").conditionalFormats.add("containsText", {
    text: "Needs",
    format: { fill: "#FEE2E2", font: { color: "#991B1B", bold: true } },
  });
  sheet.getRange("S6:S15").conditionalFormats.add("containsText", {
    text: "Verify",
    format: { fill: "#FEF3C7", font: { color: "#92400E", bold: true } },
  });
  sheet.getRange("S6:S15").conditionalFormats.add("containsText", {
    text: "Contact via platform",
    format: { fill: "#DBEAFE", font: { color: "#1E40AF", bold: true } },
  });
  sheet.getRange("S6:S15").dataValidation = {
    rule: {
      type: "list",
      values: [
        "Ready to draft",
        "Contact via platform",
        "Verify team size",
        "Needs POC identity",
        "Needs POC/email verification",
      ],
    },
  };

  const widths = [
    19, 27, 32, 12, 23, 12, 11, 34, 22, 25,
    30, 21, 20, 36, 32, 48, 52, 16, 25, 45,
  ];
  widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, 15, 1).format.columnWidth = width;
  });

  sheet.freezePanes.freezeRows(5);
  sheet.freezePanes.freezeColumns(2);
  return sheet;
}

await fs.mkdir(outputDir, { recursive: true });
const workbook = Workbook.create();
workbook.comments.setSelf({ displayName: "Alankrit" });

buildSheet(
  workbook,
  "Hacker News",
  "10 engineering-hiring companies discovered only through the July 2026 Hacker News 'Who is hiring?' thread. Exact 1-10 counts are used where public; founder-posted small-team claims are visibly flagged.",
  hackerNewsRows,
  "#F97316",
  "HackerNewsCompanies",
);
buildSheet(
  workbook,
  "Wellfound",
  "10 active engineering listings discovered only through Wellfound and explicitly marked 1-10 employees. Official sites and LinkedIn are used only to verify age, POC and contact details.",
  wellfoundRows,
  "#6D5DFB",
  "WellfoundCompanies",
);

const hnCheck = await workbook.inspect({
  kind: "table",
  range: "'Hacker News'!A1:T15",
  include: "values,formulas",
  tableMaxRows: 15,
  tableMaxCols: 20,
  maxChars: 9000,
});
console.log("HN_CHECK");
console.log(hnCheck.ndjson);

const wfCheck = await workbook.inspect({
  kind: "table",
  range: "'Wellfound'!A1:T15",
  include: "values,formulas",
  tableMaxRows: 15,
  tableMaxCols: 20,
  maxChars: 9000,
});
console.log("WF_CHECK");
console.log(wfCheck.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
console.log("ERROR_SCAN");
console.log(errors.ndjson);

for (const sheetName of ["Hacker News", "Wellfound"]) {
  const preview = await workbook.render({
    sheetName,
    range: "A1:T15",
    scale: 1,
    format: "png",
  });
  const bytes = new Uint8Array(await preview.arrayBuffer());
  await fs.writeFile(
    `${outputDir}/${sheetName.toLowerCase().replaceAll(" ", "_")}_preview.png`,
    bytes,
  );
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(`OUTPUT ${outputPath}`);
