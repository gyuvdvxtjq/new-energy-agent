"""Minimal SSH execution channel (route 2 for the first real DFT run).

Design limits, on purpose:
  * all credentials come from the environment (.env), never hardcoded:
    key auth via NEAGENT_SSH_KEY, or password auth via NEAGENT_SSH_PASSWORD
    (paramiko path — OpenSSH cannot take a password non-interactively)
  * this module is for THIS project's runs on a user-provided machine;
    it is not a general remote-execution toolkit
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


class SshConfigError(RuntimeError):
    pass


def config_from_env() -> dict[str, str]:
    cfg = {
        "host": os.environ.get("NEAGENT_SSH_HOST", ""),
        "user": os.environ.get("NEAGENT_SSH_USER", "root"),
        "port": os.environ.get("NEAGENT_SSH_PORT", "22"),
        "key": os.environ.get("NEAGENT_SSH_KEY", ""),
        "password": os.environ.get("NEAGENT_SSH_PASSWORD", ""),
    }
    missing = [k for k, v in cfg.items() if not v and k not in ("key", "password")]
    if missing or (not cfg["key"] and not cfg["password"]):
        raise SshConfigError(
            "SSH channel not configured: set NEAGENT_SSH_HOST/USER/PORT and "
            "NEAGENT_SSH_KEY or NEAGENT_SSH_PASSWORD in .env"
        )
    return cfg


def _client():
    import warnings
    warnings.filterwarnings("ignore")
    import paramiko
    cfg = config_from_env()
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(cfg["host"], port=int(cfg["port"]), username=cfg["user"],
              password=cfg["password"] or None,
              key_filename=cfg["key"] or None, timeout=30)
    return c


def _password_auth() -> bool:
    return bool(os.environ.get("NEAGENT_SSH_PASSWORD", ""))


def _put_via_stdin(local: Path, remote: str) -> dict[str, str]:
    """Fallback upload: stream through an exec channel's stdin.

    Some hosts (e.g. nodes whose .bashrc prints an environment banner)
    corrupt the SFTP handshake; exec channels are unaffected because we only
    write to stdin and read stderr.
    """
    with _client() as c:
        chan = c.get_transport().open_session()
        chan.exec_command(f"cat > {remote}")
        with open(local, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                chan.sendall(chunk)
        chan.shutdown_write()
        code = chan.recv_exit_status()
        err = b""
        while True:
            data = chan.recv_stderr(65536)
            if not data:
                break
            err += data
        return {"ok": code == 0, "stdout": "", "stderr": err.decode(errors="replace")}


def _get_via_base64(remote: str, local: Path) -> dict[str, str]:
    """Fallback download: base64 with a marker to skip any shell banner."""
    import base64
    with _client() as c:
        _, out, err = c.exec_command(f"echo __NEAGENT_B64__; base64 -w0 {remote}")
        text = out.read().decode(errors="replace")
        errs = err.read().decode(errors="replace")
    if "__NEAGENT_B64__" not in text:
        return {"ok": False, "stdout": "", "stderr": errs[:500]}
    b64 = text.split("__NEAGENT_B64__", 1)[1].strip()
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_bytes(base64.b64decode(b64))
    return {"ok": True, "stdout": "", "stderr": ""}


def run(command: str, timeout: int = 120) -> dict[str, str]:
    """Run one shell command on the remote host."""
    if _password_auth():
        with _client() as c:
            _, out, err = c.exec_command(command, timeout=timeout)
            code = out.channel.recv_exit_status()
            return {"ok": code == 0, "stdout": out.read().decode(),
                    "stderr": err.read().decode()}
    cfg = config_from_env()
    args = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
            "-p", cfg["port"]]
    if cfg["key"]:
        args += ["-i", cfg["key"]]
    r = subprocess.run(args + [f"{cfg['user']}@{cfg['host']}", command],
                       capture_output=True, text=True, timeout=timeout)
    return {"ok": r.returncode == 0, "stdout": r.stdout, "stderr": r.stderr}


def upload(local: Path, remote: str) -> dict[str, str]:
    if _password_auth():
        try:
            with _client() as c:
                c.open_sftp().put(str(local), remote)
            return {"ok": True, "stdout": "", "stderr": ""}
        except Exception:
            return _put_via_stdin(Path(local), remote)
    cfg = config_from_env()
    args = ["scp", "-P", cfg["port"]]
    if cfg["key"]:
        args += ["-i", cfg["key"]]
    r = subprocess.run(args + [str(local), f"{cfg['user']}@{cfg['host']}:{remote}"],
                       capture_output=True, text=True, timeout=300)
    return {"ok": r.returncode == 0, "stdout": r.stdout, "stderr": r.stderr}


def download(remote: str, local: Path) -> dict[str, str]:
    local = Path(local)
    local.parent.mkdir(parents=True, exist_ok=True)
    if _password_auth():
        try:
            with _client() as c:
                c.open_sftp().get(remote, str(local))
            return {"ok": True, "stdout": "", "stderr": ""}
        except Exception:
            return _get_via_base64(remote, local)
    cfg = config_from_env()
    args = ["scp", "-P", cfg["port"]]
    if cfg["key"]:
        args += ["-i", cfg["key"]]
    r = subprocess.run(args + [f"{cfg['user']}@{cfg['host']}:{remote}", str(local)],
                       capture_output=True, text=True, timeout=600)
    return {"ok": r.returncode == 0, "stdout": r.stdout, "stderr": r.stderr}
