# Open API Cookie Local Expiry Design

## Goal

When the account opens the C5 `open-api` page for IP allow-list binding, reuse the saved browser profile without forcing a re-login when the browser has stopped sending locally expired C5 cookies even though the stored token value is still usable.

## Confirmed Constraints

- Only use the existing native Edge/browser-runtime path.
- Do not touch the purchase path or `accounts.cookie_raw`.
- Do not fabricate a new token or add cookie auto-refresh logic.
- Do not break the current `clone -> launch -> cleanup/persist` mechanism.

## Approach

The launcher already clones the account profile into a temporary session before opening the `open-api` page. The new behavior stays inside that temporary session:

1. Clone the account profile as before.
2. Before launching Edge, open the cloned Chromium cookie store and extend the local expiry metadata for existing `c5game.com` cookies to a future time.
3. Launch the browser with the prepared temporary session.
4. Keep the existing cleanup and persistence behavior unchanged.

This is intentionally a local expiry refresh, not a new token injection. Cookie values remain unchanged. The purpose is only to keep the native browser willing to send the already-saved C5 cookies.

## Storage Details

- Prefer Chromium's active cookie DB at `Default/Network/Cookies`.
- Also check `Default/Cookies` as a compatibility fallback.
- Only update rows if the `cookies` table exists.
- Update local persistence fields only: `expires_utc`, `has_expires`, `is_persistent`.

## Failure Policy

If the temporary cookie-store preparation fails, the launcher should log the failure and continue opening the page with the existing behavior. This keeps the current mechanism intact and avoids turning the enhancement into a new hard blocker.

## Verification

- Unit-test that preparing a cloned session updates only `c5game.com` cookie expiry rows and leaves unrelated domains unchanged.
- Unit-test that the `open-api` launcher asks the profile store to prepare the cloned session before launching Edge.
