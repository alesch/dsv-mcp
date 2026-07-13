# DSV / DB Schenker public tracking — reverse-engineered API notes

Source: HAR capture of `https://www.dsv.com/mydsv/tracking-public/?language_region=en-GB_GB&refNumber=3476236157`
(`https://www.dbschenker.com/app/tracking-public/` redirects here). Captured 2026-07-13.

## Entry point

- `https://www.dbschenker.com/app/tracking-public/` → 302 → `https://www.dsv.com/mydsv/tracking-public/`
- Query params: `language_region` (e.g. `en-GB_GB`), `refNumber` (the number the user searches by, e.g. a waybill number like `3476236157`).
- The page is an Angular micro-frontend (`nges-portal`) served from `www.dsv.com`. Static JS/CSS assets are served from `cdn.eschenker.dbschenker.com/app/tracking-public/cdn/*` and `cdn.eschenker.dbschenker.com/app/shell/cdn/*`.
- On load, a cookie-consent banner from `policy.app.cookieinformation.com` must be accepted before the app proceeds.

## Backend

All tracking calls are same-origin, under `https://www.dsv.com/nges-portal/api/public/tracking-public/`. Config extracted from the `main.*.js` bundle:

```js
{
  backendUrl: "/nges-portal/api/public/tracking-public",
  publicTrackingBackendUrl: "/nges-portal/api/public/tracking/v1",
  publicTrackingBaseUrl: "https://mydsv.dsv.com/app/tracking-public",
  backendApiVersion: "4",
}
```

Requests carry a header `X-Version: 4`.

### 1. Resolve a reference → shipment id

```
GET /nges-portal/api/public/tracking-public/shipments?query=<refNumber>
```

Response:

```json
{
  "result": [
    {
      "id": "LandStt:SESOE620172194:CTTS:LAND",
      "stt": "SESOE620172194",
      "transportMode": "LAND",
      "percentageProgress": 100,
      "lastEventCode": "DLV",
      "fromLocation": "Norsborg",
      "toLocation": "Växjö",
      "startDate": "2026-05-15T00:00:00Z",
      "endDate": "2026-05-18T00:00:00Z",
      "consignment": null,
      "additionalReferenceValues": null,
      "isXpress": false,
      "swedenViewAvailable": true
    }
  ],
  "warnings": []
}
```

`id` is the key used for the next calls. Its shape is `<TransportMode>Stt:<sttNumber>:<something>:<TRANSPORT_MODE>` — only `LAND` was observed in this capture; other transport modes (air/sea, `Hbl`/`Hawb` references etc. — see `reference-types` below) presumably follow an analogous `id` scheme (e.g. `AirHawb:...` / `SeaHbl:...`) but this hasn't been confirmed against a real shipment.

When the query matches nothing, `result` is an empty array (this is the "not found" case — no 404, still `200`).

### 2. Shipment detail

```
GET /nges-portal/api/public/tracking-public/shipments/land/<id>
```

(the `land` path segment matches `transportMode` from step 1, lowercased)

Response (truncated — full example also has `location.deliverTo`/`shipperPlace`/`consigneePlace` fields):

```json
{
  "sttNumber": "SESOE620172194",
  "references": {
    "shipper": ["57439 /"],
    "consignee": [],
    "waybillAndConsignementNumbers": ["3476236157"],
    "additionalReferences": [],
    "originalStt": null
  },
  "goods": {
    "pieces": 1,
    "volume": {"value": 0.004, "unit": "CBM"},
    "weight": {"value": 0.8, "unit": "KGS"},
    "dimensions": [],
    "loadingMeters": {"value": 0.0, "unit": "MTR"}
  },
  "events": [
    {"code": "COL", "date": "2026-05-15T14:00:00+02:00", "location": {"name": "Norsborg", "code": "SOE", "countryCode": "SE"}, "comment": "Collected"},
    {"code": "ENM", "date": "2026-05-15T14:01:00+02:00", "location": {"name": "Södertälje", "code": "SOE", "countryCode": "SE"}, "comment": "Arrived"},
    {"code": "ENT", "date": "2026-05-15T14:33:16+02:00", "location": {"name": "Södertälje", "code": "SOE", "countryCode": "SE"}, "comment": "Booked"},
    {"code": "MAN", "date": "2026-05-15T16:42:37+02:00", "location": {"name": "Södertälje", "code": "SOE", "countryCode": "SE"}, "comment": "Departed"},
    {"code": "ENM", "date": "2026-05-18T01:40:08+02:00", "location": {"name": "Växjö", "code": "VXO", "countryCode": "SE"}, "comment": "Arrived"},
    {"code": "DOT", "date": "2026-05-18T08:35:08+02:00", "location": {"name": "Växjö", "code": "VXO", "countryCode": "SE"}, "comment": "Out for Delivery"},
    {"code": "DLV", "date": "2026-05-18T10:57:31+02:00", "location": {"name": "Växjö", "code": "VXO", "countryCode": "SE"}, "comment": "Delivered"}
  ],
  "packages": [
    {"id": "573313432228982422", "events": [ /* subset of the events above, per-package */ ]}
  ],
  "product": "DSVparcel",
  "transportMode": "LAND",
  "deliveryDate": {"estimated": "2026-05-18T00:00:00Z", "agreed": null},
  "progressBar": {
    "steps": ["BOOKED", "TRANSPORTATION", "DISPATCHING_CENTER", "IN_DELIVERY", "DELIVERED"],
    "activeStep": "DELIVERED"
  },
  "location": {
    "collectFrom": {"countryCode": "SE", "country": "Sweden", "city": "Norsborg", "postCode": "14563"},
    "deliverTo": {"countryCode": "SE", "country": "Sweden", "city": "Växjö", "postCode": "35250"}
  }
}
```

