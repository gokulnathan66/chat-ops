# Screenshot Guide — LLMOps Platform

This document is a step-by-step walkthrough of both dashboards for the purpose of capturing screenshots for the LinkedIn article and post. Follow this in order. Each section lists the URL, what to do, and exactly what to capture.

Both dashboards must be running:
- **Realtime Monitoring**: `http://localhost:3000`
- **AI Interface**: `http://localhost:3001`

---

## Part 1: Realtime Monitoring Dashboard (port 3000)

### Screenshot 1 — Overview: KPI Cards
**URL**: `http://localhost:3000`
**What to show**: The four KPI cards at the top (Avg RAG Score, Avg Faithfulness, Cost Today, HITL Pending) with the "Recent RAG Evaluations • Live" table below showing session IDs, score bars, faithfulness values, and HITL column.
**Caption idea**: "Real-time operational health — RAG scores, faithfulness, cost, and pending human reviews at a glance."
**Notes**: The live dot indicator next to "Recent RAG Evaluations" is a nice detail to show. Make sure the page has loaded data (non-zero scores if possible).

---

### Screenshot 2 — RAG Evaluations: Golden Queries + Scores
**URL**: `http://localhost:3000/evals`
**What to show**: The full split-pane view. Left panel showing the Questions list (your golden test questions). Right panel showing Avg RAG Score bar + the per-question breakdown with faithfulness and relevance score bars. The "Live · refreshes every 15s" indicator top right.
**Caption idea**: "Continuous RAG quality monitoring — define test questions once, get scored after every document ingest."
**Notes**: If there are no questions yet, add 1–2 via the input field at the bottom of the left panel before screenshotting. Questions like "What is Microsoft Azure segment revenue?" show the financial domain context well.

---

### Screenshot 3 — PCA: Sentiment Health Bar (top of page)
**URL**: `http://localhost:3000/pca`
**What to show**: The full page from the top — the "Overall sentiment health" stacked bar (green/neutral/grey), the "Live" indicator, and the Positive/Neutral/Negative percentage labels. Below it, the All/Positive/Neutral/Negative filter chip row.
**Caption idea**: "Post-conversation sentiment analysis — system-wide health calculated every 15 minutes from inactive sessions."
**Notes**: Scroll to the very top of the page before screenshotting.

---

### Screenshot 4 — PCA: Topics + Distribution + Unresolved Questions
**URL**: `http://localhost:3000/pca`
**What to show**: Scroll down past the filter chips to show the two side-by-side panels (Top Topics bar chart on the left, Sentiment Distribution on the right) plus the Unresolved Questions numbered list below.
**Caption idea**: "Automatic topic extraction and unresolved question detection — the system surfaces what customers couldn't get answers to."
**Notes**: This requires scrolling down from the top of the PCA page. The Unresolved Questions list is the most distinctive element — make sure it's visible with at least 3–4 items showing.

---

### Screenshot 5 — HITL Queue: Pending Items
**URL**: `http://localhost:3000/hitl`
**What to show**: The full HITL Queue page. The red-highlighted "Pending • Live" section at the top with ESCALATION badge items showing session IDs and timestamps. The "Resolved" section below with resolution notes.
**Caption idea**: "Human-in-the-loop queue — escalated sessions and approval requests land here for operator review."
**Notes**: The red/pink background tint on the Pending section header is a strong visual — make sure it's visible. If there are no pending items, you can trigger one by clicking "Escalate to Human" in the AI Interface.

---

### Screenshot 6 — HITL Queue: Expanded Escalation Item (optional but strong)
**URL**: `http://localhost:3000/hitl`
**What to do**: Click the arrow/expand chevron on one of the pending ESCALATION items.
**What to show**: The expanded item showing the full conversation thread, text input box ("Send Response"), and "Resolve & Hand Back" button.
**Caption idea**: "Operators see the full conversation thread and can respond in real time before handing back to AI."
**Notes**: This is the most compelling single screenshot for showing the HITL interaction model. Worth spending time to get this right.

---

### Screenshot 7 — Document Ingestion: Upload UI
**URL**: `http://localhost:3000/ingestion`
**What to show**: The full ingestion page — Upload File / S3 Key tabs, the drag-and-drop zone ("Click to browse or drag & drop · .pdf, .txt, .csv · max 50 MB"), the "Upload & Ingest" button, and below it the "Recent Jobs" section showing at least one completed job with the "• Completed" green status pill.
**Caption idea**: "Document lifecycle management — upload PDFs, CSVs, or provide an S3 key. Live job status updates every 3 seconds."
**Notes**: Scroll down slightly to show both the upload zone AND at least one entry in Recent Jobs. The green "• Completed" pill alongside a filename like "microsoft_10k_annual_report_2025.pdf" grounds the demo in a real financial use case.

---

## Part 2: AI Interface (port 3001)

