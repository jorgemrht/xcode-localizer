# Key Convention

Use:

```text
{screen}_{element}_{meaning}
```

`screen` is `common` or a screen name provided in the user request, normalized to snake_case. If the user does not provide a screen name, use `common`. Do not infer it from code or filenames.

Examples:

```text
Login -> login
Profile -> profile
Settings notifications -> settings_notifications
```

`element` must be one of:

```text
button
text
label
title
subtitle
placeholder
error
success
warning
alert
message
navigation_title
toolbar
tab
toggle
link
picker
context_menu
empty_state
accessibility_label
accessibility_hint
```

`meaning` is semantic English, not a literal UI type. Prefer verbs for actions and nouns for labels:

```text
sign_in
create_account
forgot_password
email
password
invalid_password
notifications
version
```

Good keys:

```text
login_button_sign_in
login_button_login
login_text_username
login_placeholder_email
login_error_invalid_password
common_button_cancel
settings_title_notifications
profile_text_version
```

Avoid:

```text
screen_btn_login
login_button_button
login_text_iniciar_sesion
login_label_1
```

When in doubt, use the best semantic key from the user request. Do not inspect app source files.

Element mapping:

```text
label -> label
button -> button
TextField placeholder -> placeholder
SecureField placeholder -> placeholder
error message -> error
success message -> success
screen title -> title
NavigationStack title -> navigation_title
ToolbarItem text -> toolbar
Tab label -> tab
accessibility text -> accessibility_label
accessibility hint -> accessibility_hint
```

For the natural-language request "in the Login screen, the username label is username in English and usuario in Spanish, and the login button is login in English and iniciar sesion in Spanish", use:

```text
login_text_username
login_button_login
```

Do not use:

```text
username
login
screen_btn_login
```
