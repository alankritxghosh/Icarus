# Chrome Web Store submission — Icarus, Explain This Line

Everything the Developer Dashboard asks for, drafted from what the extension
actually does (read off `extension/`, not imagined). **Nothing here is
submitted.** The account, the fee, the upload and the answers to the privacy
form are yours — they need your Google identity and payment.

Prepared 2026-08-06 for extension version **0.1.2**.

---

## What only you can do

1. **Register a developer account** — <https://chrome.google.com/webstore/devconsole>,
   one-time **$5** fee via Google Payments. Tied to a Google account; pick the
   one you want to own this listing permanently, because moving a published
   listing between accounts is a support request, not a setting.
2. **Upload** `extension/dist/icarus-extension-0.1.2.zip` (built by
   `extension/package.sh`; sha256 `29b1f64d3d1fedd23728b911d3a5a941259087a0049b62ab6765534cea34a525`).
3. **Take one real screenshot** — see "Screenshots" below. This is the one asset
   I could not produce, and it must not be faked.
4. **Publish a privacy policy at a public URL** — draft below; it is a statement
   about your product's behaviour, so read it before it goes up.
5. **Answer the data-use form** — my recommended answers are below; they are
   claims about your practices and you are the one making them.

Review typically takes a few days and can take longer when an extension requests
host permissions, which this one does.

---

## Listing fields

**Name** (45 char limit)
```
Icarus — Explain This Line
```

**Short description** (132 char limit)
```
Ask why any line of code on GitHub is the way it is. Cited answers from your repo's history, or an honest "nobody wrote this down".
```
(131 characters — counted, not estimated. The dashboard rejects an over-long
value outright, so if you edit this, count it again.)

**Category:** Developer Tools
**Language:** English

**Detailed description**
```
Icarus answers questions about a codebase using only what your team actually
wrote down — pull requests, issues, commits, docs and the code itself — and
shows you the receipts.

Select any lines in a file on GitHub and ask what they do, how they are used,
or why they exist. You get an answer with citations you can click through to
the exact evidence it came from.

When nobody ever recorded the reason, Icarus says so. It does not guess, and it
does not fill the gap with a plausible-sounding story. That refusal is enforced
in code, not left to the model's judgement: an answer is only shown if every
citation resolves to evidence that was genuinely retrieved.

Requirements
• A repository you have already connected in Icarus.
• A free GitHub sign-in, from the extension's toolbar button.

The extension is one of several ways to reach Icarus, alongside a macOS app and
an editor integration.

Alpha software. Bugs and rough edges are expected; reports are welcome at
ayushghosh2015@gmail.com.
```

---

## Permission justifications

The dashboard asks for one per permission. Be specific — vague answers are a
common rejection reason.

**`identity`**
```
Used solely to sign the user in with GitHub, via
chrome.identity.launchWebAuthFlow, so the extension can act on repositories
that user has already connected. No identity data is read or stored beyond the
resulting access token.
```

**`storage`**
```
Stores the user's GitHub access token in chrome.storage.local so they are not
asked to sign in on every page. Nothing else is stored.
```

**Host permission — `https://github.com/*`**
```
The extension's entire function is to explain code the user selects on GitHub.
The content script runs only on file pages (github.com/owner/repo/blob/*) and
reads the line range the user selected. It does not read or transmit any other
page.
```

**Host permission — the Icarus brain URL**
```
The selected code location is sent to Icarus's own backend, which returns the
cited answer. This is the only network destination the extension contacts.
```

**Single purpose statement**
```
Explain a selected passage of code on GitHub, using evidence from that
repository's own recorded history.
```

---

## Data-use form — recommended answers

Verify each against `extension/background.js` and `extension/content.js` before
submitting; these are the honest answers as the code stands at 0.1.2.

| Question | Answer |
|---|---|
| Personally identifiable information | **No** |
| Health information | No |
| Financial information | No |
| Authentication information | **Yes** — the GitHub access token |
| Personal communications | No |
| Location | No |
| Web history | No |
| User activity | No |
| Website content | **Yes** — the file path and line range the user selects |

Then the three required certifications, all of which are true as written:
- Data is **not** sold to third parties.
- Data is **not** used for purposes unrelated to the item's single purpose.
- Data is **not** used to determine creditworthiness or for lending.

One nuance worth stating rather than glossing: the selected code is sent to the
Icarus backend, and the backend sends evidence to a third-party model provider
(Google Gemini, on a billing-enabled, non-training tier) to compose the answer.
That is disclosure-worthy and is covered in the privacy policy draft below.

---

## Privacy policy — DRAFT, needs your review

Publish at a stable public URL (e.g. `https://icarus-website-kappa.vercel.app/privacy`)
and paste that URL into the dashboard. **Read this before publishing — it is a
statement about your practices, and I drafted it from the code, not from your
intentions.**

```
Privacy — Icarus, Explain This Line

What the extension sends

When you select lines in a file on GitHub and ask about them, the extension
sends the repository name, the file path, the line range, and your typed
question (if any) to the Icarus backend. It also sends your GitHub access token
so the backend can confirm you have access to that repository.

The extension does not read pages you have not asked it about. It runs only on
GitHub file pages, and only acts when you select lines and click Ask.

What is stored

Your GitHub access token is stored locally in your browser (chrome.storage.local)
so you are not asked to sign in repeatedly. Removing the extension removes it.

The Icarus backend keeps an index of repositories you have connected, and a
record of the questions asked against each repository, together with whether
Icarus answered or declined. It does not record who asked.

What leaves the backend

To compose an answer, the backend sends the retrieved evidence to a third-party
language model provider (Google, on a billing-enabled tier that does not train
on submitted content). Your code is not used to train any model, and is
discarded after the request.

What is never done

Your code is not sold or shared with anyone else. Data from one organisation is
never pooled with another's.

Deleting your data

Disconnecting a repository in Icarus deletes that repository's index from the
backend. Questions: ayushghosh2015@gmail.com.
```

---

## Screenshots — the one thing I could not produce

The store requires at least one screenshot at **1280×800** or **640×400**.

`site/shots/panel_cited.png` (828×872) and `panel_refusal.png` (828×488) are the
wrong size **and the wrong subject** — they show the macOS app's panel, not the
extension. Using them here would misrepresent what the user is installing, which
is exactly the kind of thing the honesty gate exists to prevent elsewhere in this
product. Don't.

Take a real one:

1. Load the unpacked extension (`chrome://extensions` → Developer mode → Load
   unpacked → `extension/`).
2. Connect a public repo in Icarus, sign in via the extension's toolbar button.
3. Open a file on GitHub, select a few lines, click **Ask Icarus**, and let a
   cited answer render.
4. Capture at 1280×800. A second shot of the honest-unknown state is worth
   including — it is the product's actual differentiator.

---

## After it is published

The extension ID changes when the store assigns one, which is fine: the backend
validates the OAuth redirect by *pattern*
(`https://<32 chars>.chromiumapp.org/`, see `demo/github_oauth.py`), not against
a fixed ID, so sign-in keeps working without a server change.

Two follow-ups worth doing once the listing exists:

- Replace the side-load section on the website with the store link. Until then
  both paths coexist and the two installs are different extension IDs.
- Store uploads still need a version bump each time. `extension/package.sh` is
  the only step; the zip it produces is exactly what the dashboard wants.
