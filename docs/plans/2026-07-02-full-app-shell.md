# Full App Shell (U1-B) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the "Quiet Native Memory v2" windowed macOS shell (Figma file
`SbmCti2rnsog2rwrzzCWm0`, frame `5:2`) — sidebar nav, hero card, metrics, recent
questions, proof drawer, voice overlay — as the app's primary window, with **every
data surface wired to real sources and honest empty states, never seeded fakes.**

**Architecture:** One primary SwiftUI window (`ShellView`) hosted by a
`MainWindowController`, with a sidebar that routes between five surfaces (Home,
Ask by voice, Decision history, Unknowns, Privacy boundary). Sign-in + connect
become the Home surface's gate (no separate onboarding window). The ⌘⇧Space
overlay stays for asking in the flow. All display data comes from the existing
brain endpoints (`/status`, `/ask`) plus a new in-session `AskHistory`; the
mockup's invented numbers/history are deliberately **not** reproduced.

**Tech Stack:** SwiftUI + AppKit (SwiftPM, macOS 14), the existing `IcarusKit`
models, `Theme.swift` v2 tokens, `unittest`-style XCTest for the pure logic.

**Run tests:** `cd mac/Icarus && swift build && swift test`.

---

## The non-negotiable for this brick: no fabricated data

Icarus's whole value is that it cannot bluff. The Figma mock is a *visual* target;
its **data is placeholder** and must not ship as-is. Reproducing "14.2K PRs
indexed / 98% answers cited", the seeded question history, "Acme private cloud",
or receipts like `review:marina:17` would put a lie on the investor's screen and
violate the product's one hard constraint. This plan builds the mock's **look**
and wires its **data to truth**. If a surface has no real backing yet, it shows an
honest empty state — never a convincing fake.

### Honest-data mapping (build the chrome, wire the data to these)

| Mock element (node) | Mock shows (FAKE) | Build from (REAL) |
|---|---|---|
| Metrics card (`5:59`) | "14.2K PRs indexed / 98% / 0" | `/status` counts (`pr`/`issue`/`code`) + this-session cited-rate; "0 trained on code" is a true constant |
| Recent questions (`5:66`) | seeded MSW/billing questions | `AskHistory` — real asks this session; empty state when none |
| Decision history nav | (same seeded list) | full `AskHistory` |
| Unknowns nav | — | `AskHistory` filtered to `verdict == .unknown` |
| Proof drawer (`5:94`) | `pr:1482`, `review:marina:17` | the **last real answer's** citations (`CitationChip`) + last honest unknown |
| Sidebar "COMPANY BRAIN" (`5:39/40`) | "Acme private cloud" | real connected repo from `/status` (e.g. `simonw/llm`) + "Zero training on code" (true) |
| Hero card (`5:47`) | "⌘⇧Space" (WRONG in mock) | **real trigger: hold Right Option (⌥) to ask by voice**; ⌘⇧I opens the typed overlay; "Try a question" opens the overlay |
| "GitHub indexed 4m ago" pill (`5:45`) | "4m ago" | real repo name + real indexed state from `/status` |

---

## Phase A — Real data foundations (IcarusKit, testable)

### Task 1: `AskHistory` — the in-session record of real asks

**Files:**
- Create: `mac/Icarus/Sources/IcarusKit/AskHistory.swift`
- Test: `mac/Icarus/Tests/IcarusKitTests/AskHistoryTests.swift`

**Step 1: Write the failing test**

```swift
import XCTest
@testable import IcarusKit

final class AskHistoryTests: XCTestCase {
    private func answer(_ q: String, _ v: Verdict, cites: [String] = []) -> AskResponse {
        AskResponse(verdict: v, answer: v == .answer ? "because X" : "",
                    citations: cites.map { Citation(ref: $0, url: nil) }, searched: ["code:a.py"])
    }

    @MainActor func testRecordsMostRecentFirst() {
        let h = AskHistory()
        h.record(question: "why A?", response: answer("why A?", .answer, cites: ["pr:1"]))
        h.record(question: "why B?", response: answer("why B?", .unknown))
        XCTAssertEqual(h.entries.map(\.question), ["why B?", "why A?"])
    }

    @MainActor func testUnknownsFilter() {
        let h = AskHistory()
        h.record(question: "a", response: answer("a", .answer, cites: ["pr:1"]))
        h.record(question: "b", response: answer("b", .unknown))
        XCTAssertEqual(h.unknowns.map(\.question), ["b"])
    }

    @MainActor func testCitedRate() {
        let h = AskHistory()
        XCTAssertNil(h.citedRate)                 // no asks yet → nil, never a fake %
        h.record(question: "a", response: answer("a", .answer, cites: ["pr:1"]))
        h.record(question: "b", response: answer("b", .unknown))
        XCTAssertEqual(h.citedRate, 0.5, accuracy: 0.001)
    }
}
```

