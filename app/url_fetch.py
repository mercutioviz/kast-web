"""
SSRF-guarded outbound image fetching.

Used by the logo URL-import feature: a user pastes a URL and the server
fetches it on their behalf. That is the textbook SSRF setup, so every request
made here is constrained:

- http/https only, on an allowed port, with no credentials in the URL
- the hostname is resolved up front and EVERY resolved address must be a
  public, globally-routable unicast address
- the validated IP is pinned for the actual connection, so DNS cannot be
  rebound between the check and the connect; TLS SNI and certificate
  verification still use the real hostname
- redirects are followed manually, with every hop re-validated
- the response body is streamed with a hard byte cap and a wall-clock deadline

The Content-Type a server reports is recorded but never trusted. Callers hand
the bytes to app.logo_media.prepare_logo(), which sniffs magic bytes, so an
HTML error page simply fails later as "not a recognized image format".

Error messages are deliberately vague about internal network details so this
endpoint cannot be used to map the network.
"""

import ipaddress
import socket
import time
from urllib.parse import urljoin, urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.poolmanager import PoolManager

DEFAULT_ALLOWED_SCHEMES = ('http', 'https')
DEFAULT_ALLOWED_PORTS = (80, 443)
DEFAULT_MAX_REDIRECTS = 3
DEFAULT_CONNECT_TIMEOUT = 5
DEFAULT_READ_TIMEOUT = 10
DEFAULT_TOTAL_DEADLINE = 15
DEFAULT_MAX_BYTES = 5 * 1024 * 1024

REDIRECT_STATUSES = (301, 302, 303, 307, 308)

# Belt-and-braces alongside the ipaddress property checks below. Both the
# cloud metadata address and the CGNAT range have been classified
# inconsistently across Python versions, so they are named explicitly.
BLOCKED_NETWORKS = (
    ipaddress.ip_network('169.254.0.0/16'),   # link-local, incl. 169.254.169.254
    ipaddress.ip_network('100.64.0.0/10'),    # CGNAT
    ipaddress.ip_network('192.0.0.0/24'),     # IETF protocol assignments
    ipaddress.ip_network('198.18.0.0/15'),    # benchmarking
    ipaddress.ip_network('::ffff:0:0/96'),    # IPv4-mapped IPv6
    ipaddress.ip_network('64:ff9b::/96'),     # NAT64
    ipaddress.ip_network('2002::/16'),        # 6to4
    ipaddress.ip_network('fc00::/7'),         # unique local
)


class UrlFetchError(Exception):
    """A fetch was refused or failed. The message is safe to show a user."""


# ============================================================================
# ADDRESS VALIDATION
# ============================================================================

