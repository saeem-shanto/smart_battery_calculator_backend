# Smart Battery Calculator Backend v1.5.8.1

## Fix

Corrected the password-reset email HTML escaping call in `apps/accounts/security.py`.

Previous code:

```python
html_url = escape(url, quote=True)
```

Correct code:

```python
html_url = escape(url)
```

`django.utils.html.escape()` does not accept a `quote` keyword argument. Django's helper already performs safe HTML escaping suitable for the reset-link attribute.

## Scope

No API contract, database schema, 2FA logic, password-reset token logic, calculation engine, Supabase integration, or MATLAB source was changed.

## Verification

- 116 Python files compile successfully.
- No remaining `escape(..., quote=...)` usages exist.
- MATLAB source hashes remain unchanged.
- Full Django test execution should be run in the project's installed virtual environment.
