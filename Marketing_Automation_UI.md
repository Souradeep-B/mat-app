# Marketing Automation UI Design

## Purpose

Defines the layout, components and behaviour of each page in the Streamlit app (`app.py`).
This file is referenced only when working on UI changes — never during audience query building.

**App file:** `C:\Users\souradeep.bhattachar\Documents\Claude\Audience Builder\app.py`
**Run command:** `streamlit run app.py` → opens at `http://localhost:8501`

---

## Global Sidebar — API Status & Toggle

### Purpose
Provides a persistent, always-visible control to monitor API connection status and manually disable Claude API calls during UI testing — saving API credits when only the layout/flow is being verified.

### Components

| Component | Details |
|---|---|
| **Status indicator** | Coloured dot (🟢 green / 🔴 red) + label. Sits at the top of the sidebar above the nav radio. |
| **"API is connected"** | Green dot + green bold text. Shown only when toggle is ON **and** `ANTHROPIC_API_KEY` is present in env. |
| **"API is not connected"** | Red dot + red bold text + small grey sub-label explaining why (toggle off vs key not found). |
| **Enable API toggle** | `st.toggle("Enable API", key="api_enabled")`. Default: `True`. Flip to `False` → all Claude calls immediately return `None`, zero credits consumed. |
| Divider | Visual separator between the API block and the nav radio. |

### Session state key

`st.session_state["api_enabled"]` — boolean, initialised to `True` on first load.

### How the toggle gates Claude calls

Both `_call_claude()` and `_call_claude_with_pdf()` check `st.session_state.get("api_enabled", True)` as the **first** guard — before even building the client. If `False`, they return `None` immediately. This means:
- No network requests made
- No API credits consumed
- All pages fall through to stub/sample data exactly as if the key were absent

### Connection status logic (two independent conditions)

| Toggle | Key present | Indicator |
|---|---|---|
| On | Yes | 🟢 API is connected |
| On | No | 🔴 API is not connected · *Key not found* |
| Off | Yes or No | 🔴 API is not connected · *Toggle is off* |

### Implementation note

The toggle is rendered inside a `with st.sidebar:` block **before** the nav radio is rendered. `st.session_state["api_enabled"]` is initialised at module level (before the sidebar block) so it is always available to the `_call_claude` functions which are called later in the page render.

---

## Page 1 — Jira Intake

### Purpose
Entry point. User provides an OPM ticket number. App reads the ticket, extracts the WF number, finds the BRD in Google Drive, reads it, and presents a summary for confirmation.

### Intake Method Toggle
User picks one of two methods via a horizontal radio button at the top:
- **Enter OPM Ticket Number** — existing flow
- **Upload BRD PDF** — direct upload flow

### Components — Method A (Ticket Number)

| Component | Type | Details |
|---|---|---|
| Ticket number input | Text field | Placeholder: "e.g. OPM-67" |
| Start Intake | Primary button | Triggers the intake process |
| Status stepper | `st.status` block | Shows: Reading ticket → WF found → BRD found → BRD analysed |
| BRD Summary | Two-column key-value display | Client, campaign type, channel, affiliations, relationship codes, age, geography, suppressions, activity logic, deployment dates, expected count |
| Confirm & Proceed | Primary button | Saves context to session state, navigates to Audience Builder |

### Components — Method B (Upload BRD PDF)

| Component | Type | Details |
|---|---|---|
| PDF uploader | `st.file_uploader` | Accepts `.pdf` only |
| Ticket number (optional) | Text field | For file naming and context — not required to proceed |
| Status stepper | `st.status` block | Shows: PDF received → file name + size → BRD analysed |
| BRD Summary | Same two-column layout as Method A | |
| Confirm & Proceed | Same as Method A | |

### BRD Summary — `_is_stub` warning

When the Claude API is not connected (no `ANTHROPIC_API_KEY`), `_parse_brd_json` returns the fallback template with `_is_stub: True`. `show_brd_summary` checks this flag and shows an orange `st.warning`:

> "⚠️ Claude API not connected — the fields below are blank/template only. Your ticket number has been recorded. Fill in the fields manually on the Audience Builder page, or connect the Claude API..."

When real Claude output is returned, no warning is shown — normal caption only.

**Stub template (all blanks/generic — NOT Valero-specific):**
```python
stub_summary = {
    "Client": "", "Campaign Type": "", "Channel(s)": "",
    "Affiliations in Scope": "", "Relationship Codes": "",
    "Age Filter": "18+ (baseline standard)",
    "Geography": "US 50 states only (exclude PR, GU, VI, AS, MP)",
    "Suppressions": "", "Activity Logic": "", "Email Deployments": "", "Expected Count": "",
}
```
The stub must never contain client-specific data (e.g. Valero, OPM-67). Different ticket entries cache different session state entries (`_claude_brd_{ticket}`) but all use the same blank template as fallback. Display shows `"—"` for any empty field.

**Exception: OPM-67 is a saved sample** — see below.

### OPM Ticket + WF Number injection

After the cache lookup in Method A, the `_active_summary` dict is copied (not referenced) and OPM Ticket + WF Number are injected:
```python
_active_summary = dict(st.session_state[_brd_cache_key])
_active_summary["OPM Ticket"] = ticket
_active_summary["WF Number"]  = wf_number
st.session_state["_brd_active_summary"] = _active_summary
```
For Method B (PDF), ticket_override is injected if provided:
```python
_pdf_active_summary = dict(st.session_state[_pdf_cache_key])
if ticket_override.strip():
    _pdf_active_summary["OPM Ticket"] = ticket_override.strip()
st.session_state["_brd_active_summary"] = _pdf_active_summary
```
This ensures OPM Ticket and WF Number are always available in `campaign_context` downstream.

### Rules
- Nothing moves to Audience Builder until user clicks "Confirm & Proceed"
- "Confirm & Proceed" strips internal flags (`_is_stub` etc.) before saving to `campaign_context`, sets `page_idx = 1`, `_nav_pending = True`, `_scroll_top = True`, and calls `st.rerun()`
- `_is_stub` and any `_`-prefixed keys are always stripped before saving to `campaign_context`
- Method A: corrections must go through re-entering ticket and clicking Start Intake
- Method B: if summary looks wrong, user re-uploads a corrected PDF
- **No "Something looks wrong" button** on Jira Intake — if intake is wrong, user just re-enters

---

## Page 2 — Audience Builder

### Purpose
Builds the audience SQL query step by step based on the confirmed BRD context. Six sections unlock progressively — each section requires the previous to be confirmed before it appears.

### Manual entry guard
When the user submits the "Enter campaign details manually" form, the **"Use these details"** button validates that at least **Client** and **OPM Ticket** are non-empty before saving. If either is blank, shows `st.error("⚠️ Client and OPM Ticket are required before proceeding.")` and does NOT save to `campaign_context`.

### Sections

