# Funder proposal — OYDP (Own Your Dream Property)

**Draft packet. 4 November 2026. Pre-alpha.**

Evidence point: commit `95fce64798e7108cc4cf0b346f9f3e4a8df984ba` on pull request [6](https://github.com/Manasvi-1/OYDP/pull/6) in `Manasvi-1/OYDP`. This file is a discussion draft. It does not state a round size, a company valuation, or a return. It is not an offer of securities.

## How to read this packet

Three rules control every sentence below.

1. **Document 1 controls product scope.** The uploaded master blueprint (OYDP-MASTER-001, dated 31 October 2026 in that file) names the problem, the thirteen engines, the launch geography, and one national market story. It is a research and design document. It is not built software and it is not permission to collect portal data.
2. **The repository controls what is built.** A route, a migration, a test, or a screen counts only when it is in this repository and its limits are stated. Passing tests are evidence about that test run. They are not production security and not an independent audit.
3. **Documents 2–7 are not an implementation.** Documents 2, 3, 4, and 7 are generated sketches. Documents 5 and 6 are the same code dump twice. They include mock intelligence, sample coordinates, and example secrets. They do not replace Document 1 or the repository. Their regional arithmetic is recorded in the market section and is not a forecast.

Geography in this packet means Bengaluru Urban, Bengaluru Rural, other Karnataka districts, and Hyderabad. Each place has its own records, authorities, and data limits. A feature allowed for one place is not assumed for another.

The intended shape is one modular application: a Next.js workspace, a FastAPI service, and PostgreSQL with PostGIS. Thirteen separately deployed services, a graph database, an API gateway, and worker fleets appear in the sketches. They are not the launch shape.

Deterministic code decides authorization, money, policy, validation, and critical state changes. Model output may explain a source it can cite. It must abstain when it cannot. It must not grant access, set a price, move money, or mark a claim verified.

## 1. Problem

Document 1 describes property work in these regions as split across paper, portals, advisers, listings, and spreadsheets. A buyer, a lawyer, a broker, or a lender often cannot see who asserted a fact, which record it came from, or who is still allowed to read it.

The named public systems in Document 1 are Kaveri, e-Aasthi, e-Swathu, Bhoomi, Dharani / Bhu Bharati, TS RERA, and TS-bPASS, plus municipal and planning bodies such as BBMP, BDA, BMRDA, GHMC, and HMDA. Naming them states the problem. It does not mean OYDP reads them, stores them, or speaks for them.

OYDP's proposed response is a private workspace for one property at a time: a record the creator can share for a limited time, a claim that stays attributed and unverified, and a later path for documents and professional review once rights and security gates pass. The product does not replace a sub-registrar, a licensed advocate, a valuer, or a planning authority.

This problem statement is Document 1's account. This review did not independently measure how often titles fail, how long diligence takes, or what people pay today.

## 2. Who might pay

Nobody is paying. No price has been tested. The files contain hypotheses and conflicting numbers. Treat every rupee figure in this section as a prompt for a pilot question, not as a price list.

Three payment hypotheses are worth testing, in this order, because they match the engines that could exist first:

| Hypothesis | Job a payer might buy | Prices written in the files | What would count as evidence |
| --- | --- | --- | --- |
| Professional workspace | A lawyer, broker, or architect keeps a private matter, invites a colleague, and exports only what the client allowed. | Document 1: ₹999–₹4,999 per month. Documents 5 and 6: ₹1,999 per month. | A named practice completes a consented pilot and states a price it would pay. |
| Consumer report | A buyer pays for a sourced pack of what the workspace holds and what it refuses to conclude. | Document 1: ₹999–₹4,999 per report. Documents 5 and 6: ₹999. | A buyer pays after reading a specimen that still says "unverified". |
| Institutional read | A bank, NBFC, or developer receives a revocable, audited read of fields the owner allowed. | Document 1: ₹50,000–₹5,00,000 per month. Documents 5 and 6: ₹50,000 per month, plus a separate developer seat at ₹9,999 per month. | A partner accepts a written scope that is not a title certificate and not a risk score. |

Document 1 also lists academy courses at ₹5,000–₹15,000. Engine 06 is not built. Course fees are not a current revenue line. Certificates, if they are ever issued, stay non-accredited.

Free search is also written in Document 1. It is not built, and it must not be used to collect portal records ahead of the rights gate.

## 3. What exists today, with evidence

The product is pre-alpha. The active service is `apps/api` on the public schema, with string identity subjects and configured token verification. A separate tree, `oydp/` and `migrations/`, remains from pull request 1. It is a reference backend with a different schema and subject type. The two are not interchangeable and their data is not synchronized.

### Cited test run

The verification register records this run for commit `68f2875c85e4d4fb371c554664a11b9de132cf1f`, which is an ancestor of the evidence point above. It does not, by itself, cover the later workspace commit.

| Check | Recorded result | Where |
| --- | --- | --- |
| Active API and PostgreSQL | 115 passed, zero skipped | [run 40203433997](https://github.com/Manasvi-1/OYDP/actions/runs/40203433997) |
| Reference PostGIS backend | 87 passed and 13 subtests, zero skipped | [run 40203430633](https://github.com/Manasvi-1/OYDP/actions/runs/40203430633) |
| OpenAPI, compile, and dependency audit | Passed; no known dependency vulnerabilities reported in that audit | [run 40203434051](https://github.com/Manasvi-1/OYDP/actions/runs/40203434051) |

That slice, API 0.4.0, provides:

- Private property records. A caller sees a property only as creator or while a grant is current.
- Paginated discovery. Pages do not reveal a count of records the caller cannot see.
- Unverified claims. The server fixes the claim kind and the status `unverified`. A client cannot send a field that marks a claim official. Statements are stored as text.
- Expiring read grants. The creator can grant and revoke. Expiry is enforced in the database. A read grant does not allow a claim to be written.
- Tenant isolation. Membership comes from the database. Forced row-level security applies to tenant tables. Cross-tenant denials are part of the tested set.
- Token checks for signature, issuer, audience, and expiry, plus an MFA method asserted on the token for privileged writes. A live identity provider for a deployed environment is not enrolled.
- An audit row written in the same transaction as the change it describes. An independent audit store, outside the application database, is not built.

### Present in the evidence-point commit, without that CI citation

Commit `95fce64` adds the first Next.js workspace (`apps/web`) and the notes in `docs/implementation/WEB_WORKSPACE.md` and `docs/implementation/LAUNCH_1_DROP_1.md`. Those notes describe label and jurisdiction correction with history, and an owner-delegated write grant of at most 30 days. The engineering roadmap still lists correction and write delegation as open. This packet does not treat them as closed by the 115-test run.

The workspace can list private properties, create a record, open one record, append an unverified claim, and grant or revoke expiring read or write access. It keeps the access token in an httpOnly cookie. It rejects non-local `http` API bases. `docs/implementation/WEB_WORKSPACE.md` says `npm test` covers session, query, and sign-in URL construction. This packet does not cite a passing browser end-to-end run. The GitHub workflow named `web workspace` is the intended check. A green unit run would still not be a full browser journey.

A localhost Keycloak realm is documented for one computer, bound to loopback, with HTTP allowed only in that local setup. That is a development identity provider. It is not live enrollment for any other environment, and it is not production authentication.

## 4. What is not built

- A live identity-provider enrollment, session refresh, and session revocation outside the local development realm.
- Browser end-to-end tests of the property journey.
- Document upload, quarantine, malware scanning, encryption, and authorized download.
- Deletion, export, retention, and legal hold that a privacy review would accept.
- An independent audit sink that an ordinary administrator cannot rewrite.
- Property deduplication, official observations, and any path that could be read as title.
- Engines 02 through 13, listed in the next section.
- A sourced map layer, a valuation, a layout, a feasibility model, a marketplace, or a partner API.
- Staging or production deployment, backups that have been restored, alerts, and a measured capacity.
- A price, a contract, a support offer, and a paid pilot.
- Qualified legal sign-off on data rights.
- An independent security assessment.

General availability, as written in the repository roadmap, still requires thirteen real engine journeys, legal and data-rights approval, external security review, privacy tests, checks of any AI or calculator, recovery drills, a paid pilot, and a signed release decision. None of those boxes is checked.

## 5. Thirteen-engine boundary

All thirteen engines remain bounded future commitments. "Partial" means only the behavior named in section 3. "Not built" means there is no engine workflow to demonstrate. Each engine keeps a refusal rule so a later build cannot silently overclaim.

| ID | Engine | State | Refusal rule that stays in force |
| --- | --- | --- | --- |
| E01 | Property Identity and Evidence Graph | Partial | A user claim stays unverified. The product does not certify ownership or encumbrance. |
| E02 | AI Property Advisor | Not built | Answers cite a source or abstain. No legal advice. No title opinion. The model does not change permissions. |
| E03 | Transaction and Legal Workspace | Not built | No invited matter, offer, or lawyer opinion until access and audit exist for that matter. |
| E04 | Living Property Passport | Not built | No lifetime vault and no export until consent, retention, and deletion exist. |
| E05 | Ownership Action Engine | Not built | Reminders are tasks, not a determination that a filing is legally required. |
| E06 | Real Estate Academy | Not built | Completion certificates, if issued, are non-accredited. |
| E07 | SpatialLedger GIS Intelligence | Not built | No layer is shown until its source, date, and accuracy limit can be shown with it. |
| E08 | Valuation and Market Intelligence | Not built | A range must reproduce from stored inputs. Asking prices stay separate from completed sales. No guaranteed value. |
| E09 | Layout and Architecture Concept Studio | Not built | Concepts only, labeled as requiring a licensed architect. No approval is implied. |
| E10 | Development and Business Feasibility | Not built | Inputs and formulas must reproduce. No promised return, IRR, or project approval. |
| E11 | Marketplace and Professional Network | Not built | No listing without consent, review, expiry, and moderation. |
| E12 | Time-Versioned Spatial Digital Twin | Not built | Geometry is dated. History is not a current legal boundary. |
| E13 | Institutional API and Evidence Attestations | Not built | Partner credentials are revocable and read-only. An attestation is not a government certificate. |

Shared rules already intended for every engine: server-side authorization, tenant isolation, and no decision by a model on money or access. Document 1's diagrams that show a marketplace returning an "evidence graph and risk score" describe a future flow. That flow is not implemented, and a risk score is not an allowed output of the current system.

## 6. Rights and security gaps

### Rights

No qualified opinion has been obtained. Until it is, source-dependent features stay off. An open website is not a license to copy, store, or resell records.

Document 1's competitive note says the product would rely on public scraping, user uploads, and professional partnerships. Scraping is not authorized by this packet. It waits on a qualified rights review of each named source. User uploads wait on the document gate. Partnerships wait on a contract and consent.

Document 1 also names the Digital Personal Data Protection Act, 2023, and the National Geospatial Policy, 2022. Those are topics for counsel. They are not implemented controls. Consent, purpose limitation, erasure, and map-resolution limits are open questions in section 12.

The repository does not grant an open-source license. Copyright decisions are not finalized. A funder data room needs the owner's permission. Third-party dependency licenses stay with those dependencies.

### Security that the tested slice actually exercises

The threat model in `docs/THREAT_MODEL.md` is an engineering draft, not an independent assessment. Within the API slice, the repository implements and tests:

- Verification of configured RS256 tokens, rather than a caller-supplied identity.
- Membership and grants read from the database on the request, including revocation and expiry.
- Forced row-level security and a runtime role that is not the table owner.
- Privileged claim and sharing routes that require an MFA method on the token.
- Claim text that cannot be upgraded to an official status by the client.
- Audit and business changes that commit or roll back together. A failed commit is not reported as success.

### Security that is still open

- Live identity-provider enrollment, MFA freshness against the provider, and production token configuration.
- Browser end-to-end coverage.
- Quarantine, scanning, encryption, and fail-closed download. There is no document service. Real customer files must not be uploaded.
- An audit trail that survives a privileged administrator of the application database.
- Privacy export, deletion, and retention tests.
- Rate limits, a deployed web application firewall, and hosted key management. Document 1 lists these as target controls. They are not evidence of a deployed system.
- Dependency scanning in CI is not a penetration test. The October audit reported no known vulnerabilities in that run. That statement expires as dependencies change, and it does not cover the later workspace commit.
- The local identity provider listens on loopback and allows HTTP there. The launch notes say not to expose it. An administrator of that computer can still read an unencrypted disk.

No sentence in a deck may convert this list into "production-secure" or "independently audited".

## 7. Pilot design

The pilot is not started. When it starts, it is called a pilot.

**Who.** Three named professional practices, chosen with counsel, working on matters they already handle in Bengaluru Urban, Bengaluru Rural, another Karnataka district, or Hyderabad. Three is a planning choice so support load can be counted. It is not a market sample.

**What they use.** The private property workspace only: create a record, record an unverified claim, and share an expiring read. They use synthetic files or records the practice already has the right to process. They do not upload client documents until gate 2 has passed on synthetic files and counsel has accepted the pilot terms.

**What is measured.** Whether the practice finishes one matter in the workspace. How many support contacts that matter required. Whether the practice will pay, for which job, and at what price. The answer is a data point. It is not a forecast and it does not validate either market story.

**What they are told in writing.** OYDP does not verify title. It is not a government service. It does not guarantee value or approval. Claims remain unverified. Access expires. The pilot can be stopped and the pilot records deleted. Notes are kept only with consent.

**What the pilot is not.** It is not a public launch, a listing site, an official portal connection, a valuation product, or a security approval. Publishing a pilot logo next to a government name is not allowed.

## 8. Use of funds, by gate

This packet does not ask for a stated amount. The files do not justify a round size. Any later amount is a separate decision. Money, if raised, is released when the gate's evidence exists. A calendar month does not release it. A failed gate stops the later gates that depend on it.

| Gate | Money may pay for | Release evidence | Money may not be released for |
| --- | --- | --- | --- |
| 0. Rights | A qualified review, a source register, and pilot terms. | A written opinion that names each source the pilot may touch, the permitted use, and the uses that stay forbidden. | Portal collection, scraping, purchase of bulk records, or redistribution. |
| 1. Private journey | Live sign-in for the pilot environment, correction and audit work still open on the roadmap, and hardening of the existing property workspace. | A current-head test run for the enrolled provider and the private journey, including expired tokens, wrong tenants, and revoked grants. Browser coverage of that journey, or a written statement that browser coverage is still open. | Any claim that ownership is certified. Any production launch. |
| 2. Documents | Quarantine, scanning, encryption, and downloads that fail closed, exercised on synthetic files. | Tests that a failed scan cannot be downloaded, a cross-tenant identifier cannot fetch the file, and an unscanned file is never served. | Customer or client documents before this gate passes. |
| 3. Design partners | The three consented pilots in section 7, including support time. | Consent forms, a support log, and a recorded willingness-to-pay note for each practice. | Advertising a public launch or a government integration. Paying for portal data. |
| 4. External review | An external retest of only the pilot that is actually exposed. | The reviewer's report, the scope they were given, and the unresolved findings. | Describing automated tests, or this review, as a security approval of the whole product. |

Gates 2 and 3 do not start ahead of gate 0. Gate 4 covers the system the partners used, not engines that were not in the pilot.

Staff, counsel, and a reviewer are the expected costs. This draft does not convert those words into a budget, a valuation, or a return.

## 9. Market figures

Both stories below are **unsourced assumptions**. They are not forecasts, not facts, and not a basis for a round. The inputs are not cited to a published dataset, a date, or a method note that a reviewer can check. Penetration rates are choices inside the documents. They are not evidence of future customers.

### Document 1 — national story

Document 1, section 6.1, base year 2026, says the figures are a bottom-up software and report model, not gross property value. It then states:

| Line as written | Product as written | Stated result |
| --- | --- | --- |
| Professional software | 500,000 brokers and lawyers × ₹10,000 per year | ₹5,000 Cr |
| Institutional APIs | 5,000 banks and NBFCs × ₹5,00,000 per year | ₹250 Cr |
| Consumer reports | 5 million national transactions × ₹1,000 | ₹500 Cr |
| Total, labeled TAM |  | about ₹5,750 Cr (about $690 million in that document) |
| Karnataka and Telangana, labeled SAM | about 15% of the national total | about ₹860 Cr (about $103 million) |
| Year 3, labeled SOM | 5% of that SAM | ₹43 Cr (about $5.1 million) of annual recurring revenue |

The dollar figures do not state an exchange rate or a date.

**Arithmetic check, not a replacement market.** One crore is ₹1,00,00,000. The professional product as multiplied is 500,000 × ₹10,000 = ₹500 crore, not ₹5,000 crore. The institutional product is ₹250 crore and matches the stated line. The consumer product is ₹500 crore and matches the stated line. The stated total of about ₹5,750 crore uses the ₹5,000 crore professional line. The three products, multiplied in rupees, sum to ₹1,250 crore. The SAM and the ₹43 crore year-3 story are percentages of the stated total, so they inherit the break. This packet does not adopt ₹1,250 crore, ₹5,750 crore, or ₹43 crore as a market. It records that Document 1's own lines do not agree.

Document 1's population (500,000 professionals, 5,000 institutions, 5 million national transactions) is not the population in Documents 5 and 6. The two stories must not be added together or presented as one market.

### Documents 5 and 6 — regional arithmetic

The duplicated sketch contains a function aimed at Bengaluru Urban, Bengaluru Rural, the rest of Karnataka, and Hyderabad. A comment says the inputs follow "Sub-Registrar and RERA public data trends". No table, year, or publication is cited. The comment is not a source.

| Input in the sketch | Value used |
| --- | --- |
| Transactions, Bengaluru | 250,000 |
| Transactions, Hyderabad | 180,000 |
| Transactions, rest of Karnataka | 300,000 |
| Regional transactions | 730,000 |
| Consumer report price | ₹999 |
| Professional price | ₹1,999 per month |
| Professionals | 40,000 brokers + 10,000 lawyers = 50,000 |
| Developer price | ₹9,999 per month |
| Developer organizations | 3,000 |
| Institutional price | ₹50,000 per month |
| Institutions | 500 |
| Year-3 penetration | 5% of transactions, 10% of professionals, 15% of developers, 20% of institutions |

Multiplying those inputs and rounding to crore at two decimals, as the sketch does:

| Line | Full-population product | Year-3 product at the stated penetration |
| --- | --- | --- |
| Consumer reports | ₹72.93 Cr | ₹3.65 Cr |
| Professional seats | ₹119.94 Cr | ₹11.99 Cr |
| Developer seats | ₹36.00 Cr | ₹5.40 Cr |
| Institutional reads | ₹30.00 Cr | ₹6.00 Cr |
| Total | **₹258.86 Cr** | **₹27.04 Cr** |

₹258.86 crore is the sketch's regional total if every listed transaction bought a report and every listed professional, developer, and institution bought a seat. ₹27.04 crore is the same total after the penetration rates above. Neither number is revenue. Neither number is a forecast. Neither number is the national market. The prices also disagree with Document 1's ranges.

### Prohibition

A deck, a model, or a spoken answer may quote these figures only with the source, the arithmetic check, and this sentence: **these are unsourced assumptions, not a forecast and not a fact.** They may not appear in a headline, a use-of-funds slide, or a valuation. This packet invents no round size, no valuation, and no return.

## 10. Sentences the deck must not use

Do not use these, including softened versions that keep the same meaning.

1. OYDP verifies title, certifies ownership, clears encumbrance, or eliminates fraud.
2. OYDP is a government service, or is integrated with Kaveri, e-Aasthi, e-Swathu, Bhoomi, Dharani, Bhu Bharati, RERA, TS-bPASS, BBMP, BDA, BMRDA, GHMC, or HMDA.
3. OYDP guarantees a valuation, an investment return, a feasibility result, or an architectural or planning approval.
4. OYDP is production-secure, bank-grade, or independently audited because automated tests passed.
5. The thirteen engines are built, live, or available to a customer.
6. Documents 2–7 are the codebase, a completed build, or evidence of deployed infrastructure.
7. Sample Bengaluru or Hyderabad coordinates, seed data, or mock document text are a data partnership.
8. ₹5,750 crore, ₹860 crore, or ₹43 crore is the market or the year-3 revenue.
9. ₹258.86 crore or ₹27.04 crore is the market or the year-3 revenue.
10. Any round size, pre-money valuation, ownership percentage, or investor return.
11. Scraping public portals is an approved collection method.
12. The model decides who may read a record, what a fee is, or whether a claim is verified.
13. A risk score, a cryptographic attestation, or a zero-knowledge proof is a current product. Those appear in the sketches only.
14. The local Keycloak realm, or a pasted access token, means live identity is finished.
15. A pilot is a launch.

Document 1's closing language — a paradigm shift, a defensible moat, and significant market share — is not for the deck. The competitive table in Document 1 says OYDP provides verified evidence graphs and is deeply integrated with Indian GIS and local property law. Those sentences describe unbuilt engines.

## 11. Data-room list

Include:

- Document 1, the controlling blueprint, marked "scope, not implementation".
- This proposal.
- The source comparison dated 4 November 2026, which records why Documents 2–7 are non-binding.
- `README.md`, `docs/ROADMAP.md`, `docs/ENGINE_REGISTER.md`, `docs/implementation/WEB_WORKSPACE.md`, `docs/implementation/LAUNCH_1_DROP_1.md`, `docs/implementation/DISCOVERY_CLAIMS.md`, `docs/implementation/VERIFICATION_REGISTER.md`, `docs/implementation/SECURITY_GATES.md`, and `docs/THREAT_MODEL.md`.
- Pull request 6 and the commit named above.
- The three CI run links in section 3, each labeled with the commit they actually ran.
- The open limitation list in section 4 and the counsel questions in section 12.

Archive Documents 2–7 only with a cover note that they are generated sketches, not the build. Remove example passwords, tokens, and cloud credential snippets before anyone outside the repository sees them.

Do not include:

- Customer or client records, real property documents, or personal data.
- Access tokens, private keys, `.env` files, or the generated example password.
- A claim that either market model has been reviewed by a third party. It has not.

## 12. Open questions for counsel

These questions are unanswered. The engineering team should not close them by interpretation.

1. For each named portal and map, may OYDP query, store, display, or redistribute any field? Under what statute, terms, attribution, rate limit, and fee? Which fields are forbidden?
2. Is automated collection of any of those portals lawful for this product? If a source is forbidden, the build does not collect it.
3. Which fields in a property workspace are personal data under the Digital Personal Data Protection Act, 2023? Who is the fiduciary when a professional stores a client's matter? What consent, purpose, retention, and erasure are required before a pilot stores a real record?
4. Which map resolutions and layers does the National Geospatial Policy, 2022, allow here? What must not be shown?
5. Can an unverified claim sit on the same screen as a survey number or a khata identifier without being held out as title? What legend is required?
6. What must a paid diligence pack say, and which conclusions require a licensed advocate, valuer, or architect before they can be sold?
7. May a bank or NBFC be offered any score or attestation before a licensed person signs the underlying opinion?
8. Are non-accredited academy certificates at risk of being read as a professional license?
9. What cross-border rules apply if a processor, model host, or scanner is outside India?
10. What liability cap, title disclaimer, data-return, and deletion clause belong in the three pilot contracts?
11. May this private repository be shown to a funder before the owner decides the license?
12. Which of Document 1's public claims would be unlawful or misleading if repeated in a deck while the repository is in its current state?

## Maturity

This is a pre-alpha private-property slice and a first workspace, plus a written scope for thirteen engines. It is not a launched product, not a government integration, not a title service, and not an independently reviewed system. The next honest step is gate 0.
