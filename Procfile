# Procfile (REQUIRED - Create this file in your root directory)
web: gunicorn app:app --bind 0.0.0.0:$PORT

# railway.json (OPTIONAL - Alternative configuration)
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "gunicorn app:app --bind 0.0.0.0:$PORT",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}

# nixpacks.toml (OPTIONAL - More control over build)
[phases.setup]
nixPkgs = ["python311", "postgresql_16", "gcc"]

[phases.install]
cmds = ["python -m venv /opt/venv && . /opt/venv/bin/activate && pip install -r requirements.txt"]

[start]
cmd = "gunicorn app:app --bind 0.0.0.0:$PORT"

# runtime.txt (OPTIONAL - Specify Python version)
python-3.11.7