| Section | What it shows | Unlock condition | User action |
|---|---|---|---|
| 1 — Campaign Context | BRD summary carried from Jira Intake (read-only) | Always visible | Confirm or go back to edit |
| 2 — Sanity Config Lookup | `childOrgId`, affiliations, `rewardMaxCap`, `rewardEarningEndDate`, affiliation filter decision | `s1_confirmed = True` | Fetch then confirm affiliation list |
| 3 — Query Clarification (conditional) | **Activity-based:** external activity IDs. **Incentive-based:** capping rule IDs (info only). **Simple filter:** auto-advances | `s2_confirmed = True` | Confirm activities (activity-based only) |
| 4 — Query Preview | Full SQL + output columns + PII check | `s3_confirmed = True` | Review query |
| 5 — Databricks Notebook | Notebook name, Copy or Create options | `s4_confirmed = True` | Choose option |
| 6 — Next Step | "Proceed to Approval Gate →" | `s4_confirmed = True` | Proceed |

### Section 1 — "Looks good — proceed" guard

Before confirming, checks that at least one campaign field has a non-empty value:
```python
if not any(str(v).strip() for v in campaign.values()):
    st.error("⚠️ No campaign data found. Run Jira Intake first or enter details manually above.")
else:
    st.session_state["s1_confirmed"] = True
    st.session_state["s2_confirmed"] = False   # reset downstream
    st.session_state["s2_fetched"] = False
    st.success("Context confirmed. Section 2 unlocked.")
```
The guard does NOT require a specific key like "OPM Ticket" — it passes if ANY campaign value is non-empty. This is important because BRD-parsed summaries use keys like "Channel(s)" and "Affiliations in Scope", not always "OPM Ticket".

### Section 2 — gated on `s1_confirmed`

Section 2 is ONLY rendered when `st.session_state.get("s1_confirmed")` is True:
```python
if not st.session_state.get("s1_confirmed"):
    st.info("✋ Confirm Section 1 context first to unlock the Sanity config fetch.")
else:
    # Fetch button + results render here
```
Without this gate, the "Fetch Client Config from Sanity" button was accessible with no intake data at all.

### Fallback SQL — no hardcoded Org IDs

The Claude-fallback SQL template uses `<ORG_ID>` as a placeholder, not a hardcoded client ID:
```sql
WHERE md.org_id = {_sanity_cfg.get("childOrgId", "<ORG_ID>")}
```
Never use a real client org_id (e.g. `9000288`) in the template — stub SQL with a real org_id could mislead if run accidentally.

### Section 5 — Notebook name
Built from non-empty parts only:
```python
_nb_parts = [p for p in [campaign.get("OPM Ticket",""), campaign.get("WF Number",""), campaign.get("Client","")] if p.strip()]
_nb_parts.append("2026_Progress_Campaign")
notebook_name = "_".join(_nb_parts)
```
Prevents ugly `"___2026_Progress_Campaign"` names when fields are blank.

### Standalone mode
If no `campaign_context` in session state, shows "Enter campaign details manually" expander before Section 1. Fields: Client, OPM Ticket, WF Number, Campaign Type, Channel(s), Affiliations, Geography, Suppressions. **"Use these details" requires Client + OPM Ticket before saving.** Section 1 "Edit / Re-run intake" sets `page_idx = 0`, `_nav_pending = True`, `_scroll_top = True`, `st.rerun()`.

### Rules
- Sections unlock one at a time — no skipping
- Affiliation filter decision label always shows the count rationale
- Activity IDs shown in human-readable format (activity name + external ID)
- Primary capping target rule ID is displayed but never asked for confirmation
- Output query always shows which columns are included and confirms no PII
- "Proceed to Approval Gate" writes `audience_summary`, sets `page_idx = 2`, `_nav_pending = True`, `_scroll_top = True`, `st.rerun()`

---

## Page 3 — Approval Gate

### Purpose
Send the HTML approval report to recipients, wait for reply, and track approval status.

### Sections

| Section | What it shows | User action |
|---|---|---|
| 1 — HTML Report Preview | Inline scrollable preview + Download HTML + Download PDF | Review and download |
| 2 — Recipients | Default: `stacy.swicegood@optum.com` — editable | Edit if needed |
| 3 — Send for Approval | "Send Approval Email" button with guard (see below) | Click to send |
| 4 — Approval Status | Manual override: Mark as Approved / Mark as Rejected | Override if needed |
| 5 — Next Step | "Proceed to Monitoring →" — enabled only after approval confirmed | Proceed |

### Send button guard

Before showing "Send Approval Email", the page checks if campaign data is present:
```python
_ag_has_data = bool(campaign.get("OPM Ticket", "").strip() or campaign.get("Client", "").strip())
if not _ag_has_data:
    st.warning("⚠️ No campaign data found. Please complete Jira Intake → Audience Builder first, or enter details manually above, before sending the approval email.")
elif st.button("📨 Send Approval Email", ...):
    ...
```
The button is hidden entirely (replaced by a warning) when both OPM Ticket and Client are blank.

### Standalone mode
If no `audience_summary` or `campaign_context` found, shows "Enter campaign details manually" expander. Fields: Client, OPM Ticket, Channel, Campaign Name, Audience Count, Affiliations. Submitting writes to `st.session_state["audience_summary"]` and reruns.

### Campaign dict (built from `audience_summary` or `campaign_context`)

```python
campaign = {
    "Client":         _ag_ctx.get("Client",         ""),
    "OPM Ticket":     _ag_ctx.get("OPM Ticket",     ""),
    "WF Number":      _ag_ctx.get("WF Number",      ""),
    "Campaign":       _ag_ctx.get("Campaign",       ""),
    "Audience Count": _ag_ctx.get("Audience Count", "—"),
    "Channel":        _ag_ctx.get("Channel",        _ag_ctx.get("Channel(s)", "—")),
    "Affiliations":   _ag_ctx.get("Affiliations",   _ag_ctx.get("Affiliations in Scope", "—")),
}
```

**All fallbacks are empty strings or `"—"` — never hardcoded stub values.**

### HTML report — standard structure

The approval report HTML is built dynamically from BRD context.

| Section | Always shown? | Dynamic behaviour |
|---|---|---|
| Header (gradient, badges, ticket/WF) | Always | Badge row shows "Email Ready", "DM Ready", "EM1+EM2 Ready" based on Channel |
| Campaign Overview table | Always | Relationship Code + Geography rows only appear if BRD specifies them |
| Audience Summary KPI cards | Always | Email block if channel contains Email; DM block if channel contains Direct Mail/DM |
| Filters Applied | Always | Tier 1: 4 baselines + Valid Email (if email channel) + Valid Address (if DM); Tier 2: BRD-driven |
| EM1 vs EM2 section | Only if multi-wave email | Keywords in Suppressions or Campaign name: "reminder", "em2", "contact history", "wave 2" |
| Approval Sign-off | Always | Two signature boxes: Data Analyst + Marketing Manager |

**Channel detection:**
- `_has_email = True` if channel contains "email" or " em"
- `_has_dm = True` if channel contains "direct mail", " dm", or "mail"
- If neither → default `_has_email = True`

**PDF download:** `except (ImportError, OSError)` — covers missing `weasyprint` AND missing GTK/GLib on Windows.

### Rules
- Subject line: `[APPROVAL REQUIRED] {OPM Ticket} | {Client} {Campaign} — Audience Review`
- "Proceed to Monitoring →" sets `page_idx = 3`, `_nav_pending = True`, `_scroll_top = True`, `st.rerun()`

---

## Page 4 — Monitoring

### Purpose
Generate an on-demand HTML delivery report for a campaign at any point after launch. Day N is auto-calculated from today vs the launch date.