### Screenshot 8 — Session List: Overview
**URL**: `http://localhost:3001`
**What to show**: The two-pane layout with the session list visible on the left — showing multiple sessions with different status labels (complete · active · hitl_pending). The right pane should show the empty state ("Select a session or start a new chat" + "New Chat" button).
**Caption idea**: "Session management — all conversations with status tracking across active, complete, and human-review states."
**Notes**: The status badge text under each session ID (e.g., "8 turns · hitl_pending") is the key detail. Make sure at least one session shows `hitl_pending` in the list so the different states are visible.

---

### Screenshot 9 — Chat Thread: GENERAL Response (with metadata)
**URL**: `http://localhost:3001`
**What to do**: Click any session in the list that shows `complete` status. Look for turns that have the `GENERAL` badge.
**What to show**: A chat turn where the AI response bubble shows the `GENERAL` route badge in purple/indigo text, with the latency (e.g., "492ms") and token count (e.g., "142 tok") displayed. The conversation context should be visible above.
**Caption idea**: "Every response is tagged with its route (GENERAL or TOOLS), latency, and token count — full operational transparency per turn."
**Notes**: The `GENERAL` + `TOOLS` badges are what differentiate this from a regular chat UI. The latency and token count metadata per bubble is a distinctive LLMOps feature.

---

### Screenshot 10 — Chat Thread: TOOLS Response (RAG with source)
**URL**: `http://localhost:3001`
**What to do**: Find a session that asked a financial document question (e.g., "tell me about alphabet"). Click on it and scroll to the TOOLS-tagged response.
**What to show**: The full `TOOLS` response bubble with the badge (in a different color from GENERAL), latency (typically 9000ms+ for agent), token count, and the response text referencing financial data.
**Caption idea**: "TOOLS route — the LangChain agent performs semantic search over ingested documents and returns grounded, cited responses."
**Notes**: The higher latency on TOOLS responses (9000ms vs 500ms for GENERAL) is itself a meaningful signal to show. If you can expand source documents (if a toggle exists), include that.

---

### Screenshot 11 — HITL Escalation State (in AI Interface)
**URL**: `http://localhost:3001`
**What to do**: Click the `hitl_pending` session in the session list.
**What to show**: The full view — the blue banner at the top ("Connected to a human agent — type below to reply. AI resumes when the agent hands back control."), the `ESCALATED` amber message box ("I wasn't able to give you a confident answer..."), the `HUMAN AGENT` response bubbles, and the "Reply to human agent…" input placeholder at the bottom.
**Caption idea**: "When the AI escalates, customers are seamlessly connected to a human agent — the interface adapts in real time."
**Notes**: This is the single most important AI Interface screenshot. The blue banner, amber escalation card, `HUMAN AGENT` bubble styling, and changed input placeholder together tell the entire HITL story in one frame.

---

## Bonus Screenshots (use if space allows)

### Bonus A — Dark Mode Comparison
Both dashboards support dark mode via the moon icon in the bottom-left sidebar. Toggle it on the Overview page and take a screenshot of the same KPI cards in dark mode for a side-by-side comparison.

### Bonus B — Theme Toggle
Capture the moon icon in the sidebar before and after clicking to show the theme toggle. Small detail but shows product polish.

### Bonus C — RAG Evals: Adding a Golden Query
On the RAG Evals page, type a new test question into the input field at the bottom of the Questions panel and take a screenshot before clicking Add. Shows the dynamic golden query management in action.

---

## Screenshot Checklist

| # | Page | Element | Done |
|---|------|---------|------|
| 1 | Overview | KPI cards + RAG eval table | ☐ |
| 2 | RAG Evals | Golden queries + per-question scores | ☐ |
| 3 | PCA top | Sentiment health bar + filter chips | ☐ |
| 4 | PCA bottom | Topics chart + unresolved questions | ☐ |
| 5 | HITL Queue | Pending + resolved sections | ☐ |
| 6 | HITL Queue | Expanded escalation item with response UI | ☐ |
| 7 | Ingestion | Upload zone + completed job | ☐ |
| 8 | AI Interface | Session list with status badges | ☐ |
| 9 | AI Interface | GENERAL response with metadata | ☐ |
| 10 | AI Interface | TOOLS response with financial data | ☐ |
| 11 | AI Interface | HITL pending state (blue banner + escalation) | ☐ |

---

## Tips for Clean Screenshots

- Use a browser zoom of 100% (Cmd+0 to reset)
- Make sure all data has loaded before capturing (no "Loading…" spinners visible)
- For the monitoring dashboard, the light theme with clean white cards photographs better than dark mode for document use
- For the HITL Queue expanded item, resize the window slightly wider so the conversation thread and the action buttons are both visible without scrolling
- For the AI Interface HITL state, scroll the chat pane so the blue banner, the ESCALATED card, and at least one HUMAN AGENT bubble are all in frame simultaneously
