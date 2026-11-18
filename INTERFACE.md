# Mission Local Source Agent: interface guide

This guide is for an agent that wants to call this service, and for the person who sets that agent up. It covers access, requests, replies, source packages, signature checks, limits and errors.

Version 2, 2026-11-18. Section 11 lists the changes since version 1.

## 1. What it offers

Mission Local is a local news outlet in San Francisco. Its archive starts in 2008. This service is the outlet’s own agent. Other agents ask it in plain language about Mission Local’s reporting. It answers from published stories only.

A caller with an active subscriber credential gets a **signed source package**. The package holds:

- Exact sentences from one story.
- The documents those sentences link to. For each document it gives the web archive’s copy nearest the publication day, with its address and capture time.
- The story’s title, address, publication time, last change time and authors.
- Correction status: the correction note, and the sentence it concerns.
- Usage terms.

The agent does three more things:

- It asks one clarifying question if a broad request matches two or more distinct events.
- It may offer a package on a related story after it answers.
- It returns a signed “no match” result if the archive has nothing on the request.

A signature proves one thing: the content came from Mission Local and nobody changed it on the way. It makes no claim about the truth of the reporting.

## 2. Access

| Item | Value |
|---|---|
| Base address | `https://source-agent-905861176071.us-west1.run.app` |
| Agent card | `GET {base}/.well-known/agent-card.json`, no credential needed |
| Conversation endpoint | `POST {base}/a2a` |
| Protocol | A2A 1.0 over JSON-RPC 2.0. Plain request and reply. No streaming, no push |
| Authentication | Header `Authorization: Bearer <subscriber credential>` |
| Health check | `GET {base}/health` |

**Setup.** Requests need nothing beyond HTTPS. The signature check needs an Ed25519 library. In Python, a virtual environment gives you one without system rights:

```bash
python3 -m venv .venv && .venv/bin/pip install cryptography
```

Use a library. Do not write Ed25519 code yourself. A small mistake there can accept a bad signature.

**Credential.** The outlet issues a credential to each subscriber. The subscriber hands it to their agent. Ask the author for a course test credential. Keep the credential out of public files and logs.

The agent card lists three values for the signature check: `signing.alg` (`Ed25519`), `signing.key` (the outlet’s public key as a `did:key`) and `signing.packages` (the address pattern for packages).

## 3. Send a request

The method is `SendMessage`.

```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "SendMessage",
  "params": {
    "message": {
      "role": "ROLE_USER",
      "messageId": "<a unique id you create>",
      "contextId": "<optional: set it to continue a conversation>",
      "parts": [{"text": "<your question>", "mediaType": "text/plain"}]
    }
  }
}
```

| Field | Required | Notes |
|---|---|---|
| `parts[].text` | Yes | A question in plain language, 1 to 2,000 characters. The agent reads text only |
| `messageId` | Recommended | A new id for each new message. Reuse the same id for a resend after a timeout. See section 7 |
| `contextId` | No | Leave it out on the first message. The service creates one and returns it. Send the same value to answer a clarifying question or an offer |
| `taskId` | No | You may send the task id of the clarifying question with your answer |

Send the header `Content-Type: application/json`. The whole body must stay under 64,000 bytes.

Tips for questions:

- Name the event, the people, the place and the rough date. Matches get better.
- To check a quotation, put the exact words in quotation marks. The agent then searches for those exact words.
- One reply needs an archive search and several model steps. Allow up to 240 seconds.

A second method, `GetTask`, takes `{"id": "<task id>"}` and returns an earlier task. Its `result` is the task object itself, with no `task` wrapper.

## 4. Replies

The reply is in `result.task`:

```json
{
  "id": "<task id>",
  "contextId": "<conversation id>",
  "status": {
    "state": "TASK_STATE_COMPLETED",
    "timestamp": "2026-11-18T21:38:07Z",
    "message": {"role": "ROLE_AGENT", "parts": [{"text": "<reply text>"}]}
  }
}
```

Read `status.state` first. Then read `status.message.parts[].text`. There are five cases:

| Case | `state` | The text holds | Your next step |
|---|---|---|---|
| Clarifying question | `TASK_STATE_INPUT_REQUIRED` | A short list of distinct events and a request to pick one | Answer in a new message with the same `contextId`. The agent asks at most once per conversation |
| Source package | `TASK_STATE_COMPLETED` | The story’s date and title, the sentence count, any correction note, a line `Package: <address>`, the public key, and sometimes an offer of a related story | Fetch the package and verify it (sections 5 and 6). Quote only after that |
| No match | `TASK_STATE_COMPLETED` | A statement that the archive has nothing on the request, and a line `Package: <address>` | This result is signed too, so you can fetch and verify it. Tell your user plainly that nothing was found. Add nothing of your own |
| Headlines only | `TASK_STATE_COMPLETED` | The reason the credential did not qualify, and up to three story titles with links | There is no package to fetch. See section 7 |
| Service failure | `TASK_STATE_FAILED` | A one-line apology | You may retry |

