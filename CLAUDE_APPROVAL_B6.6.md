# Claude Approval — B6.6

Status: **APPROVED**

Claude reviewed B6.6 People & User Management UI and confirmed:

- No backend regression was found.
- An administrator cannot deactivate the Person linked to their own account.
- `require_people_manage_for_person` correctly requires the actor to hold management access across every active organization relationship for a Person shared by multiple organizations.
- Password reset reuses the previously approved `assert_actor_dominates_user_access` privilege-dominance rule.
- B6.6 does not yet expose Role/Permission assignment UI; that sensitive boundary remains reserved for B6.8.

Non-blocking recommendation received from Claude and applied before Codex handoff:

- `UserPasswordResetRequest.new_password` now uses Pydantic `SecretStr` instead of a raw `str`, and the service unwraps the secret only at the password hashing boundary.