### Layout — no section gating

#### Inputs (four columns)

| Component | Type | Details |
|---|---|---|
| Campaign ID | Text input | Numeric campaign ID from `read_api_9000084` |
| Launch Date | Date picker | The date the campaign emails were sent |
| OPM Ticket Number | Text input | Alternative lookup |
| WF Number | Text input | Alternative lookup |

If Campaign ID is empty and either OPM Ticket or WF Number is filled, shows **"🔍 Look up Campaign ID"** button. On click, stub resolves to a placeholder Campaign ID with an explicit **orange `st.warning`**: *"⚠️ Stub result: Campaign ID resolved to [value] (example only). Real Databricks lookup not yet wired. Please verify or enter manually."* Never show a stub lookup result as if it were real.

#### Generate button guard

`⚙️ Generate Delivery Report` — **disabled if launch date is in the future OR if Campaign ID is empty**:
```python
disabled=(_dp < 0 or not _cid_in.strip())
```
A `st.caption` shows `"⚠️ Enter a Campaign ID above to enable report generation."` when Campaign ID is blank.

#### Stub camp data — uses campaign_context

The stub camp dict is seeded from `campaign_context` session state (if available) so it reflects the actual campaign being worked on:
```python
_mon_ctx = st.session_state.get("campaign_context", {})
_stub_camp = {
    "opm_ticket":  _mon_ctx.get("OPM Ticket",   "OPM-??"),
    "client":      _mon_ctx.get("Client",        "—"),
    "campaign":    _mon_ctx.get("Campaign Type", "Campaign"),
    "wf_name":     _mon_ctx.get("WF Number",     "—"),
    "campaign_id": "—",
    "launch_date": "—",
}
```
`campaign_id` and `launch_date` are always overwritten from the user's inputs on generate.

#### Report preview and send — same as before

- Download HTML / Download PDF / Send via Gmail appear after generation
- "Proceed to Post-Campaign ROI →" sets `page_idx = 4`, `_nav_pending = True`, `_scroll_top = True`, `st.rerun()`

### Session state keys

| Key | Default | Purpose |
|---|---|---|
| `mon_cid_val` | `""` | Preserves Campaign ID — blank on first load |
| `mon_launch_date` | `None` | Saved on generate |
| `mon_report_sent` | `False` | Drives status block visibility |
| `mon_sent_at` | `None` | Timestamp of last send |

---

## Page 5 — Post-Campaign ROI

### Purpose
Generate an on-demand ROI report comparing T+0 baseline against post-campaign data.

### Layout — no section gating

#### Inputs (five columns)

| Component | Type | Details |
|---|---|---|
| Campaign ID | Text input | Numeric campaign ID |
| Launch Date | Date picker | T+0 anchor |
| Campaign Type | Selectbox | Progress / Completion / Activity-based / Simple Filter |
| OPM Ticket Number | Text input | Alternative lookup |
| WF Number | Text input | Alternative lookup |

Lookup button shows same orange warning as Monitoring when stub result is returned.

#### Generate button guard

`⚙️ Generate ROI Report` — **disabled if launch not selected, launch is in the future, OR Campaign ID is empty**:
```python
_roi_btn_disabled = (not _roi_launch) or (_roi_day_n < 0) or (not _roi_cid.strip())
```
Caption shown when CID missing: `"⚠️ Enter a Campaign ID above to enable ROI report generation."`

#### Email subject — uses campaign_context

The email subject line uses campaign_context for client name and campaign type:
```python
_roi_ctx_email = st.session_state.get("campaign_context", {})
_roi_client_lbl = _roi_ctx_email.get("Client", "") or _roi_stub_camp.get("client", "") or "Client"
_roi_camp_lbl   = _roi_ctx_email.get("Campaign Type", "") or _roi_stub_camp.get("campaign", "") or "Campaign"
_msg["Subject"] = f"[ROI REPORT T+{_dn}] Campaign {_cid} | {_roi_client_lbl} {_roi_camp_lbl}"
```
Never hardcode a specific client name (e.g. "Valero") in the email subject.

### Session state keys

| Key | Default | Purpose |
|---|---|---|
| `roi_report_html` | `None` | Stored HTML |
| `roi_report_sent` | `False` | Status block visibility |
| `roi_sent_at` | `None` | Timestamp |
| `roi_cid_val` | `""` | Blank on first load |
| `roi_day_n` | `None` | Saved on generate |

### Report structure (HTML)
1. **Header** — navy gradient, WF name, Campaign ID badge, T+N badge, Launch date, Check date
2. **Delivery Summary** — 6 KPI cards + 4 rate KPIs
3. **Incentive Completion Change** — T+0 vs T+N cards: Overall / TEST / CONTROL + incremental lift
4. **Bucket Distribution** *(Progress only)* — Bucket | At Send | % | At Check | % | Trend arrow
5. **Sign-off** — Data Analyst + Marketing Manager + Generated timestamp
6. **Footer** — data sources, campaign ID, T+N, "Generated by MAT"

---

## Cross-Page Session State & Navigation

### Navigation — `_nav_pending` pattern

