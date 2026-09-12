# Alert delivery

The runnable alert implementation lives in `services/api/app/main.py` to keep the optional demo backend a single process. Replay warnings are deduplicated by scenario, persisted, broadcast over WebSocket and optionally delivered to `SLACK_WEBHOOK_URL`. Unacknowledged warnings escalate after `ALERT_ESCALATION_SECONDS` (default 60). Acknowledgement suppresses escalation.

No external messages were sent during development. Webhook delivery is opt-in through backend configuration. In-process escalation timers do not survive a process restart; production needs a durable queue, authentication, rate limits and a separate worker.

