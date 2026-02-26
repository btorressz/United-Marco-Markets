# Changelog

## 2026-02-25 — Fix Paper SELL + Live Pricing + Clean Logs

### Root Cause
Paper SELL was blocked by the risk engine's **300-second cooldown timer**. After any successful order (BUY), all subsequent orders — including sells — were rejected with "Cooldown active: Xs remaining" for 5 minutes. The cooldown was designed for live trading safety but incorrectly applied to paper mode.