**Why:** `index=` on a keyless radio is ignored by Streamlit on reruns (widget retains state from the user's last click), causing programmatic navigation to require a double-click. With `key=` and a pre-render hook, the radio updates correctly in a single rerun.

**Implementation:**
```python
if "page_idx" not in st.session_state:
    st.session_state["page_idx"] = 0
if "_nav_radio" not in st.session_state:
    st.session_state["_nav_radio"] = PAGES[st.session_state["page_idx"]]

# Only sync when a Proceed/Edit button explicitly flagged a navigation
if st.session_state.pop("_nav_pending", False):
    st.session_state["_nav_radio"] = PAGES[st.session_state["page_idx"]]

selected = st.sidebar.radio("", PAGES, key="_nav_radio")
st.session_state["page_idx"] = PAGES.index(selected)
```

**Key rule:** `_nav_radio` session state is ONLY written BEFORE the radio widget renders (via the `_nav_pending` hook). Writing to a keyed widget's session state AFTER it renders raises `StreamlitAPIException`. The `_nav_pending` flag is the safe mechanism — it defers the write to the next rerun's pre-render phase.

**Every "Proceed to X →" and "Edit / Re-run intake" button must set three flags:**
```python
st.session_state["page_idx"]    = <target_index>
st.session_state["_nav_pending"] = True   # triggers radio sync on next render
st.session_state["_scroll_top"]  = True   # scroll new page to top
st.rerun()
```

**Navigation points that set `_nav_pending = True`:**
1. Jira Intake — "Confirm & Proceed to Audience Builder →" (`page_idx = 1`)
2. Audience Builder Section 1 — "Edit / Re-run intake" (`page_idx = 0`)
3. Audience Builder Section 6 — "Proceed to Approval Gate →" (`page_idx = 2`)
4. Approval Gate Section 5 — "Proceed to Monitoring →" (`page_idx = 3`)
5. Monitoring — "Proceed to Post-Campaign ROI →" (`page_idx = 4`)

User sidebar clicks do NOT set `_nav_pending` — this is intentional. User clicks update `_nav_radio` directly through Streamlit's widget interaction, which is correct and doesn't need a pre-render hook.

### BRD summary persistence

The `show_brd_summary()` call must be OUTSIDE both method blocks. Structure:
- Inside `if submitted:` (Method A) or `if uploaded_pdf:` (Method B) → run intake → store result in `st.session_state["_brd_active_summary"]`
- **After both method blocks** → `if st.session_state.get("_brd_active_summary"): show_brd_summary(...)`

This means the summary persists when: any button is clicked, the method toggle changes, the user navigates away and comes back.

"Confirm & Proceed" → strips `_`-prefixed keys, saves clean dict to `campaign_context`, pops `_brd_active_summary`, sets `page_idx = 1`, `_nav_pending = True`, `_scroll_top = True`, calls `st.rerun()`.

### Scroll-to-top implementation

- `st.components.v1.html(..., height=1)` — **not `height=0`** (zero-pixel iframe may not execute)
- JS wrapped in `setTimeout(..., 120)` — fires 120ms after iframe loads
- Targets multiple selectors for cross-version Streamlit compatibility
- In-page reruns (status updates, form submits, lookup buttons) do NOT set `_scroll_top`

### Cross-page data flow

| Key | Written by | Read by | Contents |
|---|---|---|---|
| `campaign_context` | Page 1 — "Confirm & Proceed" | Pages 2, 3, 4, 5 | Full BRD summary dict (Client, OPM Ticket, WF Number, Campaign Type, Channel, Affiliations, etc.) |
| `audience_summary` | Page 2 — "Proceed to Approval Gate" | Page 3 | Audience fields: Client, OPM Ticket, WF Number, Campaign, Audience Count, Channel, Affiliations |

### Audience Builder session keys

| Key | Default | Purpose |
|---|---|---|
| `s1_confirmed` | `False` | Section 1 confirmed (gates Section 2 entirely) |
| `s2_fetched` | `False` | Tracks whether Sanity fetch has run |
| `s2_sanity_result` | `{}` | Fetched Sanity config dict |
| `s2_confirmed` | `False` | Section 2 confirmed |
| `s3_confirmed` | `False` | Section 3 confirmed |
| `s4_confirmed` | `False` | Section 4 confirmed |
| `s5_confirmed` | `False` | Section 5 confirmed |
| `s4_query` | — | Generated SQL (Claude or fallback) |
| `_claude_brd_{ticket}` | — | Caches Claude's BRD extraction per ticket |
| `_claude_pdf_{name}_{size}` | — | Caches Claude's PDF extraction per file |

### Standalone manual entry

Pages 2 (Audience Builder) and 3 (Approval Gate) show "Enter campaign details manually" expanders when no upstream context is found. Page 2 requires at least Client + OPM Ticket. Pages 4 and 5 require only Campaign ID and Launch Date — no dependency on earlier pages.

---

## Claude API Integration

### Configuration
- **API key**: `ANTHROPIC_API_KEY` env variable (`.env` file or system env — never hardcoded)
- **Model**: `_CLAUDE_MODEL = "claude-sonnet-4-5"`
- **Skill file**: `Marketing_automation_skill.md` — loaded once via `@st.cache_data`, used as system prompt
- **Graceful fallback**: every Claude call returns `None` if key is unset or call fails — caller falls back to stub with `_is_stub = True` flag

### `_parse_brd_json` behaviour

```python
def _parse_brd_json(claude_response, fallback):
    if not claude_response:
        return {**fallback, "_is_stub": True}   # tag fallback so UI can warn
    try:
        # parse JSON from Claude response
        result = json.loads(...)
        result.pop("_is_stub", None)             # real response — remove stub flag
        return result
    except Exception:
        pass
    return {**fallback, "_is_stub": True}
```

`_is_stub` and `_is_sample` are internal flags — always stripped (via `if not k.startswith("_")` filter) before saving to `campaign_context`.

**Two distinct internal flags:**

| Flag | Set when | BRD Summary message |
|---|---|---|
| `_is_sample: True` | API off + ticket = OPM-67 | 📋 Blue info box: "OPM-67 sample data loaded — all fields pre-filled" |
| `_is_stub: True` | API off + any other ticket | ⚠️ Orange warning: "API not connected — fields below are blank/template only" |
| Neither | API connected, real Claude output | Caption: "Review the summary below…" |

**Cache clearing on re-submit:** Every "Start Intake" button press pops `_claude_brd_{ticket}` from session state before re-evaluating. This prevents stale cached data from a previous run (or previous code version) from persisting across re-runs in the same browser session.

### Wired call points

| Location | What Claude does | Fallback |
|---|---|---|
| **Jira Intake — Method A** | Extracts BRD campaign parameters from ticket as JSON | Blank template stub |
| **Jira Intake — Method B** | Reads PDF via document API, extracts BRD parameters as JSON | Blank template stub |
| **Audience Builder — Section 4** | Generates production Databricks SQL per all skill rules | Template SQL with `<ORG_ID>` placeholder |
| **Post-Campaign ROI — Ask MAT** | Answers metric questions, generates campaign-scoped SQL | Template stub SQL |

### Jira + Google Drive stubs
Not yet wired — stubs with comments (`mcp__d8026533 getJiraIssue`, `mcp__a42bc1b9 search_files`). WF number is hardcoded as `"WF22031341"` (stub).

---

## OPM-67 Saved Sample Dataset

### Rule (strict — do not deviate)

**OPM-67 is the ONLY pre-loaded sample in the entire app.** It activates across ALL five pages ONLY when the user enters `"OPM-67"` in Jira Intake (ticket field).

**The four scenarios — confirmed behaviour:**

| Ticket entered | Claude API connected | All 5 pages show |
|---|---|---|
| `OPM-67` | **Yes** | **Real Claude-generated data (API call made, sample NOT used)** |
| `OPM-67` | No | Full OPM-67/Valero saved sample data everywhere |
| Any other ticket | **Yes** | **Real Claude-generated data based on the marketing automation skill** |
| Any other ticket | No | Blank fields, placeholder text, zero numbers — no OPM-67 data anywhere |

**Critical rule:** The OPM-67 saved sample is a **fallback only** — it is used ONLY when the API is not connected. When the API IS connected, OPM-67 goes through Claude exactly like any other ticket. The sample is never used when the API is available, because a re-pull of OPM-67 may be needed with fresh data.

For all tickets, Claude IS called normally (`_call_claude()`) when the API key is present. OPM-67 only receives special treatment when the API is absent — in that case `_OPM67_BRD` is used as the direct result (with `_is_stub: True` flagged for UI warning). For other tickets without API, `stub_summary` (blank template) is used.

Detection: `campaign.get("OPM Ticket", "") == "OPM-67"` (or `st.session_state.get("campaign_context", {}).get("OPM Ticket", "") == "OPM-67"` from pages 4 and 5).

**Caveat — Pages 4 & 5 standalone use:** Monitoring and ROI detect OPM-67 via `campaign_context`. If the user navigates directly to those pages without completing Jira Intake first, `campaign_context` won't be set and OPM-67 data won't load even if they enter Campaign ID 52136. Normal flow (Intake → Builder → Approval → Monitoring → ROI) works correctly end to end.

### Sample data stored (module-level constants in app.py)

| Constant | Contents |
|---|---|
| `_OPM67_BRD` | Client: Valero, Campaign Type: Progress, Channel: Email, Affiliations 02-11, etc. |
| `_OPM67_SANITY` | childOrgId: 9000288, clientId: 0907816, rewardMaxCap: $200, affiliations 02-11, NOT IN ('01') |
| `_OPM67_DELIVERY` | total: 7974, sent: 7652, control: 322, invalid: 73, delivered: 7579, opened: 1694, clicked: 128 |
| `_OPM67_DAILY` | One row: 2026-03-03 send data |
| `_OPM67_ROI_COMP` | overall/test/control completion comparison, lift: 0.3% |
| `_OPM67_BUCKETS` | 6 completion buckets (0% through 100%) with send/check counts |

### Where the OPM-67 check is applied

| Page | Where | What happens |
|---|---|---|
| **1 — Jira Intake** | `if _claude_brd: ... elif ticket == "OPM-67": ...` in cache block | API connected → Claude runs (OPM-67 or not). API not connected + OPM-67 → `_OPM67_BRD` with `_is_stub: True`. API not connected + other → blank stub. |
| **2 — Audience Builder S2** | `_is_opm67 = campaign.get("OPM Ticket","") == "OPM-67"` | OPM-67 → `_OPM67_SANITY`; others → placeholder dict with "connect to Sanity API" values |
| **2 — Audience Builder S4** | `_is_opm67_sql = ...` | OPM-67 → full Valero SQL with org_id 9000288 and `NOT IN ('01')`; others → template with `<PLACEHOLDERS>` |
| **4 — Monitoring** | `_is_opm67_mon = _mon_ctx.get("OPM Ticket","") == "OPM-67"` | OPM-67 → `_OPM67_DELIVERY` + `_OPM67_DAILY`; others → all zeros, empty daily list |
| **5 — ROI** | `_is_opm67_roi = _roi_ctx.get("OPM Ticket","") == "OPM-67"` | OPM-67 → `_OPM67_ROI_COMP` + `_OPM67_BUCKETS`; others → all zeros, empty bucket list |

### Non-OPM-67 fallback (no API)

When ticket ≠ OPM-67 and Claude API is not connected:
- Jira Intake: blank summary + `_is_stub = True` warning
- AB Section 2: Sanity config shows `"— (connect to Sanity API)"` for every field + `st.warning`
- AB Section 4: SQL template shows `<CLIENT_NAME>`, `<AFFILIATION_FILTER>`, `<ORG_ID>` placeholders
- Monitoring: report generates with all-zero metrics
- ROI: report generates with all-zero metrics and empty bucket table

---

## Negative Testing Rules (enforced in code)

Every button that processes or sends data must be guarded against no-intake scenarios:

| Page | Button | Guard |
|---|---|---|
| AB — "Use these details" (manual form) | Requires Client + OPM Ticket non-empty | `st.error` if either blank |
| AB — Section 1 "Looks good — proceed" | Requires any campaign field non-empty | `st.error` if all blank; sets `s1_confirmed` on pass |
| AB — Section 2 "Fetch Client Config" | Gated on `s1_confirmed` | Shows info message if not confirmed |
| AB — Fallback SQL | Uses `<ORG_ID>` placeholder | Never hardcode a client org_id in the template |
| AG — "Send Approval Email" | Requires OPM Ticket or Client non-empty | Warning + hidden button if both blank |
| MON — "Generate Delivery Report" | Requires Campaign ID non-empty + launch not future | `disabled=(not cid or dp < 0)` |
| MON — "Look up Campaign ID" | Stub — always warns | Orange `st.warning`: "Stub result — verify manually" |
| ROI — "Generate ROI Report" | Requires Campaign ID non-empty + launch date selected + not future | `disabled=(not cid or no_launch or dp < 0)` |
| ROI — "Look up Campaign ID" | Same as Monitoring | Orange `st.warning` |
| ROI — "Send via Gmail" | Subject uses campaign_context | Never hardcode client name in email subject |

---

## App Branding — MAT Identity

### Name
**MAT** — *Marketing Automation Tool*. All caps. Positioned as a personal smart agent ("Ask MAT").

### Page config
```python
st.set_page_config(page_title="MAT — Marketing Automation Tool", page_icon="⚡", layout="wide")
```

### Sidebar logo
Custom HTML/CSS block: dark navy gradient, teal `M` badge, `MAT` lettering, accent bars.

### Sidebar footer
```python
st.sidebar.caption("Optum Engage · B2C Campaigns · ⚡ MAT")
```

### "Ask MAT" pattern
- Header: `### 💬 Ask MAT`
- Button: `"Ask MAT ✨"` (primary)

---

## App Storage — SQLite (`campaigns.db`)

> **Not yet implemented.** Documents the intended design for when SQLite is wired in.

One row per campaign in a `campaigns` table. All columns except `id`, `client`, `campaign_name`, `created_at` are nullable — partial module usage is supported.

### Write triggers

| Page | Trigger | DB action |
|---|---|---|
| 1 — Jira Intake | "Confirm & Proceed" | INSERT or UPDATE (upsert on `opm_ticket`) |
| 2 — Audience Builder | Notebook created / query copied | UPDATE audience builder columns |
| 3 — Approval Gate | "Send Approval Email" | UPDATE approval_status = "Not Yet" |
| 3 — Approval Gate | "Mark as Approved/Rejected" | UPDATE approval_status + timestamp |
| 4 — Monitoring | "Generate Delivery Report" | UPDATE campaign_id + launch_date |
| 4 — Monitoring | Report sent | UPDATE t1/t2_report_sent_at |
| 5 — ROI | ROI report generated | UPDATE roi_report_generated_at |

### Rules
- `campaigns.db` created automatically on first app run
- Timestamps stored as ISO 8601 strings
- Lookup key: `opm_ticket` if present; else `campaign_name + client + campaign_type`
- Never duplicate rows — always upsert

---

## Future State — Multi-User Product Roadmap

> **Vision:** Convert this single-user Streamlit tool into a company-wide workflow management platform — with Google SSO login, role-based dashboards, in-app approvals, and full audit history. Designed to run on localhost for internal testing first, then deploy to Capillary infrastructure.

---

### What Is Being Built

A **multi-account, role-gated, dashboard-driven product** where:
- Every team member logs in with their Capillary Gmail (`@capillarytech.com`)
- Each person sees only what their role allows
- Approval requests appear in the approver's in-app dashboard — not in email
- All ticket history, approvals, and audit logs are persisted in a shared database
- Downstream automation (Drive link → Jira ticket) triggers automatically on approval

---

### The Core Architectural Shift

**Current:** Everything in `st.session_state` — per-browser, per-user, per-session. No sharing between users.

**Future:** Shared database (SQLite for localhost, PostgreSQL/Supabase for production). All sessions read/write the same data. Session state becomes UI-only scratch space; business data lives in DB.

---

### Layer 1 — Authentication (Google SSO)

#### Recommended: `streamlit-google-auth` (Phase 1)
- `pip install streamlit-google-auth`
- Register a Google OAuth app in Google Cloud Console (free)
- Returns `user_email`, `user_name`, `user_picture` after login
- Domain restriction: `if not user_email.endswith("@capillarytech.com"): st.stop()`
- Works on localhost and deployed identically

#### Upgrade path: Auth0 (when deploying to production)
- Handles Google SSO + Microsoft/Okta for future flexibility
- Free tier: 7,500 active users/month
- Consistent identity layer across environments

#### Login flow
```
User visits app → Google OAuth popup → Google confirms identity →
App receives email → Check @capillarytech.com → Look up user in DB →
Get role → Show role-appropriate dashboard
```

---

### Layer 2 — Database

#### Localhost: SQLite (single file, zero setup)
- `pip install sqlalchemy`
- File: `marketing_automation.db` in project root
- Fine for 1–10 users testing locally
- Cannot be shared across machines

#### Production: PostgreSQL via Supabase
- Free-tier PostgreSQL with web UI
- Switch from SQLite → Supabase by changing one connection string
- Multiple users on different machines all connect to same DB
- Supabase also provides Realtime (websocket notifications)

#### Database schema

| Table | Key columns |
|---|---|
| `users` | id, email, name, picture_url, role, created_at |
| `tickets` | id, opm_ticket, wf_number, client, status, created_by, created_at |
| `approvals` | id, ticket_id, requested_by, assigned_to, status, requested_at, acted_at, notes |
| `audience_files` | id, ticket_id, drive_link, row_count, uploaded_at |
| `notifications` | id, user_id, ticket_id, message, is_read, created_at |
| `audit_log` | id, ticket_id, actor_email, action, timestamp |

---

### Layer 3 — Role System

#### Roles

| Role | Permissions |
|---|---|
| **Admin** | All actions + assign roles to users, see all tickets, system health panel |
| **Campaign Manager** | Create tickets, run Audience Builder, submit approval requests |
| **Approver** | See approval inbox, approve/reject, download reports |
| **Viewer** | Read-only — ticket history, report downloads |

#### Role assignment flow
1. First login with `@capillarytech.com` email → account created with Viewer role (default)
2. Admin logs in → opens Admin Panel page → sees all users → assigns roles via dropdown
3. Role stored in `users` table → applied on every subsequent login

---

### Layer 4 — Dashboard Page (New Page 0)

Replaces the current landing page. Content is role-gated.

#### Campaign Manager view
- "My Tickets" table — ticket ID, client, status, last updated
- Quick stats: X campaigns this month, Y awaiting approval
- "Start New Campaign →" button

#### Approver view
- **Pending Approvals inbox** — one card per ticket awaiting sign-off
- Each card: Ticket ID, Client, Campaign Type, Submitted by, Date
- Click card → opens full Approval Gate for that ticket (with Approve/Reject buttons)
- History: previously approved/rejected tickets below

#### Admin view
- All of the above
- User management table (assign/change roles)
- System health: API connected, Gmail connected, DB status

---

### Layer 5 — In-App Approval Flow

#### Current (email-based — being replaced)
```
Campaign Manager → "Send Approval Email" → Gmail → Stacey reads email →
No in-app feedback loop
```

#### Future (in-app)
```
Campaign Manager → "Submit for Approval" → writes to approvals table →
Notification badge appears on Stacey's dashboard →
Stacey clicks pending card → sees full report + Download HTML + Download PDF →
Stacey clicks Approve/Reject → DB updated with her email + timestamp →
Automation triggers: audience CSV Drive link posted to Jira ticket →
Campaign Manager's dashboard updates: "✅ Approved by Stacey on [date]"
```

#### What Stacey sees
- Identical to the current Approval Gate layout
- "Send Approval Email" button replaced by **✅ Approve** and **❌ Reject** buttons
- Action recorded in `approvals` table with actor + timestamp

---

### Layer 6 — Notifications

| Option | When to use | How it works |
|---|---|---|
| **Polling (now)** | Localhost / MVP | Every 30s each session queries DB for new notifications. Badge on Dashboard nav item. |
| **Email + in-app (hybrid)** | Best for initial deploy | Gmail pings approver ("new approval request — open the app"). Action still happens in-app. |
| **Supabase Realtime** | Production | Websocket push — instant badge update when approval arrives. No polling needed. |

---

### Layer 7 — Downstream Automation on Approval

When approver clicks Approve:
1. Query `audience_files` table → get Google Drive link for this ticket
2. Call Jira MCP (`mcp__d8026533__editJiraIssue`) → post Drive link to Jira ticket
3. Write to `audit_log` → `action: "approved + drive_link_posted"`
4. Update `tickets.status` → `"Approved"`
5. Trigger notification to Campaign Manager

Both the Jira MCP and Drive MCP are already available in this Claude session — wiring them is straightforward once the DB layer exists.

---

### Phased Build Plan

#### Phase 1 — Auth + Roles ✅ BUILT
- [x] `pip install streamlit-google-auth` — installed (v1.1.8)
- [x] `pip install xhtml2pdf` — replaces WeasyPrint for PDF export (Windows-compatible)
- [x] `auth.py` — SQLite DB module: `init_db`, `upsert_user`, `get_user`, `get_all_users`, `set_role`, `delete_user`, `is_allowed_domain`, `role_badge_html`
- [x] `marketing_automation.db` — SQLite file, auto-created on first run
- [x] `google_credentials.json` — template file; fill with Google Cloud Console credentials
- [x] `.env` additions: `DEV_MODE`, `DEV_EMAIL`, `DEV_ROLE`, `COOKIE_SECRET`
- [x] Auth gate in `app.py` — runs before all rendering; DEV_MODE bypass for testing
- [x] Top-right profile bubble — avatar/initials in the Streamlit toolbar; click → dropdown with name, email, role badge, Sign Out

**Profile bubble — implementation notes (important):**
- Rendered via `st.components.v1.html(...)` running JS that reaches into `window.parent.document` (the bubble lives in the real toolbar, not the iframe).
- **Mounted as the first child of `[data-testid="stToolbarActions"]`** → natural flex order `[Profile] [Deploy] [⋮]` with auto-spacing. Do NOT use `position:fixed` + manual pixel math — it breaks because the component script's `window.innerWidth` is the iframe width, not the parent's.
- Real Streamlit test-ids (verified in browser): toolbar = `stToolbar`, actions wrapper = `stToolbarActions`, deploy = `stAppDeployButton` (NOT `stDeployButton`), menu = `stMainMenu`.
- Dropdown menu uses `position:fixed` with top/right computed from the bubble's `getBoundingClientRect()` on open → never clipped by the header.
- A `MutationObserver` on `stToolbar` re-mounts the bubble if React re-renders the toolbar; plus a 100 ms retry loop (max 20) for initial paint.
- Logout: the Sign out link points to `/?logout=1`; Python catches `st.query_params["logout"] == "1"`, clears session, reruns.

**File-change prompt removed via `.streamlit/config.toml`:**
- `[server] fileWatcherType = "none"` + `runOnSave = false` → the "Source file changed → Rerun / Always rerun" toolbar prompt never appears (it showed up after editing files and switching tabs).
- `[client] toolbarMode = "auto"` → keeps the Deploy button and ⋮ main menu.
- **Requires a Streamlit server restart to take effect** (config is read once at startup). Code edits now require a manual browser refresh.
- [x] Admin Panel page — user table with role dropdowns, remove button, system info
- [x] `⚙ Admin Panel` added to PAGES list for Admin role only

**Auth modes — controlled by `AUTH_MODE` in `.env` (plug-and-play):**

| `AUTH_MODE` | Behaviour | Use for |
|---|---|---|
| `demo` (current) | Simulated login screen — no Google. Real logout/login cycle. | Hackathon demo, localhost testing |
| `google` | Real Google OAuth via `google_credentials.json`, domain-restricted | Production |

**Path B — Demo login (AUTH_MODE=demo):**
- Full-screen login page: MAT branding card → "Sign in with Google" button (with real Google "G" SVG) → "Choose an account" email entry → Continue.
- Two-step flow tracked by `st.session_state["_demo_step"]` (`welcome` → `email`).
- On Continue: validates `@capillarytech.com`, upserts the user into SQLite, sets `auth_user`, reruns into the app.
- Sidebar + toolbar deploy button hidden on the login screen for a clean full-screen look.
- **Logout actually logs out** — `/?logout=1` is handled at the top of the auth gate (before it re-evaluates), so the login screen stays put. No auto-login bounce.
- Any `@capillarytech.com` email logs in as that user with their DB-assigned role → lets you demo different role dashboards by logging in as different emails.
- `ADMIN_EMAIL` in `.env` is seeded as Admin on startup so there is always an admin (bootstrap).
- Profile dropdown shows a **DEMO MODE** badge.

**Path A — Real Google OAuth (AUTH_MODE=google), when ready for production:**
1. Go to [console.cloud.google.com](https://console.cloud.google.com) → create project.
2. Configure OAuth consent screen (Internal = capillarytech.com only, or External + test users).
3. Create OAuth Client ID (Web app) → add `http://localhost:8501` to Authorised JavaScript origins **and** redirect URIs.
4. Download credentials JSON → replace contents of `google_credentials.json`.
5. Set `AUTH_MODE=google` in `.env`.
6. Restart the app. No other code changes — the gate switches automatically.

**`.env` keys (auth):** `AUTH_MODE` (`demo`/`google`), `ADMIN_EMAIL` (bootstrap admin), `COOKIE_SECRET` (OAuth cookie signing).

**Google SSO — hosting findings (2026-06-11, CORRECTED):**
- On **Streamlit Cloud** (`mat-capillary.streamlit.app`): immediate Google 403 before any account picker. Initially suspected a Workspace org block — **that diagnosis was WRONG**.
- On **Railway**: the Google account picker appears and authentication succeeds → the 403 was Streamlit-Cloud-hosting-related, not an org policy. **Use Railway for Google SSO.**
- **PKCE bug + fix:** after authenticating, `(invalid_grant) Missing code verifier` — the OAuth redirect lands in a fresh Streamlit session, losing the PKCE `code_verifier` (newer `google-auth-oauthlib` ≥1.4 enables PKCE by default; older local versions don't, which is why it never reproduced locally). Fix in app.py PATH A: after constructing `Authenticate`, set `_authenticator.flow.autogenerate_code_verifier = False` and `code_verifier = None` (web-app clients use client_secret; PKCE optional).
- **Railway deploy config:** `railpack.json` (Railpack builder ignores nixpacks.toml/Procfile) — buildAptPackages `pkg-config, libcairo2-dev, libffi-dev`, deploy aptPackages `libcairo2`, startCommand binds streamlit to `$PORT`. `.python-version` pins 3.12 (3.13 has no mise prebuilt + missing wheels). Env vars set directly in Railway Variables (no st.secrets needed — the os.environ bridge handles both).

**Sidebar spacing:** Tightened so all 6 nav items (5 pages + Admin Panel) + footer fit without scrolling on a standard window. Removed a duplicate `---` divider (the profile-bubble component renders in the main area, leaving two sidebar dividers adjacent). CSS injected at top of sidebar: `stVerticalBlock gap: 0.45rem`, `hr margin: 0.35rem 0`, sidebar `padding-top: 1rem`. Do NOT re-add a second divider between the MAT logo and the API status block.

## Design System (global, 2026-06-11)

All visual styling lives in TWO places — change these, not per-page markup:
1. `.streamlit/config.toml` `[theme]` — base palette: primary `#007B8F` (teal), background `#FFFFFF`, secondary `#F6F8FA`, text `#1A202C`.
2. **Global CSS block in app.py** (right after `st.set_page_config`) — the design system:
   - **Typeface:** Inter (Google Fonts import), all elements.
   - **Buttons:** ONE size everywhere — 38px height, 8px radius, 0.875rem/600, `white-space: nowrap` + `min-width: max-content` (never wraps to two lines). Primary = solid `#007B8F` w/ white text (selector prefix `[data-testid^="stBaseButton-primary"]` — the `^=` matters: it also catches `primaryFormSubmit`). Secondary = white w/ `#D7DEE6` border, teal hover.
   - **Cards:** expanders, forms, metrics = white bg, `#E8ECF1` 1px border, 12px radius, faint shadow.
   - **Headings:** h1 1.55rem/800, h2 1.15rem/700, h3 0.98rem/700 — uniform across pages.
   - **Spacing:** `.block-container` padding-top 2.2rem, max-width 1180px; main `stVerticalBlock` gap 0.65rem; `hr` margin 0.9rem.
   - **Sidebar:** white bg, right border, nav radio items = 8px-radius hover pills.
   - **Inputs:** 8px radius, teal focus ring `rgba(0,123,143,0.12)`.
   - Canvas: `#FAFBFC` app background.

**Button-column rule:** paired buttons need column ratios wide enough for one-line text — use e.g. `[1.6, 1.6, 2.8]` (two buttons) or `[1.4, 1.4, 1.4, 1.8]` (three), NOT `[1, 1, 4]` (overlaps, since buttons no longer wrap).

**⚠️ Local dev note:** `fileWatcherType = "none"` means the server does NOT pick up app.py edits on browser refresh — restart `streamlit run app.py` after every code change.

**Common pitfall:** global `p { color: ... }` rules override button label color — the design system explicitly re-whitens `button p` for primary buttons. Keep that rule if editing.

**Verified in browser (2026-06-11):** login screen → Google button → email entry → logged in as Admin → Sign out → returns to login screen and stays (no bounce). ✅

**Session persistence across browser refresh (cookie-based):**
- Problem: `st.session_state` is wiped on a hard refresh (refresh = new Streamlit session), which logged users out. A real app must persist auth in a cookie.
- Fix: `auth.py` adds `sign_token(email)` / `verify_token(token)` — an HMAC-signed `email|sig` token using `COOKIE_SECRET`. Cookie name = `mat_auth`.
- **Set:** the profile-bubble JS component writes `mat_auth` (path=/, max-age=24h / 86400s, SameSite=Lax) on every logged-in render. Google OAuth cookie also set to `cookie_expiry_days=1`.
- **Read:** the auth gate reads `st.context.cookies.get("mat_auth")` **synchronously** at the top and re-hydrates `auth_user` → no login-screen flash on refresh.
- **Delete:** on `/?logout=1`, the gate skips cookie-restore (`_logging_out` flag) and the login screen emits JS to delete the cookie → refresh after logout stays logged out.
- Token is signed → cannot be forged to impersonate another user; domain check still enforced in `verify_token`.

**⚠️ IMPORTANT — editing `auth.py` requires a Streamlit server restart.** `auth.py` is an imported module; Python caches it for the process lifetime. Only the main `app.py` re-runs on browser refresh. After ANY change to `auth.py` (or `.streamlit/config.toml`), restart: `streamlit run app.py`. Symptom if forgotten: `ImportError: cannot import name '...' from 'auth'`.

#### Phase 2 — Persistent campaign database (IN PROGRESS)

**Architecture — shared DB layer + relational design (built 2026-06-11):**
- `db.py` — single shared `engine` + `metadata` for ALL tables. SQLite locally (no `DATABASE_URL`), Postgres/Supabase on cloud. `init_db()` imports all table modules and `create_all()`s. Every new table module imports `engine, metadata, now_iso` from `db`.
- **Universal join key = `campaign_uid`** (surrogate PK on `campaigns`). Every child table (approvals, audience_files, delivery_metrics, roi_metrics, notifications, email_log, audit_log, knowledge_entries) carries `campaign_uid` FK → campaigns. `users` links via email (`created_by`/`assigned_to`).
- Three **business lookup keys** on campaigns (unique, human-facing): `opm_ticket`, `wf_number`, `campaign_id`.
- **Snapshot + history pattern:** denormalized snapshot columns live on `campaigns` (e.g. `approval_status`, `t1_report_sent_at`) for fast lookup + the scheduled flow; child tables hold full history/detail.

**`campaigns` table = master spreadsheet migrated 1:1** (`campaigns.py`). Columns: campaign_uid (PK) + the 22 sheet columns (opm_ticket, wf_number, client, campaign_name, campaign_type, channel, brd_link, intake_date, notebook_link, approval_subject_line, approval_sent_at, approval_status, approval_updated_at, approval_recipients, campaign_id, launch_date, t1_report_sent_at, t2_report_sent_at, roi_report_generated_at, row_created_at, last_updated_at, created_by). Master sheet: `1Mbui5tDyXPkYdrbIg7EdiCeFifN1Vsdj24S-FMK4MiI` (migrate, not sync — app is source of truth). Sheet was empty (headers only) → no data import needed.

Functions: `get_campaign_by_ticket/wf/campaign_id`, `find_campaign(query)` (flexible: tries all three), `upsert_campaign(dict)`, `update_campaign(uid, **)`, `list_campaigns`, `list_campaigns_by_user`. ✅ Verified against Supabase + local SQLite.

**Full table catalog (tiered):** Tier1 = users✅, campaigns✅, client_config, approvals, audience_files · Tier2 = delivery_metrics, roi_metrics · Tier3 = audit_log, notifications, email_log, knowledge_entries · Tier4 = scheduled_jobs. PII RULE: member/audience data NEVER stored — only counts + Drive links (audience_files).

**Tier 1 child tables — BUILT ✅ (2026-06-11):** `client_config.py`, `approvals.py`, `audience_files.py` — registered in `db.init_db()`, verified on Supabase + SQLite with a full relational round-trip (campaign → approval → file → config, joined by `campaign_uid`).
- `client_config`: PK `client` · upsert_client_config / get_client_config · caches Sanity config
- `approvals`: PK `approval_uid`, FK `campaign_uid` · create_approval / set_status / get_pending_for(approver) / get_by_campaign · full history (campaigns.approval_status stays the snapshot)
- `audience_files`: PK `file_uid`, FK `campaign_uid` · add_audience_file / get_files_for_campaign · Drive link + row_count ONLY (PII rule)

**Tier 1 page wiring — DONE ✅ (2026-06-11), verified in browser:**
- Jira Intake confirm → `upsert_campaign()` (only when ticket or WF present — prevents blank rows); `campaign_uid` stored in session.
- AB §2 fetch → OPM-67 sample also writes `client_config` cache; other clients try `get_client_config()` first (source tracked in `s2_source`: sample/cache/stub with distinct messaging), stub placeholders only as last resort.
- AB §5 "Create Notebook" → `update_campaign(notebook_link=…)`.
- Approval Gate send → `approvals.create_approval()` + campaign snapshot (status=Awaiting, sent_at, subject, recipients); Approve/Reject buttons → `set_status()` + snapshot. `ag_approval_uid` kept in session.
- Monitoring/ROI "Look up Campaign ID" → real `find_campaign()` (ticket → WF → campaign_id). Three outcomes: found+has campaign_id → autofill; found without → warning to enter manually; not found → error suggesting intake.
- **⚠️ Keyed text_input gotcha:** `value=` is IGNORED after first render. To programmatically fill `mon_cid_input`/`roi_cid_input`, stage via `_mon_cid_pending`/`_roi_cid_pending` and write to the widget key BEFORE instantiation (pre-render hook, same pattern as `_nav_pending`).
- `audience_files` writes NOT yet wired — no real Drive upload exists in the app yet; wire it the moment Drive upload lands.

**Remaining Phase 2:**
- [ ] Tier 2: delivery_metrics + roi_metrics (save report snapshots on generate)
- [ ] Tier 3: audit_log, notifications, email_log, knowledge_entries
- [ ] Tier 4: scheduled_jobs

#### Phase 3 — Dashboards (~2 days)
- [ ] Add Page 0 — Dashboard (role-aware landing page)
- [ ] Campaign Manager view: my tickets table
- [ ] Approver view: pending approvals inbox
- [ ] Admin view: user management

#### Phase 4 — Downstream Automation (~1 day)
- [ ] On Approve: get Drive link from DB → post to Jira via MCP
- [ ] Write audit log entry
- [ ] Notify Campaign Manager in-app

#### Phase 5 — Deploy + Supabase (production)
- [ ] Swap SQLite → Supabase PostgreSQL (connection string change only)
- [ ] Deploy Streamlit app (Streamlit Community Cloud / Docker on VM / Capillary server)
- [ ] Enable Supabase Realtime for instant notifications
- [ ] Set `ALLOWED_DOMAIN=capillarytech.com` in production env

---

### Localhost vs. Deployed

| Option | Effort | Cost | Best for |
|---|---|---|---|
| **ngrok** | 5 min | Free | Quick multi-user testing — shares your localhost via temp URL |
| **Streamlit Community Cloud** | 30 min | Free | Up to 3 apps, GitHub-connected deploy |
| **Docker on VM** (AWS/GCP/Azure) | 2–3 hrs | ~$5–20/month | Proper production deploy |
| **Capillary internal server** | IT dependency | Free | Best long-term — stays inside corporate network |

> For testing with Stacey before deployment: run `ngrok http 8501` → share the URL → she can access your localhost from her machine.

---

### What Changes in the Existing App

| Current | Future |
|---|---|
| No login | Google SSO gate — Capillary Gmail only |
| `st.session_state` for all business data | SQLite/PostgreSQL for shared persistent data |
| Approval via Gmail reply | In-app Approve/Reject buttons in Approver dashboard |
| Single-user view | Role-gated pages — each user sees their view |
| Hardcoded recipient email | Approver pulled from `users` table by role assignment |
| No history | All tickets persisted with full audit trail |
| 5 pages | 6 pages (Dashboard added as Page 0) + Admin Panel |

> The 5 existing pages are **unchanged in layout and logic**. They gain: (a) an auth check at the top, (b) DB writes at key actions, (c) data sourced from DB instead of session state.
