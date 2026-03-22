# UI Check Runbook (Local)

This project does not include browser E2E in CI yet.
Use the script below for local, real-browser verification of analysis preference persistence.

## Check: AI Prediction Auto-Toggle Persistence

- Script: `scripts/ui_check_analysis_pred_toggle.py`
- Validates:
  1. Temporary Plus user creation
  2. Auth via `/_auth` session token
  3. Navigate `분석 → AI판단 → AI예측`
  4. Turn ON `입력 변경 시 자동 예측`
  5. Verify DB value saved (`pred_auto_rerun = true`)
  6. Navigate away and return
  7. Verify UI toggle still ON + DB still true

## How to run

```bash
cd stock-platform
python scripts/ui_check_analysis_pred_toggle.py
```

## Unified check runner

You can run consolidated checks from one command:

```bash
cd stock-platform
python scripts/run_checks.py
```

Include UI persistence check:

```bash
python scripts/run_checks.py --with-ui
```

`--with-ui` runs both UI checks:

- `scripts/ui_check_analysis_pred_toggle.py` (AI prediction toggle)
- `scripts/ui_check_analysis_chart_toggles.py` (data/technical auto-rerun toggles)
- `scripts/ui_check_analysis_full_subsections.py` (all analysis subsections full smoke)
- `scripts/ui_check_analysis_user_switch_isolation.py` (user A/B session-state leakage check)
- `scripts/ui_check_data_analysis_blank_state.py` (data-analysis empty-input should show warning, not blank)

Useful flags:

- `--skip-compile` : skip compileall step
- `--skip-pytest` : skip pytest step
- `--pytest-args "..."` : pass extra args to pytest (example: `--pytest-args "-q -k analysis"`)

Success output:

```text
[PASS] pred_auto_rerun persisted across UI rerender and navigation.
```

Failure output starts with:

```text
[FAIL] ...
```

## Notes

- The script starts a temporary local Streamlit server on a random free port.
- It creates and deletes a temporary user/settings/session rows automatically.
- This script is intentionally separate from pytest/CI to avoid flaky browser dependency in default test runs.

## Direct run: chart toggles check

```bash
python scripts/ui_check_analysis_chart_toggles.py
```

Success output:

```text
[PASS] data_auto_rerun and ta_auto_rerun persisted across UI navigation.
```

## Direct run: full analysis subsections smoke

```bash
python scripts/ui_check_analysis_full_subsections.py
```

Success output:

```text
[PASS] Full analysis subsection smoke run completed without fatal runtime errors.
```

## Direct run: user-switch isolation check

```bash
python scripts/ui_check_analysis_user_switch_isolation.py
```

Success output:

```text
[PASS] Analysis session state is isolated across user switch (no toggle leakage).
```

## Direct run: data-analysis blank-state check

```bash
python scripts/ui_check_data_analysis_blank_state.py
```

Success output starts with:

```text
[PASS]
```
