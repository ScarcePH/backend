# ScarcePH Backend

Flask backend for the ScarcePH commerce API and Messenger bot. Messenger checkout is now a guided, button-first workflow with synchronous webhook handling and human payment review. Uploading a payment screenshot does **not** create an order: inventory is rechecked and the order, payment, and stock deduction are created atomically only after staff approval.

## What changed

- Messenger webhook deliveries are processed synchronously without storing message bodies in PostgreSQL.
- Events retain their batch order and are serialized per sender with a Redis lock. Hashed event identifiers are retained in Redis for 24 hours to suppress completed duplicates.
- Checkout uses stable actions such as `ORDER_CONFIRM`, `PAYMENT_COD`, and `CHECKOUT_RESTART`; GPT is not used during an active checkout.
- Invalid checkout input is retried once, then handed to a person while preserving context.
- Messenger payment screenshots are downloaded with host, MIME, image, size, and dimension checks and copied to permanent object storage. OCR remains available only for web checkout.
- Submitted checkouts wait for human review. Approval locks the checkout and variations, rechecks price and stock, and creates the order and one payment in a transaction.
- Signed admin email links show a confirmation page on `GET`; approval or rejection only occurs on `POST`.

## Prerequisites

- Python 3.11 recommended (the Docker image uses 3.11)
- PostgreSQL
- Redis
- A Meta app and Messenger-enabled Facebook Page
- Google Cloud project with Cloud Tasks enabled
- HTTPS deployments for this backend and the email worker
- S3-compatible permanent object storage
- Existing email worker; OCR worker only if web checkout uses OCR

## 1. Install locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env` before importing or starting the application. Startup intentionally fails and lists missing required variables. Never commit `.env`, service-account keys, tokens, or storage credentials.

If the checked-in virtual environment was moved and its command wrappers have stale paths, use module commands such as `venv/bin/python -m flask` and `venv/bin/python -m alembic`.

## 2. Configure environment variables

Start from [`.env.example`](.env.example). These variables are required at startup:

| Variable | Purpose |
| --- | --- |
| `DB_URI` | PostgreSQL SQLAlchemy URL |
| `REDIS_URL` | Checkout state, handover context, sender locks, and 24-hour event deduplication |
| `JWT_SECRET_KEY` | API JWTs and fallback signing key for admin approval links |
| `APP_SECRET` | Meta webhook signature verification |
| `VERIFY_TOKEN` | Meta webhook setup challenge |
| `PAGE_ACCESS_TOKEN` | Graph API Messenger sends |
| `PAGE_APP_ID` | Detect staff/Page echo messages |
| `GOOGLE_CLOUD_PROJECT` | Project containing Cloud Tasks queues |
| `GOOGLE_CLOUD_LOCATION` | Queue region, for example `asia-southeast1` |
| `EMAIL_WORKER_URL` | Existing email worker HTTPS endpoint |

Also configure these before accepting Messenger checkout traffic:

- Set `ADMIN_APPROVAL_SECRET` to a separate random secret. Without it, the configured `JWT_SECRET_KEY` is used; there is no development-secret fallback.
- `EMAIL_TASK_QUEUE` defaults to `email-queue`.
- Set `BUCKER_API_URL` (the existing variable name), `BUCKET_ACCESS_KEY`, `BUCKET_SECRET_KEY`, and `IMAGE_BASE_URL` for permanent proof storage. The uploader currently writes to a bucket named `scarce-images`; create that bucket and grant the credentials permission to upload objects with the configured public-read behavior.
- `PAYMENT_PROOF_ALLOWED_HOSTS` is a comma-separated list of additional exact attachment hosts. Meta CDN suffixes are accepted by default. Do not add broad or untrusted hosts.
- Ensure the existing email worker is reachable at `EMAIL_WORKER_URL` from Cloud Tasks and that the `email-queue` contract matches the worker deployment.

Optional tuning:

- `BOT_DEPOSIT_AMOUNT` defaults to `1000` and applies to preorder/COD/COP deposits, capped at the current database price.
- Set `META_GRAPH_API_VERSION` to the Graph version approved for your Meta app. The code currently preserves `v17.0` as its default, so production should set this explicitly.
- `OPENAI_API_KEY` and `SYSTEM_PROMPT_ANALYSIS` are used for idle sales inquiries, never for active checkout transitions.

Generate secrets instead of inventing short values:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

## 3. Create the email Cloud Tasks resource

Authenticate the Google Cloud CLI, choose the deployment project, and enable Cloud Tasks:

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable cloudtasks.googleapis.com
```

Create the email queue in the same location configured in `.env`:

```bash
gcloud tasks queues create email-queue \
  --location=asia-southeast1 \
  --max-attempts=10 \
  --min-backoff=5s \
  --max-backoff=300s
