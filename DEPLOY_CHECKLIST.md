# Archon Deploy Checklist

Use this checklist before every production deployment.

## 1) Secrets preflight

Configure these keys in `.streamlit/secrets.toml` (or Streamlit Cloud Secrets).

### Core trading
- `TRADING_MODE` (`paper` recommended for initial rollout)
- `KIS_APP_KEY`
- `KIS_APP_SECRET`
- `KIS_ACCOUNT_NO`
- `KIS_BASE_URL`
- `KIWOOM_APP_KEY`
- `KIWOOM_SECRET_KEY`
- `KIWOOM_ACCOUNT_NO`
- `KIWOOM_BASE_URL`
- `NH_APP_KEY`
- `NH_APP_SECRET`
- `NH_ACCOUNT_NO`

### Payments
- `APP_BASE_URL`
- `STRIPE_SECRET_KEY`
- `TOSS_CLIENT_KEY`
- `PORTONE_IMP_CODE`
- `KAKAO_ADMIN_KEY`
- `ALLOW_DEMO_PAYMENTS` (`false` in production)

### Marketing automation alerts (optional)
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`

## 2) Security preflight

- Ensure `ALLOW_DEMO_PAYMENTS=false` in production.
- Verify payment success only via provider verification (no query-only trust).
- Verify webhook URLs used by marketing automation are public and trusted endpoints.
- Rotate exposed credentials immediately if any were shared in chat/logs.

## 3) Functional smoke test

Login and role checks:
- User login works.
- Admin login works (`admin / 7777` by current policy).
- Admin page appears at bottom of sidebar.
- Toolbar/GitHub icon: hidden for user, visible for admin.

AI chat checks:
- Provider/model selection works.
- TTS button (`🔊`) triggers speech script.
- Mic button (`🎤`) appears and can start recording.

Auto-trading checks:
- Broker API connection succeeds with valid key.
- US autopilot selection works (simulation path).
- Stop-loss/take-profit and forced liquidation create trade logs.

Marketing checks:
- Manual run creates notice + automation log.
- Webhook publish succeeds (or retries/fails with log).
- Failure alert path (notice/email) works when enabled.

## 4) Technical verification commands

Run from repo root:

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
python3 -m compileall -q .
```

Both must pass before release.

## 5) Release gate

Only deploy when all conditions are true:
- Secrets set and valid
- Security preflight pass
- Smoke test pass
- Tests pass
- Compile pass
