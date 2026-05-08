"""
app/cloud/ssh_executor — SSH connection helper for cloud VM bootstrap.

Ported from kast/kast/scripts/ssh_executor.py with these adaptations:
  - Logger via Flask current_app.logger instead of kast's logger.
  - SSH key material comes from CloudCredential fields (decrypted by the caller)
    rather than from ~/.ssh/ on the kast CLI host.

Used by CloudProvider.provision() to verify the VM is reachable and ZAP
is running before returning to the orchestrator.
"""

import socket
import time
from pathlib import Path

import paramiko
from flask import current_app


class SshExecutor:
    """Manages an SSH connection to a provisioned cloud VM.

    Args:
        host: IP address or hostname of the target VM.
        key_path: Local filesystem path to the SSH private key file.
        user: SSH username (e.g. 'ubuntu', 'ec2-user', 'azureuser').
        port: SSH port, default 22.
    """

    def __init__(self, host: str, key_path: str, user: str, port: int = 22):
        self.host = host
        self.key_path = Path(key_path)
        self.user = user
        self.port = port
        self._client = None
        self._sftp = None

    def _log(self, msg: str) -> None:
        current_app.logger.info("[SshExecutor %s@%s:%s] %s", self.user, self.host, self.port, msg)

    def connect(self, timeout: int = 30) -> None:
        """Open an SSH connection to the host.

        Args:
            timeout: Connection timeout in seconds.

        Raises:
            ConnectionError: if the connection cannot be established.
        """
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            private_key = paramiko.RSAKey.from_private_key_file(str(self.key_path))
            client.connect(
                hostname=self.host,
                port=self.port,
                username=self.user,
                pkey=private_key,
                timeout=timeout,
                banner_timeout=60,
                auth_timeout=30,
            )
            self._client = client
            self._sftp = client.open_sftp()
            self._log("connected")
        except Exception as exc:
            raise ConnectionError(
                f"SSH connect to {self.user}@{self.host}:{self.port} failed: {exc}"
            ) from exc

    def run_command(self, command: str, timeout: int = 60) -> tuple[int, str, str]:
        """Run a command over SSH and return its exit code and output.

        Args:
            command: Shell command to execute on the remote host.
            timeout: Command timeout in seconds.

        Returns:
            Tuple of (exit_code, stdout, stderr).

        Raises:
            RuntimeError: if the SSH connection is not open.
        """
        if not self._client:
            raise RuntimeError("SSH client is not connected")
        _, stdout, stderr = self._client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        return (
            exit_code,
            stdout.read().decode("utf-8", errors="replace"),
            stderr.read().decode("utf-8", errors="replace"),
        )

    def upload_file(self, local_path: str, remote_path: str) -> None:
        """Upload a file to the remote host via SFTP.

        Args:
            local_path: Absolute path to the local file.
            remote_path: Absolute path for the destination on the remote host.

        Raises:
            RuntimeError: if the SSH connection is not open or upload fails.
        """
        if not self._sftp:
            raise RuntimeError("SFTP channel not open")
        try:
            self._sftp.put(str(local_path), remote_path)
            self._log(f"uploaded {local_path} → {remote_path}")
        except Exception as exc:
            raise RuntimeError(f"SFTP upload failed: {exc}") from exc

    def wait_for_port(self, port: int, timeout: int = 300, interval: int = 5) -> None:
        """Poll until a TCP port on the host is accepting connections.

        Used to wait for SSH (port 22) or ZAP (port 8080) to open after boot.

        Args:
            port: TCP port to poll.
            timeout: Maximum total wait time in seconds.
            interval: Seconds between poll attempts.

        Raises:
            TimeoutError: if the port does not open within timeout.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with socket.create_connection((self.host, port), timeout=5):
                    self._log(f"port {port} open")
                    return
            except OSError:
                time.sleep(interval)
        raise TimeoutError(
            f"Port {port} on {self.host} did not open within {timeout}s"
        )

    def close(self) -> None:
        """Close the SSH connection if open."""
        if self._sftp:
            try:
                self._sftp.close()
            except Exception:
                pass
            self._sftp = None
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