**Offers.** To accept or decline an offer, reply in the same `contextId`. An acceptance returns a new package. After a decline, the agent confirms briefly and makes no further offer.

**Privacy.** The service needs only the question. Leave out who your user is and why they care.

## 5. The source package

Fetch it with `GET <package address>` and the same `Authorization` header. A request without an active credential gets HTTP 401.

The response has three parts:

```json
{
  "package_id": "df://sha256-<64 hex characters>",
  "package": { "...": "..." },
  "signature": {"alg": "Ed25519", "key": "did:key:z6Mk...", "value": "<signature>"}
}
```

Fields of `package` for a `match` result:

| Field | Meaning |
|---|---|
| `schema` | `mission-local/source-package@0.1` |
| `result` | `match` or `no_match` |
| `publisher` | The outlet’s name, address and public key (`agent_key`) |
| `issued_at` | Time of signature, in UTC |
| `request.sha256` | SHA-256 of the text of your last message. Your words are never in the package |
| `story` | `post_id`, `title`, `url`, `published`, `modified`, `authors` |
| `correction` | `null` for a story with no note. Otherwise `kind` (`correction` or `editors_note`), `note` (the note’s text) and `applies_to_sentence` (a sentence number, or `null`) |
| `sentences[]` | Each item has `n` (the sentence’s position in the story), `text` (the exact sentence) and `sources[]` |
| `sentences[].sources[]` | `anchor` (the link text), `url` (the original link), `kind` (`document` or `mission_local_story`) and `copy` (for `document` only) |
| `copy` | `status`, and for a found copy `archive_url`, `captured_at` and `days_from_publication` |
| `archive_covers_through` | The archive’s latest coverage time. Later stories are out of reach |
| `usage_terms` | You may quote with credit to Mission Local and a link to the story. No bulk storage. No model training |
| `limits` | What this package cannot prove |

Values of `copy.status`:

| Value | Meaning |
|---|---|
| `archived` | A copy exists and the package carries its fingerprint (`sha256`) |
| `located` | A copy exists. The package carries its address and capture time. You take the fingerprint yourself after download |
| `no_archived_copy` | The web archive has no copy of this document |
| `copy_unavailable` | The lookup failed, so the answer is unknown |

A `no_match` package has no `story` and no `sentences`. It adds `reason` and `explanation`. `reason` is `no_story` (no story on the request), `no_quotation` (no story has the exact quotation) or `withdrawn` (the story that matched has left the published archive).

## 6. Verify a package

Verify before you quote any sentence. Three steps are required:

1. **Get the public key.** Read `signing.key` from the agent card. It must equal `signature.key` and `package.publisher.agent_key`. Take the key from the agent card. The copy inside the package is not enough on its own.
2. **Build the canonical bytes.** Serialize the `package` object as JSON with keys in sorted order, with `,` and `:` as separators and no spaces, with non-ASCII characters left as they are, in UTF-8. In Python this is `json.dumps(package, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`.
3. **Check two things.**
   - `package_id` equals `df://sha256-` plus the SHA-256 of the canonical bytes in hex.
   - `signature.value` is an Ed25519 signature over the canonical bytes. It is base64url text with the trailing `=` removed.

To decode the public key, drop the prefix `did:key:z` and base58-decode the rest (Bitcoin alphabet). You get 34 bytes. The first two are `0xed 0x01`. The last 32 are the Ed25519 public key.

If any step fails, do not quote the package. Tell your user that you could not verify it.

Two optional steps go deeper:

- Open `story.url` and confirm that each `text` appears word for word in the published story.
- Download each `copy.archive_url`. The address should start with `https://web.archive.org/web/`. Compare the fingerprint with `sha256` if the package has one. Otherwise record the fingerprint yourself.

**What to pass on to your user.** A package gives you more than quotes. A complete answer carries five things:

- The sentence, word for word. Keep its punctuation and the quotation marks inside it.
- The story: title, publication date, address and authors.
- The sources of each sentence you quote, from `sources[]`. For a `document`, give the original address, the `archive_url` and the capture date. For a `mission_local_story`, give its address.
- The correction status. State it even for a `null` value.
- What you checked: the signature, and any optional step.

## 7. Permissions and limits

| Caller | What it gets | Hourly cap |
|---|---|---|
| Active subscriber credential | Clarifying questions, source packages, offers, signed “no match” results | 30 requests per credential |
| Lapsed subscriber credential | Story titles and links only | 30 requests per credential |
| No credential, or an unknown one | Story titles and links only, from a simple keyword search | 60 requests per caller address |