```

Grant the backend runtime identity permission to enqueue email tasks:

```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:BACKEND_RUNTIME_SERVICE_ACCOUNT" \
  --role="roles/cloudtasks.enqueuer"
```

Google’s current documentation is available in [Create Cloud Tasks queues](https://docs.cloud.google.com/tasks/docs/creating-queues) and [Create HTTP target tasks](https://docs.cloud.google.com/tasks/docs/creating-http-target-tasks).

## 4. Prepare and migrate PostgreSQL

The checkout migration adds a unique constraint to `payments.order_id`. Check for old duplicates first:

```sql
SELECT order_id, COUNT(*)
FROM payments
WHERE order_id IS NOT NULL
GROUP BY order_id
HAVING COUNT(*) > 1;
```

If this returns rows, review and merge those payments before migration. The migration deliberately stops with an actionable error instead of deleting financial data.

Apply all pending migrations:

```bash
venv/bin/python -m flask db upgrade
```

The expected Alembic head is:

```text
8b9c0d1e2f3a
```

The migrations add checkout review metadata, enforce one payment per order, and permanently drop `messenger_events`. The migration performs no backup or export; its downgrade recreates only an empty table and cannot recover deleted conversations. Back up production before applying migrations if the old webhook records must be retained outside the application.

## 5. Run the backend

Local process:

```bash
venv/bin/python app.py
```

Docker:

```bash
docker-compose up --build
```

Messenger processing finishes inside `POST /webhook`. For end-to-end local testing, expose the local backend with an HTTPS tunnel and point Meta at its `/webhook` URL. Redis must be available for sender locking and deduplication.

## 6. Configure Meta Messenger

In the Meta app dashboard:

1. Add Messenger and connect the Facebook Page.
2. Set the webhook callback to `https://YOUR_BACKEND/webhook`.
3. Enter the same private value used for `VERIFY_TOKEN`.
4. Subscribe the Page to message and postback events required by the bot.
5. Store the app secret, Page access token, and app ID in `APP_SECRET`, `PAGE_ACCESS_TOKEN`, and `PAGE_APP_ID`.
6. Confirm Meta can complete the `GET /webhook` verification challenge and that signed `POST /webhook` requests return `200`.

## 7. Human-review checkout flow

```text
Customer selects variation
  -> bot reloads item, size, status, stock, and price
  -> customer confirms and selects payment method
  -> screenshot is validated and copied to permanent storage
  -> customer supplies validated shipping details
  -> staff receives one signed review notification
  -> staff opens GET confirmation page and submits POST approval/rejection
  -> approval transaction rechecks stock and creates order/payment once
```

Cancel and Start over invalidate the persisted checkout, including while the conversation is in human handover. Proof-submitted or expired sessions cannot silently create orders.

## 8. Verify the installation

Run the test suite and syntax checks:

```bash
venv/bin/python -m unittest discover -s tests
PYTHONPYCACHEPREFIX=/tmp/scarce_pycache \
  venv/bin/python -m compileall -q app.py config.py api bot db middleware services task tests migrations
git diff --check
venv/bin/python -m alembic -c alembic.ini heads
```

Before production traffic, smoke-test:

- a Meta delivery containing multiple events;
- duplicate message delivery;
- `503` retry behavior after dispatch or sender-lock failures;
- Redis sender serialization and 24-hour completed-event deduplication;
- JPEG, PNG, and WebP proof uploads plus invalid-host/oversize rejection;
- staff notification and signed GET-to-POST approval/rejection;
- cancellation after proof upload;
- concurrent approval and stock loss before approval;
- customer approval/rejection notifications.

## Operations and recovery

Messenger events are not persisted or dead-lettered. Meta retries the complete webhook delivery when the backend returns `503`; events already completed during an earlier attempt are skipped by their hashed Redis keys. The 24-hour deduplication window intentionally gives up permanent replay and recovery.

Before deploying this change, pause or delete the old Messenger Cloud Tasks queue and drain any tasks that should not invoke the retired worker. Deploy the code first so it no longer queries `messenger_events`, then apply the drop migration. This order prevents old application workers from querying a table that has already been removed.

Useful checks:

```bash
gcloud tasks queues describe email-queue --location=asia-southeast1
```

## Known local limitations

- Python 3.9 emits end-of-life warnings from Google libraries and boto3; use Python 3.11.
- A pre-existing migration (`e57b13e53de2`) has a broken full-history downgrade involving an unnamed constraint. The newer migrations generate valid upgrade/downgrade SQL, but do not attempt a full production downgrade without repairing and testing the older migration.
- Live PostgreSQL, Meta, Redis, email Cloud Tasks, email-worker, and object-storage checks require staging credentials and were not run by the unit suite.
