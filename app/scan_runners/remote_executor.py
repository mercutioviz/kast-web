"""
app/scan_runners/remote_executor — execute kast scans on a remote VM over SSH.

The remote runner runs kast with the same argv shape that would have been used
locally; results are rsynced back to the kast-web host so the existing
post-processing in execute_scan_task continues unchanged. The kast<->kast-web
file-format contract is preserved end-to-end because kast itself is unchanged.
"""

import io
import os
import select
import shlex
import subprocess
import tempfile
import time
from pathlib import Path

import paramiko
from flask import current_app

from app.encryption import decrypt_value


SSH_CONNECT_TIMEOUT = 15
SCAN_EXEC_TIMEOUT = 3600  # 1 hour, matches local path


def _load_pkey(blob: str):
    """Try the common key formats. Returns a paramiko PKey or raises ValueError."""
    candidates = [paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey]
    dss = getattr(paramiko, 'DSSKey', None)
    if dss is not None:
        candidates.append(dss)
    for cls in candidates:
        try:
            return cls.from_private_key(io.StringIO(blob))
        except paramiko.SSHException:
            continue
    raise ValueError("Could not parse SSH private key in any supported format (Ed25519/RSA/ECDSA/DSS)")


def _decrypt_runner_key(runner):
    blob = decrypt_value(runner.ssh_private_key_encrypted)
    if not blob:
        raise ValueError("Failed to decrypt runner SSH private key")
    return blob


class _KeyFile:
    """Context manager: write decrypted key to a tmpfile (mode 0600), delete on exit."""
    def __init__(self, blob: str):
        self.blob = blob
        self.path = None

    def __enter__(self):
        fd, path = tempfile.mkstemp(prefix='kast-runner-key-', suffix='.pem')
        try:
            os.write(fd, self.blob.encode())
        finally:
            os.close(fd)
        os.chmod(path, 0o600)
        self.path = path
        return path

    def __exit__(self, exc_type, exc, tb):
        if self.path and os.path.exists(self.path):
            try:
                os.unlink(self.path)
            except OSError:
                pass


def test_runner(runner) -> dict:
    """Probe a runner: SSH in, check kast version, ensure output dir is writable.

    Returns a dict with success/error/kast_version fields for the admin UI.
    """
    try:
        blob = _decrypt_runner_key(runner)
        pkey = _load_pkey(blob)
    except Exception as exc:
        return {'success': False, 'error': f'Key decode failed: {exc}'}

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=runner.hostname,
            port=runner.port,
            username=runner.username,
            pkey=pkey,
            timeout=SSH_CONNECT_TIMEOUT,
            banner_timeout=30,
            auth_timeout=15,
        )
    except Exception as exc:
        return {'success': False, 'error': f'SSH connect failed: {exc}'}

    try:
        kast_q = shlex.quote(runner.kast_binary_path)
        out_q = shlex.quote(runner.remote_output_root)
        cmd = f'{kast_q} --version 2>&1 && mkdir -p {out_q} && test -w {out_q} && echo OK'
        _, stdout, stderr = client.exec_command(cmd, timeout=20)
        rc = stdout.channel.recv_exit_status()
        out = stdout.read().decode('utf-8', errors='replace').strip()
        err = stderr.read().decode('utf-8', errors='replace').strip()
        if rc != 0:
            return {'success': False, 'error': f'Probe command failed (rc={rc}): {err or out}'}
        version = 'unknown'
        for line in out.splitlines():
            if 'KAST version' in line or line.lower().startswith('kast '):
                version = line.strip()
                break
        return {'success': True, 'kast_version': version, 'output': out}
    finally:
        try:
            client.close()
        except Exception:
            pass


def _stream_to_log(channel, log_file_path: str, max_wait: int) -> int:
    """Read combined stdout/stderr from a paramiko channel into the local log file.

    Returns the remote command's exit status.
    """
    deadline = time.monotonic() + max_wait
    buf = b''
    with open(log_file_path, 'ab') as log:
        log.write(b'\n=== REMOTE EXECUTION OUTPUT ===\n')
        log.flush()
        while True:
            if time.monotonic() > deadline:
                channel.close()
                log.write(b'\n=== REMOTE EXECUTION TIMED OUT ===\n')
                return 124  # convention: 124 = timeout

            if channel.recv_ready():
                chunk = channel.recv(65536)
                if chunk:
                    buf += chunk
                    while b'\n' in buf:
                        line, buf = buf.split(b'\n', 1)
                        log.write(line + b'\n')
                        log.flush()

            if channel.exit_status_ready() and not channel.recv_ready():
                # drain anything left
                while channel.recv_ready():
                    chunk = channel.recv(65536)
                    if chunk:
                        buf += chunk
                if buf:
                    log.write(buf)
                    log.flush()
                return channel.recv_exit_status()

            # avoid busy-loop when no data
            select.select([channel], [], [], 0.5)


def _rsync_pull(key_path: str, runner, remote_dir: str, local_dir: Path) -> tuple[int, str]:
    """rsync the remote results directory back to local. Returns (rc, log_output)."""
    local_dir.mkdir(parents=True, exist_ok=True)
    ssh_cmd = (
        f'ssh -i {shlex.quote(key_path)} '
        f'-o StrictHostKeyChecking=accept-new '
        f'-o ConnectTimeout=15 '
        f'-p {runner.port}'
    )
    rsync_cmd = [
        'rsync', '-az', '--timeout=60',
        '-e', ssh_cmd,
        f'{runner.username}@{runner.hostname}:{remote_dir.rstrip("/")}/',
        str(local_dir).rstrip('/') + '/',
    ]
    current_app.logger.info(f'[remote_executor] rsync: {" ".join(rsync_cmd)}')
    proc = subprocess.run(rsync_cmd, capture_output=True, text=True, timeout=900)
    return proc.returncode, (proc.stdout + proc.stderr)


