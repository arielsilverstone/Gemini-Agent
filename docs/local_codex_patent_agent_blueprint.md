# Local Codex Patent Agent Blueprint

Created: 2026-02-09T07:27:51Z

## 1) Scope and objective
Use a **locally installed Codex** as the execution engine for patent drafting and prosecution support, with strict citation/audit behavior and an explicit human sign-off gate.

## 2) Suggested repository layout on your machine
```text
patent-agent/
  data/
    raw/                    # source PDFs, DOCX, emails, notes
    processed/              # normalized extracted text + metadata
  index/
    vectors/                # embedding/vector DB files
    metadata.sqlite         # fast filter + matter isolation
  prompts/
    system/
    tasks/
    qa/
  workflows/
    patent_workflow.yaml
  runs/
    2026-02-09T07-27-51Z/   # one directory per run
      inputs.json
      retrieved_sources.json
      draft.md
      verification.json
      eval.json
      log.txt
```

## 3) Timestamped run protocol
For each run:
1. Generate `run_id` in UTC (example: `2026-02-09T07-27-51Z`).
2. Save all inputs, retrievals, and outputs under `runs/<run_id>/`.
3. Stamp every section in generated deliverables with:
   - run id
   - model id
   - retrieval index version
   - policy version

Recommended metadata block:
```yaml
run_id: 2026-02-09T07-27-51Z
operator: <your_name>
model: <local_model_or_endpoint>
index_version: v1.0.0
prompt_bundle: patent_v1
verification_profile: strict_patent_v1
```

## 4) Prompt stack (ordered)
Use a layered prompt stack to separate durable policy from matter-specific tasking:
1. **System policy prompt** (global guardrails)
2. **Workflow controller prompt** (your step-by-step method)
3. **Task prompt** (draft claims, OA response, claim chart, etc.)
4. **Verification prompt** (citation and quality checks)

Files added in this repo for starter use:
- `config/templates/patent_workflow/patent_system_prompt.txt`
- `config/templates/patent_workflow/patent_task_prompt.txt`
- `config/templates/patent_workflow/patent_verification_prompt.txt`

## 5) Verification gates (must pass)
Before output is accepted:
- **Citation gate:** every substantive statement maps to at least one retrieved source.
- **Support gate:** each claim limitation is mapped to spec support snippet IDs.
- **Consistency gate:** terms are used consistently (same noun phrase map).
- **Risk gate:** hallucination risk, over-breadth risk, unsupported feature risk scored.
- **Human gate:** explicit reviewer sign-off required.

If a gate fails, force a revise cycle and store failure reasons in `verification.json`.

## 6) Testing plan
### Smoke tests (every run)
- Retrieve top-k docs by matter id and ensure deterministic filtering.
- Generate one draft section and verify output schema.
- Run verifier and ensure a machine-readable pass/fail report exists.

### Regression tests (weekly)
- Replay a fixed benchmark set of historical matters.
- Compare:
  - citation precision
  - reviewer edit distance
  - missing-support defects
  - draft turnaround time

### Release tests (prompt/index updates)
- A/B test old vs new prompt bundle.
- Block rollout if quality score drops below threshold.

## 7) Minimal implementation sequence
1. Build ingestion for one patent family.
2. Build retrieval with matter isolation.
3. Add prompt stack and structured outputs.
4. Add verification gates and reviewer sign-off.
5. Add benchmark replay for regression tracking.

## 8) Security defaults
- Local-only storage by default.
- Encryption at rest for source and run artifacts.
- Matter-based access control lists.
- Immutable run logs for auditability.

## 9) Beginner guide: download, PRs, and basic commands
If you're new to Git/Codex workflows, use this as a plain-English guide.

### A) How to "download" these changes to your machine
If this repository is on GitHub:
1. Open the repository page in a browser.
2. Click **Code** -> copy the HTTPS URL.
3. In terminal:
   ```bash
   git clone <repo-url>
   cd Gemini-Agent
   ```

If you already cloned it before, update it:
```bash
git pull
```

### B) What a PR is
A **PR** means **Pull Request**. It's a review page that shows:
- what files changed,
- exactly what lines were added/removed,
- and discussion/comments before merging.

Think of it as "please review these proposed changes" before they become part of main code.

### C) How to use this blueprint in practice (first run)
1. Copy your patent source files into `data/raw/`.
2. Run your ingest/index script to populate `data/processed/` and `index/`.
3. Choose a task (for example: OA response draft).
4. Run Codex with the prompt stack in section 4.
5. Save output and verifier report under a new `runs/<timestamp>/` folder.
6. Manually review before any external sharing or filing.

### D) What `sed` is
`sed` is a command-line text tool used to print or edit text streams/files.

Common example used in reviews:
```bash
sed -n '1,120p' some_file.md
```
That means: print lines 1 through 120 only.

If you prefer simpler commands, you can use:
```bash
cat some_file.md
```
or open files in a text editor instead of using `sed`.

### E) Minimal command cheat sheet
```bash
# show changed files
git status

# show recent commits
git log --oneline -n 5

# fetch latest updates
git pull

# create a new branch
git checkout -b my-update

# stage and commit your edits
git add <file1> <file2>
git commit -m "Describe what changed"
```
