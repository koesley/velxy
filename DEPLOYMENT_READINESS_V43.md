# VELXTRIA deployment readiness (V43)

The Render startup failure on November 18, 2026 was caused by a missing `cryptography` installation, despite that package already being declared in `requirements.txt`. This release adds a pre-deploy guard that detects missing dependencies and missing entrypoint modules before Render attempts to start the server.

## Recommended Render build command

```sh
python -m pip install -r requirements.txt && python -m compileall -q . && python deployment_readiness_v43.py
```

Use this exact build command in the Render dashboard for **both** existing services. A change to `render.yaml` does not automatically override a manually configured service.

## Diagnostics

```sh
python deployment_readiness_v43.py --json
python -m unittest test_deployment_readiness_v43
```

Checks include Python entrypoint parsing, presence of local imports, required installed packages and requirement declarations, and mainnet checkout configuration if enabled. The checks never contact a payment processor, print secrets, or alter data. A passing result is **not** proof that the database, web process, payment processor, or live website is working. Inspect Render runtime logs and verify `/healthz` after deployment.

Keep `VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT=0` until real payment configuration is verified. The preflight checks presence and basic URL shape only, not actual BTCPay credentials or store network.

For failures, fix missing modules or dependencies rather than disabling the preflight. Do not paste API keys into logs, GitHub, or support messages.