Other limits:

- All credential holders together share 300 requests per hour. Over the cap, the service returns HTTP 429.
- **A resend is safe.** The same credential, `contextId`, `messageId` and text get the first reply again. This holds for a first message with no `contextId` too. The resend does not count against the cap and creates no second package. After a timeout, resend the message unchanged. Use a new `messageId` for every new message, or you get the stored reply.
- **Fetch packages right away.** Conversations and packages live in the service’s memory. A restart clears them, and old package addresses then return HTTP 404.
- The archive covers published stories only.
- The agent answers one kind of question: what did Mission Local report? A package holds exact sentences and no summary. The agent does not judge truth and does not search other outlets.

## 8. Errors

| What you see | Meaning | What to do |
|---|---|---|
| HTTP 400 with JSON-RPC error `-32700` | The body is not valid JSON | Fix and resend |
| `-32600` | The request has the wrong shape | See section 3 |
| `-32601` | Unknown method | Use `SendMessage` or `GetTask` |
| `-32602` | `message` is missing, or the text is empty or over 2,000 characters | Fix and resend |
| HTTP 429 with `-32029` | Hourly cap reached | Capacity returns over the next hour. Try later |
| `-32001` | `GetTask` found no such task | A restart may have cleared it |
| HTTP 413 | The body is empty or over 64,000 bytes | Shorten and resend |
| HTTP 401 on a package | The credential is missing, unknown or lapsed | Use an active credential |
| HTTP 404 on a package | No such package, or a restart cleared it | Ask the question again |

## 9. A small example

Ask a question:

```bash
curl -s -X POST https://source-agent-905861176071.us-west1.run.app/a2a \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SOURCE_AGENT_TOKEN" \
  -d '{"jsonrpc":"2.0","id":"1","method":"SendMessage","params":{"message":{"role":"ROLE_USER","messageId":"example-001","parts":[{"text":"What did Mission Local report about the September 2023 staffing cuts at San Francisco State University?","mediaType":"text/plain"}]}}}'
```

The reply text, shortened:

```text
Here is a signed source package from our September 29, 2023 story, “San Francisco State University facing mass staffing cuts.” It has 6 sentences on the September 2023 staffing cuts at San Francisco State University, each with the sources it cites; 5 of those sources come with the web archive’s copy nearest publication day. This story carries a correction (it concerns the fourth sentence in this package): “Correction: A previous version of this story noted that San Francisco State had suffered a 16 percent drop in enrollment. The school is actually 16 percent below its target enrollment.”

Package: https://source-agent-905861176071.us-west1.run.app/packages/sha256-1a24f2f9...
The package is signed by did:key:z6Mkgv3iY1cHXdci8ezF54Az3nsGnxfzYE3tkgwZCqHoeKLn; the same key is listed in our agent card at .../.well-known/agent-card.json. Verify the signature before you quote it.

On October 30, 2023, Mission Local reported that the California State University faculty union voted to sanction a strike. Want a package on that too?
```

One sentence from the package:

```json
{
  "n": 8,
  "text": "The cuts will affect an unknown number of the 1,084 lecturers across the university.",
  "sources": [{
    "anchor": "1,084 lecturers",
    "url": "https://marcomm.sfsu.edu/sf-state-facts",
    "kind": "document",
    "copy": {
      "status": "located",
      "archive_url": "https://web.archive.org/web/20230929224052id_/https://marcomm.sfsu.edu/sf-state-facts",
      "captured_at": "2023-09-29T22:40:52Z",
      "days_from_publication": 0
    }
  }]
}
```

In this package `correction.applies_to_sentence` is 22. The correction concerns sentence 22 of the story. A quote of that sentence should mention the correction.

## 10. Known limits

- Source copies are web archive snapshots near the publication day. They stand in for a copy that the newsroom would save at publication.
- The service’s cloud host cannot download web archive snapshots. Most copies therefore have the status `located`: the service signs the address and capture time, and the caller takes the fingerprint.
- Conversations, packages and first replies live in the memory of one instance.
- Author names come from the public story page. If the page gives none, `authors` is empty.
- This is a course prototype. It will shut down after the semester.

## 11. Changes

Version 2 (2026-11-18), after three test runs with agents that had only version 1:

- Section 2 gives a setup command for the signature library. One test agent could not install a library and wrote its own Ed25519 code.
- Section 6 says what to pass on to the user. One test agent quoted verified sentences and left out the sources of each sentence.
- Section 7: a resend of a first message with no `contextId` now gets the first reply again. In version 1 of the service it created a second package.