**Step 2: Run it to verify it fails**

Run: `cd mac/Icarus && swift test --filter AskHistoryTests`
Expected: FAIL — `AskHistory` doesn't exist.

**Step 3: Implement**

```swift
import Foundation
import Observation

/// The real, in-session record of questions asked and what the brain returned.
/// Session-scoped (not yet persisted — a later brick), so the UI shows honest
/// empty states rather than seeded history. Powers recent-questions, decision
/// history, unknowns, the proof drawer, and the cited-rate metric.
@MainActor
@Observable
public final class AskHistory {
    public struct Entry: Identifiable, Sendable {
        public let id = UUID()
        public let at: Date
        public let question: String
        public let response: AskResponse
        public var isCited: Bool { response.verdict == .answer && !response.citations.isEmpty }
        public var isUnknown: Bool { response.verdict == .unknown }
    }

    public private(set) var entries: [Entry] = []   // most-recent first
    public init() {}

    public func record(question: String, response: AskResponse) {
        entries.insert(Entry(at: Date(), question: question, response: response), at: 0)
    }

    public var unknowns: [Entry] { entries.filter(\.isUnknown) }
    public var mostRecent: Entry? { entries.first }

    /// Fraction of answered (non-unknown) asks that carried a citation. `nil`
    /// until at least one ask — so the UI never shows a fabricated percentage.
    public var citedRate: Double? {
        guard !entries.isEmpty else { return nil }
        let cited = entries.filter(\.isCited).count
        return Double(cited) / Double(entries.count)
    }
}
```

**Step 4: Run to verify pass**

Run: `cd mac/Icarus && swift test --filter AskHistoryTests`
Expected: PASS.

**Step 5: Commit**

```bash
git add mac/Icarus/Sources/IcarusKit/AskHistory.swift mac/Icarus/Tests/IcarusKitTests/AskHistoryTests.swift
git commit -m "feat(mac): AskHistory — real in-session ask record (honest, no seeded data)"
```

---

### Task 2: Decode real index counts from `/status`