`progressBar.activeStep` is the best single field for "current status". `events[].code` is a small controlled vocabulary (`COL`=Collected, `ENM`=Arrived at facility, `ENT`=Booked, `MAN`=Departed, `DOT`=Out for Delivery, `DLV`=Delivered — inferred from `comment`, not exhaustive).

### 3. Trip / map points

```
GET /nges-portal/api/public/tracking-public/shipments/land/<id>/trip
```

```json
{
  "start": {"name": null, "latitude": 59.22888181, "longitude": 17.840829818},
  "end": {"name": null, "latitude": 56.914394339, "longitude": 14.73500537},
  "trip": [
    {"lastEventCode": "COL", "lastEventDate": "2026-05-15T14:00:00+02:00", "latitude": 59.22888181, "longitude": 17.840829818},
    {"lastEventCode": "ENM", "lastEventDate": "2026-05-15T14:01:00+02:00", "latitude": 59.197360959, "longitude": 17.623899516},
    {"lastEventCode": "DLV", "lastEventDate": "2026-05-18T10:57:31+02:00", "latitude": 56.914394339, "longitude": 14.73500537}
  ],
  "isDelivered": true
}
```

Used to render the map; optional for a text-only MCP tool.

### 4. Reference types (validation metadata)

```
GET /nges-portal/api/public/tracking-public/reference-types
```

Returns an array of `{referenceType, allowedPattern}`, e.g. `Stt`, `WaybillNo`, `ShippersRefNo`, `PackageId`, `ConsigneesRefNo`, `Hawb` (air), `BookingId`, `Hbl` (sea), `ContainerNo`, `COS`, etc., each with a regex for valid input. Useful for client-side validation of what a user types before submitting, and a hint at which reference types/transport modes exist beyond the `LAND`/`Stt` case captured here.

## Anti-bot: proof-of-work challenge

**Every** `nges-portal/api/public/tracking-public/*` call returned **HTTP 429** on the first attempt in this capture, including on internal navigations that had already "warmed up" earlier in the session. The 429 response carries:

- Header `captcha-puzzle`: base64-encoded, comma-separated list of 3 JWTs (`alg: HS256`). Each JWT payload looks like:

  ```json
  {"puzzle": "AAAAAADdnJqlouy5tiEKAAAAAAAAAAAAAAAAAAAAAABnp3iHl6EEitOaLepAhlbS0PMsVjxCLgRIKRaCpBCSTQ==", "iat": 1783938576, "exp": 1783938636}
  ```

  (60-second expiry). This matches the Friendly Captcha proof-of-work puzzle format.

The retried request then succeeds (`200`) once it carries a request header:

- `Captcha-Solution`: base64 JSON array of `{"jwt": "<same JWT as one of the puzzles>", "solution": "<base64 8-byte nonce>"}`, one entry per puzzle.

The site's own client-side JS (bundled in the shell/tracking-public bundles) solves these puzzles — it's a proof-of-work brute-force search for a nonce, done in-browser, not a visual/interactive CAPTCHA. No third-party CAPTCHA domain (e.g. `*.friendlycaptcha.com`) is contacted in this capture — the puzzle is issued and verified same-origin (`www.dsv.com`), proxied through their own backend.

### Implication for automation

We deliberately **do not** reimplement the puzzle-solving algorithm. Doing so would mean building a standalone anti-bot bypass tool, decoupled from an actual browser session — that's a different (and more sensitive) thing than automating a real browser. Instead, this project drives an actual Chromium instance via Playwright so the site's own JS solves its own challenge, exactly as it would for any human visitor, and we read the resulting JSON responses off the network. Requests are paced (delays, no concurrency) to resemble a single human user browsing, not to defeat the challenge itself.

## Other endpoints seen (not needed for tracking)

- `POST /nges-portal/api/public/microfrontend/translate/keys` — i18n string bundles for the UI.
- `GET /nges-portal/api/visitor/user-settings/context/app-context` — app bootstrap/context.
- `POST /nges-portal/api/public/user-experience/entry/tracking-public` and `POST .../action/tracking-public/tracking/CTTS` — analytics/UX event beacons, not required to fetch tracking data.
- `GET /nges-portal/api/public/openstreetmap/*` — map tiles/styles for the trip map, not required for a text-only client.