def run_remote_scan(
    scan,
    runner,
    cmd: list,
    local_output_dir: Path,
    log_file_path: str,
    env_extra: dict | None = None,
) -> dict:
    """Execute kast on a remote runner, stream output to the local log, rsync results back.

    Args:
        scan: the Scan row being executed (used for the remote per-scan subdir).
        runner: the ScanRunner row.
        cmd: the local kast command list as built by execute_scan_task. The
            '-o <local_output_dir>' segment is rewritten to point at the
            remote per-scan directory; everything else passes through unchanged.
        local_output_dir: the local Path where results are expected after rsync.
        log_file_path: the local execution log file (append-only).
        env_extra: optional env vars (e.g. KAST_AI_API_KEY) to prepend to the
            remote command — SSH daemons typically reject SendEnv for arbitrary
            vars, so inlining is more reliable.

    Returns:
        dict with success (bool), returncode (int), error (str|None), and
        the path to the local results dir (after rsync).
    """
    # Rewrite -o <local_dir> to -o <remote_dir>
    remote_scan_dir = f'{runner.remote_output_root.rstrip("/")}/scan-{scan.id}'
    remote_cmd = []
    skip_next = False
    for i, part in enumerate(cmd):
        if skip_next:
            remote_cmd.append(shlex.quote(remote_scan_dir))
            skip_next = False
            continue
        if part == '-o':
            remote_cmd.append('-o')
            skip_next = True
            continue
        remote_cmd.append(shlex.quote(part))

    if skip_next:
        # cmd ended on '-o' with no value — pathological, refuse
        return {'success': False, 'returncode': 1, 'error': "Malformed command: '-o' with no value", 'output_dir': str(local_output_dir)}

    # Inline env vars; runner needs them since most sshd configs reject SendEnv
    env_prefix = ''
    if env_extra:
        env_prefix = ' '.join(f'{k}={shlex.quote(v)}' for k, v in env_extra.items() if v) + ' '

    # mkdir the remote output dir, then run kast
    full_remote_cmd = (
        f'mkdir -p {shlex.quote(remote_scan_dir)} && '
        f'cd {shlex.quote(remote_scan_dir)} && '
        f'{env_prefix}{" ".join(remote_cmd)}'
    )

    current_app.logger.info(
        f'[remote_executor] runner={runner.name} ({runner.username}@{runner.hostname}:{runner.port}) '
        f'remote_dir={remote_scan_dir}'
    )
    current_app.logger.debug(f'[remote_executor] remote command: {full_remote_cmd}')

    try:
        blob = _decrypt_runner_key(runner)
        pkey = _load_pkey(blob)
    except Exception as exc:
        return {'success': False, 'returncode': 1, 'error': f'Runner key decrypt failed: {exc}', 'output_dir': str(local_output_dir)}

    with _KeyFile(blob) as key_path:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=runner.hostname,
                port=runner.port,
                username=runner.username,
                pkey=pkey,
                timeout=SSH_CONNECT_TIMEOUT,
                banner_timeout=30,
                auth_timeout=15,
            )
        except Exception as exc:
            return {
                'success': False,
                'returncode': 1,
                'error': f'SSH connect to {runner.hostname}:{runner.port} failed: {exc}',
                'output_dir': str(local_output_dir),
            }

        try:
            with open(log_file_path, 'a') as log:
                log.write(f'\n[remote_executor] runner: {runner.name} ({runner.username}@{runner.hostname}:{runner.port})\n')
                log.write(f'[remote_executor] remote output dir: {remote_scan_dir}\n')
                log.flush()

            transport = client.get_transport()
            channel = transport.open_session()
            channel.set_combine_stderr(True)
            channel.exec_command(full_remote_cmd)

            rc = _stream_to_log(channel, log_file_path, SCAN_EXEC_TIMEOUT)
            current_app.logger.info(f'[remote_executor] remote kast exit code: {rc}')

            # rsync the results back regardless of rc — partial results are still useful
            rsync_rc, rsync_log = _rsync_pull(key_path, runner, remote_scan_dir, local_output_dir)
            with open(log_file_path, 'a') as log:
                log.write(f'\n[remote_executor] rsync rc={rsync_rc}\n')
                if rsync_rc != 0:
                    log.write(rsync_log + '\n')

            # best-effort remote cleanup; never let this fail the scan
            try:
                _, sout, _ = client.exec_command(f'rm -rf {shlex.quote(remote_scan_dir)}', timeout=10)
                sout.channel.recv_exit_status()
            except Exception as cleanup_exc:
                current_app.logger.warning(f'[remote_executor] remote cleanup failed: {cleanup_exc}')

            return {
                'success': rc == 0 and rsync_rc == 0,
                'returncode': rc,
                'error': None if (rc == 0 and rsync_rc == 0) else f'kast rc={rc}, rsync rc={rsync_rc}',
                'output_dir': str(local_output_dir),
            }
        finally:
            try:
                client.close()
            except Exception:
                pass