def is_public_address(ip_text):
    """
    True when an address is a public, globally-routable unicast address.

    Args:
        ip_text: address in string form

    Returns:
        bool
    """
    try:
        ip = ipaddress.ip_address(ip_text)
    except ValueError:
        return False

    if (ip.is_loopback or ip.is_private or ip.is_link_local
            or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
        return False

    if getattr(ip, 'is_site_local', False):  # deprecated IPv6 site-local
        return False

    for network in BLOCKED_NETWORKS:
        if ip.version == network.version and ip in network:
            return False

    return True


def _encode_host(host):
    """IDNA-encode a hostname, leaving ASCII hostnames untouched."""
    try:
        return host.encode('idna').decode('ascii')
    except (UnicodeError, UnicodeDecodeError):
        return host


def validate_url(url, allowed_schemes=DEFAULT_ALLOWED_SCHEMES,
                 allowed_ports=DEFAULT_ALLOWED_PORTS):
    """
    Check a URL's shape before any network activity happens.

    Returns:
        tuple: (scheme: str, host: str, port: int)

    Raises:
        UrlFetchError: with a user-facing message
    """
    if not url or not url.strip():
        raise UrlFetchError('Enter a URL.')

    url = url.strip()
    parts = urlsplit(url)

    if parts.scheme.lower() not in allowed_schemes:
        raise UrlFetchError(
            'Only http and https URLs can be imported.'
        )

    if parts.username or parts.password:
        raise UrlFetchError(
            'URLs containing credentials are not allowed.'
        )

    host = parts.hostname
    if not host:
        raise UrlFetchError('That URL has no hostname.')

    try:
        port = parts.port or (443 if parts.scheme.lower() == 'https' else 80)
    except ValueError:
        raise UrlFetchError('That URL has an invalid port.')

    if port not in allowed_ports:
        allowed = ', '.join(str(p) for p in allowed_ports)
        raise UrlFetchError(f'Only ports {allowed} can be imported from.')

    return (parts.scheme.lower(), _encode_host(host), port)


def resolve_public_ip(host, port):
    """
    Resolve a hostname and require every address it returns to be public.

    Resolving once and pinning the result is what closes the DNS-rebinding
    hole: a name that answers with a public address now cannot answer with
    127.0.0.1 a moment later, because the connection never resolves again.

    Args:
        host: hostname or address literal
        port: TCP port

    Returns:
        str: the address to connect to

    Raises:
        UrlFetchError
    """
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise UrlFetchError(f'Could not resolve "{host}".')

    if not infos:
        raise UrlFetchError(f'Could not resolve "{host}".')

    addresses = [info[4][0] for info in infos]

    for address in addresses:
        if not is_public_address(address):
            raise UrlFetchError(
                'That URL points to a private or internal address, '
                'which is not allowed.'
            )

    return addresses[0]


# ============================================================================
# IP-PINNED TRANSPORT
# ============================================================================

def _pinned_pool_classes(ip):
    """Build urllib3 pool classes that always connect to `ip`."""

    class PinnedHTTPConnection(HTTPConnection):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._dns_host = ip

    class PinnedHTTPSConnection(HTTPSConnection):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # conn.host proxies _dns_host, so capture the real hostname for
            # SNI and certificate verification BEFORE repointing DNS at the
            # IP. Without this the handshake would offer the IP as SNI and
            # validate the certificate against it.
            if not self.server_hostname:
                self.server_hostname = self.host
            self._dns_host = ip

    class PinnedHTTPConnectionPool(HTTPConnectionPool):
        ConnectionCls = PinnedHTTPConnection

    class PinnedHTTPSConnectionPool(HTTPSConnectionPool):
        ConnectionCls = PinnedHTTPSConnection

    return {'http': PinnedHTTPConnectionPool, 'https': PinnedHTTPSConnectionPool}


class PinnedIPAdapter(HTTPAdapter):
    """requests adapter that connects to a fixed IP regardless of DNS."""

    def __init__(self, ip, **kwargs):
        self._pinned_ip = ip
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize, block=block, **pool_kwargs
        )
        self.poolmanager.pool_classes_by_scheme = _pinned_pool_classes(self._pinned_ip)


def _pinned_session(ip, user_agent):
    """A session that connects only to `ip` and carries no ambient state."""
    session = requests.Session()
    session.trust_env = False      # ignore proxy / netrc env for this fetch
    # Note: do NOT set session.max_redirects here. requests builds the "next"
    # request even when allow_redirects=False, and a max_redirects of 0 makes
    # it raise TooManyRedirects for any 3xx -- which would bypass the per-hop
    # re-validation in fetch_remote_image. Redirects are bounded by the
    # max_redirects argument to fetch_remote_image instead.
    session.headers.clear()
    session.headers.update({
        'User-Agent': user_agent,
        'Accept': 'image/*,*/*;q=0.8',
    })
    adapter = PinnedIPAdapter(ip, max_retries=0)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


# ============================================================================
# FETCH
# ============================================================================

class FetchResult:
    """Outcome of a successful fetch."""

    def __init__(self, data, final_url, content_type, resolved_ip, redirects):
        self.data = data
        self.final_url = final_url
        self.content_type = content_type
        self.resolved_ip = resolved_ip
        self.redirects = redirects

    def __repr__(self):
        return (f'<FetchResult {len(self.data)}B {self.content_type!r} '
                f'from {self.final_url!r}>')


