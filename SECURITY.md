# Security

- Do not commit `.env`, database files, uploaded documents, Gmail App Passwords, or real user data.
- Set a strong unique `SECRET_KEY` in the deployment environment.
- Create management accounts with environment variables and `flask --app app init-db`.
- Change all initial passwords immediately after first login.
- Keep `FLASK_DEBUG=0` in production.
