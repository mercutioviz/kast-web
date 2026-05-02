"""
app/cloud/ssh_executor — SSH connection helper for cloud VM bootstrap.

Ported from kast/kast/scripts/ssh_executor.py with these adaptations:
  - Logger via Flask current_app.logger instead of kast's logger.
  - SSH key material comes from CloudCredential fields (decrypted by the caller)
    rather than from ~/.ssh/ on the kast CLI host.

Used by CloudProvider.provision() to verify the VM is reachable and ZAP
is running before returning to the orchestrator.
"""

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
        self.key_path = key_path
        self.user = user
        self.port = port
        self._client = None

    def connect(self, timeout: int = 30) -> None:
        """Open an SSH connection to the host.

        Args:
            timeout: Connection timeout in seconds.

        Raises:
            ConnectionError: if the connection cannot be established within timeout.
        """
        raise NotImplementedError("Will be implemented in D2 (ssh_executor port)")

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
        raise NotImplementedError("Will be implemented in D2 (ssh_executor port)")

    def upload_file(self, local_path: str, remote_path: str) -> None:
        """Upload a file to the remote host via SFTP.

        Args:
            local_path: Absolute path to the local file.
            remote_path: Absolute path for the destination on the remote host.

        Raises:
            RuntimeError: if the SSH connection is not open or upload fails.
        """
        raise NotImplementedError("Will be implemented in D2 (ssh_executor port)")

    def wait_for_port(self, port: int, timeout: int = 300, interval: int = 5) -> None:
        """Poll until a TCP port on the host is accepting connections.

        Used to wait for ZAP's HTTP port to open before returning to the caller.

        Args:
            port: TCP port to poll.
            timeout: Maximum total wait time in seconds.
            interval: Seconds between poll attempts.

        Raises:
            TimeoutError: if the port does not open within timeout.
        """
        raise NotImplementedError("Will be implemented in D2 (ssh_executor port)")

    def close(self) -> None:
        """Close the SSH connection if open."""
        raise NotImplementedError("Will be implemented in D2 (ssh_executor port)")