def _read_capped(response, max_bytes, deadline):
    """Stream a response body, aborting past max_bytes or the deadline."""
    declared = response.headers.get('Content-Length')
    if declared and declared.isdigit() and int(declared) > max_bytes:
        raise UrlFetchError(
            f'That image is too large. Maximum size is '
            f'{max_bytes // (1024 * 1024)}MB.'
        )

    chunks = []
    total = 0
    for chunk in response.iter_content(chunk_size=65536):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise UrlFetchError(
                f'That image is too large. Maximum size is '
                f'{max_bytes // (1024 * 1024)}MB.'
            )
        if time.monotonic() > deadline:
            raise UrlFetchError('Timed out downloading that URL.')
        chunks.append(chunk)

    return b''.join(chunks)


def fetch_remote_image(url, max_bytes=DEFAULT_MAX_BYTES,
                       allowed_schemes=DEFAULT_ALLOWED_SCHEMES,
                       allowed_ports=DEFAULT_ALLOWED_PORTS,
                       max_redirects=DEFAULT_MAX_REDIRECTS,
                       connect_timeout=DEFAULT_CONNECT_TIMEOUT,
                       read_timeout=DEFAULT_READ_TIMEOUT,
                       total_deadline=DEFAULT_TOTAL_DEADLINE,
                       user_agent='kast-web'):
    """
    Fetch an image from a user-supplied URL under the SSRF guard.

    Args:
        url: the URL to fetch
        max_bytes: hard cap on the response body
        allowed_schemes / allowed_ports: policy knobs
        max_redirects: redirect hops to follow, each re-validated
        connect_timeout / read_timeout: per-socket timeouts
        total_deadline: wall-clock budget for the whole operation
        user_agent: User-Agent header to send

    Returns:
        FetchResult

    Raises:
        UrlFetchError: with a message safe to show the user
    """
    deadline = time.monotonic() + total_deadline
    current_url = url.strip()
    redirects = []

    for hop in range(max_redirects + 1):
        if time.monotonic() > deadline:
            raise UrlFetchError('Timed out fetching that URL.')

        scheme, host, port = validate_url(current_url, allowed_schemes, allowed_ports)
        ip = resolve_public_ip(host, port)

        session = _pinned_session(ip, user_agent)
        try:
            response = session.get(
                current_url,
                headers={'Host': host},   # conn.host is the pinned IP now
                timeout=(connect_timeout, read_timeout),
                allow_redirects=False,
                stream=True,
            )
        except requests.exceptions.SSLError:
            raise UrlFetchError(
                'The HTTPS certificate for that site could not be verified.'
            )
        except requests.exceptions.Timeout:
            raise UrlFetchError('Timed out connecting to that URL.')
        except requests.exceptions.RequestException:
            raise UrlFetchError('Could not reach that URL.')

        try:
            if response.status_code in REDIRECT_STATUSES:
                location = response.headers.get('Location')
                if not location:
                    raise UrlFetchError('That URL redirected without a target.')
                if hop >= max_redirects:
                    raise UrlFetchError('That URL redirected too many times.')
                redirects.append(current_url)
                # Re-validated at the top of the next iteration.
                current_url = urljoin(current_url, location)
                continue

            if response.status_code != 200:
                raise UrlFetchError(
                    f'That URL returned HTTP {response.status_code}.'
                )

            data = _read_capped(response, max_bytes, deadline)
        finally:
            response.close()
            session.close()

        if not data:
            raise UrlFetchError('That URL returned an empty response.')

        return FetchResult(
            data=data,
            final_url=current_url,
            content_type=(response.headers.get('Content-Type') or '').split(';')[0].strip(),
            resolved_ip=ip,
            redirects=redirects,
        )

    raise UrlFetchError('That URL redirected too many times.')