**Why:** The metrics card needs real numbers. [Models.swift:32](../../mac/Icarus/Sources/IcarusKit/Models.swift) currently drops `counts` (comment says it's ignored). Decode it so "PRs indexed" is true.

**Files:**
- Modify: `mac/Icarus/Sources/IcarusKit/Models.swift`
- Test: `mac/Icarus/Tests/IcarusKitTests/ModelsTests.swift`

**Step 1: Write the failing test** (add to `ModelsTests`)

```swift
func testDecodesIndexCounts() throws {
    let json = #"{"state":"ready","repo":"simonw/llm","commit":"abc","counts":{"pr":141,"issue":84,"code":18},"error":null}"#
    let s = try JSONDecoder().decode(RepoStatus.self, from: Data(json.utf8))
    XCTAssertEqual(s.counts?.pr, 141)
    XCTAssertEqual(s.counts?.code, 18)
}

func testMissingCountsIsNil() throws {
    let json = #"{"state":"indexing","repo":"o/r","commit":"","error":null}"#
    let s = try JSONDecoder().decode(RepoStatus.self, from: Data(json.utf8))
    XCTAssertNil(s.counts)
}
```

**Step 2: Run** → FAIL (`counts` undefined on `RepoStatus`).

**Step 3: Implement** — add to `Models.swift`:

```swift
public struct IndexCounts: Decodable, Sendable {
    public let pr: Int
    public let issue: Int
    public let code: Int
}
```

and add `public let counts: IndexCounts?` to `RepoStatus` (optional, so an
`indexing` status with no counts still decodes).

**Step 4: Run** → PASS. Also run the whole suite: `swift test` (existing status
tests must stay green — `counts` optional is backward-compatible).

**Step 5: Commit**

```bash
git add mac/Icarus/Sources/IcarusKit/Models.swift mac/Icarus/Tests/IcarusKitTests/ModelsTests.swift
git commit -m "feat(mac): decode real /status index counts for the metrics card"
```

---

### Task 3: Append every real ask to history

**Files:**
- Modify: `mac/Icarus/Sources/Icarus/AskModel.swift` (call a sink on each result)
- Test: covered via OverlayController wiring (manual) + AskHistory unit tests.

**Step 1:** Give `AskModel` an optional history sink it appends to on `.response`:

```swift
var history: AskHistory?
```
and in `submit()`, after setting `state = .response(...)` on success:
```swift
if case .response(let r) = state { history?.record(question: trimmed, response: r) }
```
Keep `onResult` as-is (speech still fires from it).

**Step 2:** Build: `swift build` — expected clean.

**Step 3: Commit**

```bash
git add mac/Icarus/Sources/Icarus/AskModel.swift
git commit -m "feat(mac): record each real ask into AskHistory"
```

---

## Phase B — Shell chrome

### Task 4: Nav model + `ShellView` scaffold

**Files:**
- Create: `mac/Icarus/Sources/Icarus/Shell/ShellNav.swift` (enum of surfaces)
- Create: `mac/Icarus/Sources/Icarus/Shell/ShellView.swift` (HStack: Sidebar + content router)
- Test: `mac/Icarus/Tests/IcarusKitTests/` — the enum's title/order is pure; if
  `ShellNav` lives in IcarusKit it's unit-testable. **Decision:** put `ShellNav`
  in `IcarusKit` so its titles/cases are tested; keep the `View`s in the app target.

**Step 1: Write the failing test** (`ShellNavTests` in IcarusKit)

```swift
func testSurfaceOrderAndTitles() {
    XCTAssertEqual(ShellSurface.allCases.map(\.title),
        ["Home", "Ask by voice", "Decision history", "Unknowns", "Privacy boundary"])
}
```

**Step 2: Run** → FAIL.

**Step 3: Implement** `ShellSurface` in `IcarusKit/ShellNav.swift`:

```swift
public enum ShellSurface: String, CaseIterable, Sendable, Identifiable {
    case home, askByVoice, decisionHistory, unknowns, privacyBoundary
    public var id: String { rawValue }
    public var title: String {
        switch self {
        case .home: "Home"; case .askByVoice: "Ask by voice"
        case .decisionHistory: "Decision history"; case .unknowns: "Unknowns"
        case .privacyBoundary: "Privacy boundary"
        }
    }
}
```

Then `ShellView` (app target) — scaffold only in this task:

```swift
struct ShellView: View {
    @State private var surface: ShellSurface = .home
    let auth: AuthModel; let connect: ConnectModel; let ask: AskModel
    let history: AskHistory; let status: StatusModel   // StatusModel from Task 7

    var body: some View {
        HStack(spacing: 0) {
            SidebarView(surface: $surface, status: status)   // Task 5
            Divider()
            ContentRouter(surface: surface, auth: auth, connect: connect,
                          ask: ask, history: history, status: status)  // Tasks 7-11
        }
        .background(Theme.surface)
        .frame(minWidth: 1100, minHeight: 720)
    }
}
```

**Step 4: Run** `swift test --filter ShellNav` → PASS; `swift build` → clean (stub
the not-yet-built subviews with `Text("todo")` so it compiles).

**Step 5: Commit**

```bash
git add mac/Icarus/Sources/IcarusKit/ShellNav.swift mac/Icarus/Sources/Icarus/Shell/ShellView.swift mac/Icarus/Tests/IcarusKitTests/ShellNavTests.swift
git commit -m "feat(mac): shell nav model + ShellView scaffold"
```

---

### Task 5: Sidebar (real repo footer)

**Files:** Create `mac/Icarus/Sources/Icarus/Shell/SidebarView.swift`.

Build to match nodes `5:12`–`5:40`: traffic dots (decorative), the Icarus mark
(reuse `IconArt`), wordmark, the five nav rows (active = filled dot + ink text,
inactive = muted), and the bottom "COMPANY BRAIN" block. **The footer shows the
real connected repo** from `status` (e.g. `simonw/llm`), not "Acme private cloud",
and "Zero training on code" (a true claim). Nav selection drives the `@Binding`.

Use `Theme.ink/muted/border/surface`, `Theme.mono` for the COMPANY BRAIN label.
No test (pure view); verified by build + manual.

**Commit:** `feat(mac): shell sidebar with real connected-repo footer`

---

### Task 6: `MainWindowController` + AppDelegate wiring

**Files:**
- Create: `mac/Icarus/Sources/Icarus/Shell/MainWindowController.swift`
- Modify: `mac/Icarus/Sources/Icarus/AppDelegate.swift`

Replace the onboarding window as the primary surface: `MainWindowController` hosts
`ShellView` in a titled, resizable `NSWindow` (hidden title bar to match the mock's
custom traffic-dot header is optional; simplest is a standard window first). Wire
the shared `auth`, `connect`, `ask` (now carrying `history`), a new `AskHistory`,
and `StatusModel`. Keep the ⌘⇧Space overlay and push-to-talk exactly as-is.

`OnboardingWindowController` is retained only if Home's gate reuses its views;
otherwise fold sign-in/connect into the Home surface (Task 7) and remove the
separate onboarding window in a later cleanup (don't delete files you didn't
create without confirming — leave it unused and note it).

Build + manual launch: `./scripts/bundle.sh` then run the inner binary with
`ICARUS_GH_CLIENT_ID=…`. Expected: the shell window opens with the sidebar.

**Commit:** `feat(mac): main window hosts the shell; overlay/PTT unchanged`

---

## Phase C — Surfaces wired to real data

### Task 7: Home surface + `StatusModel` (metrics/hero/recent/proof, all real)

**Files:**
- Create: `mac/Icarus/Sources/Icarus/Shell/StatusModel.swift` (polls `/status`)
- Create: `mac/Icarus/Sources/Icarus/Shell/HomeView.swift`
- Test: `StatusModel`'s reducer logic if extracted; otherwise manual.

`StatusModel` (`@MainActor @Observable`) periodically calls `BrainClient.status()`
and publishes `repo`, `state`, and `counts`. Home composes:
- **Welcome** (`5:41/42`): "Welcome back, Alankrit" — the name is fine (it's you).
- **Hero card** (`5:47`, black `Theme.ink`): copy is **"Hold ⌥ (Right Option) to
  ask Icarus"** — the real push-to-talk trigger, NOT ⌘⇧Space (the mock is wrong).
  Mention ⌘⇧I opens the typed overlay. The **Try a question** button opens the ask
  overlay. Keep the "never always-listening" pill (true). Evidence stripes are pure
  decoration — fine (no data claim).
- **Metrics card** (`5:59`): from `StatusModel.counts` → "{pr} PRs indexed",
  "{code} code files", and from `history.citedRate` → "{n}% answers cited **this
  session**" (label says session; shows "—" until the first ask), and "0 trained on
  code" (true constant). **Never 14.2K/98%.**
- **Recent questions** (`5:66`): first ~4 of `history.entries`, real time/question/
  evidence + `cited`/`unknown` pill (`Theme.cited/unknown`). **Empty state** when
  history is empty: "No questions yet this session — press ⌘⇧Space to ask."
- **Proof drawer** (`5:94`): `history.mostRecent` → spoken answer (real answer text),
  receipts (real `CitationChip`s), or the honest-unknown card with the real
  `searched` refs. Empty state before any ask.

Gate: if `!auth.isSignedIn || !connect.isReady`, Home shows the sign-in/connect
flow (reuse `OnboardingView`'s controls) instead of the hero — so setup lives in
the shell.

Build + manual. **Commit:** `feat(mac): Home surface — real metrics, recent, proof drawer`

---

### Task 8: Decision history surface

Create `Shell/DecisionHistoryView.swift`: the full `history.entries` as rows
(reuse the recent-question row from Home — extract a `HistoryRow` view to stay
DRY). Empty state when none. Clicking a row selects it into the proof drawer
(optional; can defer). **Commit:** `feat(mac): Decision history surface (real session history)`

---

### Task 9: Unknowns surface

Create `Shell/UnknownsView.swift`: `history.unknowns` rendered with the honest
"No one wrote this down" treatment (`Theme.unknown`). Empty state: "No unknowns
yet — Icarus will list here every question the record couldn't answer." This is a
hero surface for the product's honesty; keep it dignified, not an error.
**Commit:** `feat(mac): Unknowns surface (real abstentions)`

---

### Task 10: Privacy boundary surface (honest static content)

Create `Shell/PrivacyBoundaryView.swift`: a real, plain-language explainer of the
actual privacy model — **on-device voice** (`requiresOnDeviceRecognition`, audio
never leaves the Mac), **public repos only** on free models, **never trained on
your code**, **cite-or-unknown**. Every line must be literally true of the current
build (cross-check against the code). No fake tenant, no fake compliance badges.
**Commit:** `feat(mac): Privacy boundary surface (true privacy claims only)`

---

### Task 11: Ask-by-voice surface + voice overlay state

Create `Shell/AskByVoiceView.swift`: the ask composer (text field + Ask button,
reuse `AskModel`) plus voice affordance (hold ⌥, driven by existing `VoiceModel`),
and render the live `partialTranscript`. Style the bottom **voice overlay state**
(`5:114`): "ICARUS IS ANSWERING" + the mark bars + answer text — reuse the existing
overlay/`Speaker`; this surface just mirrors it inside the window.
**Commit:** `feat(mac): Ask-by-voice surface + voice overlay state`

---

## Phase D — Honesty pass, build, and verify

### Task 12: Empty-state + honest-data audit

Grep the new views for any hardcoded numbers, question strings, repo names, or ref
tokens and confirm each is bound to real data or is a true constant. Concretely:
`grep -rnE "14\.2K|98%|Acme|marina|MSW|legacy (billing|adapter)|incident-" mac/Icarus/Sources` → must return **nothing**. Confirm every surface has an honest
empty state. **Commit:** `chore(mac): honest-data audit — no fabricated values in the shell`

### Task 13: Build, test, regenerate the index, manual run

- `cd mac/Icarus && swift build && swift test` — all green (IcarusKit logic tests
  incl. `AskHistory`, `ShellNav`, `Models` counts).
- Regenerate `general_index.md`/`detailed_index.md` (new files added) per CLAUDE.md.
- Manual: start the brain **with keys**
  (`GROQ_API_KEY=… GEMINI_API_KEY=… python3 -m demo.server`), `./scripts/bundle.sh`,
  launch with `ICARUS_GH_CLIENT_ID=…`, then: sign in → connect `simonw/llm` → ask
  the known cited question → confirm it appears in Recent + Proof drawer with the
  real `pr:1435` receipt → ask an unanswerable one → confirm it lands in Unknowns.
- Update `docs/HANDOFF.md` (U1-B done; note session-scoped history + deferred
  persistence).

**Commit:** `docs(mac): refresh index + HANDOFF for the full app shell`

---

## Definition of done

- The five-surface windowed shell matches the Figma **look** (sidebar, hero,
  metrics, recent, proof drawer, voice state) using `Theme` tokens.
- **Every displayed value is real or a true constant** — verified by the Task 12
  grep returning nothing and by the manual run showing a real ask flow through
  Recent → Proof drawer → Unknowns.
- Honest empty states everywhere; no seeded history, no invented metrics.
- `swift build && swift test` green; the ⌘⇧Space overlay and push-to-talk still work.
- HANDOFF + index updated.

## Deferred (call out, don't fake)

- **Persistent history** across launches (session-scoped for now).
- **Real fonts** (Geist / JetBrains Mono) — still SF stand-ins.
- **Custom traffic-dot title bar** — standard window first; chrome polish later.
- Metrics beyond index counts + session cited-rate (org-wide numbers need the
  cloud + real tenants).

---

## Execution note

Phases A→B→C→D are ordered so the app compiles and runs after each phase. If time
is short, Phase A + Task 7 (Home) alone gives a real, demoable single-screen shell;
the other surfaces are additive.
