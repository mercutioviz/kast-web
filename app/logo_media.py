"""
Logo media handling for the report white-labeling feature.

Owns everything format-specific about uploaded logos:

- the registry of accepted graphic formats
- magic-byte content verification (an extension alone is never trusted)
- SVG sanitization (uploaded vectors are served from our own origin)
- raster normalization to PNG for formats the kast report renderer cannot
  reliably embed

Design note: kast's PDF renderer base64-embeds the logo and derives the MIME
type from the file extension, mapping only png/jpg/jpeg/gif/svg. Anything else
would be handed to WeasyPrint under a false MIME type. kast-web therefore keeps
the original upload for provenance and hands kast a "render derivative" that is
always either PNG or sanitized SVG.
"""

import gzip
import io
import re
import xml.etree.ElementTree as ET

# Defaults; overridable via Flask config (see config.py).
DEFAULT_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5MB
DEFAULT_MAX_DIMENSION = 2000  # longest edge, pixels

# Guard against decompression bombs. Pillow raises above this pixel count.
MAX_IMAGE_PIXELS = 50 * 1000 * 1000

SVG_NS = 'http://www.w3.org/2000/svg'
XLINK_NS = 'http://www.w3.org/1999/xlink'


# ============================================================================
# FORMAT REGISTRY
# ============================================================================

# key: canonical format id. Each entry lists the extensions that map to it.
LOGO_FORMATS = {
    'png': {
        'label': 'PNG',
        'extensions': ('png',),
        'mime': 'image/png',
        'kind': 'raster',
        'needs_normalize': False,
    },
    'jpeg': {
        'label': 'JPEG',
        'extensions': ('jpg', 'jpeg'),
        'mime': 'image/jpeg',
        'kind': 'raster',
        'needs_normalize': False,
    },
    'svg': {
        'label': 'SVG',
        'extensions': ('svg',),
        'mime': 'image/svg+xml',
        'kind': 'vector',
        'needs_normalize': False,
    },
    'svgz': {
        'label': 'SVGZ',
        'extensions': ('svgz',),
        'mime': 'image/svg+xml',
        'kind': 'vector',
        'needs_normalize': False,
    },
    'webp': {
        'label': 'WebP',
        'extensions': ('webp',),
        'mime': 'image/webp',
        'kind': 'raster',
        'needs_normalize': True,
    },
    'avif': {
        'label': 'AVIF',
        'extensions': ('avif',),
        'mime': 'image/avif',
        'kind': 'raster',
        'needs_normalize': True,
    },
    'gif': {
        'label': 'GIF',
        'extensions': ('gif',),
        'mime': 'image/gif',
        'kind': 'raster',
        'needs_normalize': True,
    },
    'bmp': {
        'label': 'BMP',
        'extensions': ('bmp',),
        'mime': 'image/bmp',
        'kind': 'raster',
        'needs_normalize': True,
    },
    'tiff': {
        'label': 'TIFF',
        'extensions': ('tif', 'tiff'),
        'mime': 'image/tiff',
        'kind': 'raster',
        'needs_normalize': True,
    },
    'ico': {
        'label': 'ICO',
        'extensions': ('ico',),
        'mime': 'image/x-icon',
        'kind': 'raster',
        'needs_normalize': True,
    },
}

# extension -> canonical format id
EXTENSION_MAP = {
    ext: fmt_id
    for fmt_id, spec in LOGO_FORMATS.items()
    for ext in spec['extensions']
}

ALLOWED_EXTENSIONS = tuple(sorted(EXTENSION_MAP))


def accept_attribute():
    """Value for the file input's accept attribute, e.g. '.png,.jpg,...'."""
    return ','.join('.' + ext for ext in ALLOWED_EXTENSIONS)


def format_list_text():
    """Human-readable list of supported formats for help text and errors."""
    return ', '.join(spec['label'] for spec in LOGO_FORMATS.values())


def extension_of(filename):
    """Lowercased extension without the dot, or '' when there isn't one."""
    if not filename or '.' not in filename:
        return ''
    return filename.rsplit('.', 1)[1].strip().lower()


def format_for_extension(ext):
    """Canonical format id for an extension, or None if unsupported."""
    return EXTENSION_MAP.get((ext or '').lower())


def format_label(mime_type, filename=None):
    """Best-effort display label (PNG, SVG, WebP...) for an existing logo."""
    fmt_id = format_for_extension(extension_of(filename or ''))
    if fmt_id:
        return LOGO_FORMATS[fmt_id]['label']
    for spec in LOGO_FORMATS.values():
        if spec['mime'] == mime_type:
            return spec['label']
    return (mime_type or 'unknown').split('/')[-1].upper()


# ============================================================================
# CONTENT SNIFFING
# ============================================================================

# How much of the file the SVG probe looks at. Design tools emit an XML
# declaration, a generator comment and often a DOCTYPE before the <svg> tag,
# which easily runs past the first few hundred bytes.
SVG_PROBE_BYTES = 8192


def _looks_like_svg(head):
    """True when the leading bytes plausibly open an SVG/XML document."""
    probe = head.lstrip(b'\xef\xbb\xbf').lstrip()
    if not probe.startswith(b'<'):
        return False
    return b'<svg' in head.lower()


def sniff_format(head):
    """
    Identify a graphic format from its leading bytes.

    Args:
        head: first bytes of the file (at least 64 recommended)

    Returns:
        str: canonical format id, or None when nothing matches
    """
    if not head:
        return None

    if head.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if head.startswith(b'\xff\xd8\xff'):
        return 'jpeg'
    if head.startswith((b'GIF87a', b'GIF89a')):
        return 'gif'
    if head.startswith(b'BM'):
        return 'bmp'
    if head.startswith((b'II*\x00', b'MM\x00*', b'II+\x00', b'MM\x00+')):
        return 'tiff'
    if head.startswith(b'\x00\x00\x01\x00'):
        return 'ico'
    if head.startswith(b'RIFF') and head[8:12] == b'WEBP':
        return 'webp'
    if head[4:8] == b'ftyp' and head[8:12] in (b'avif', b'avis'):
        return 'avif'
    if head.startswith(b'\x1f\x8b'):
        # gzip: only meaningful here as a compressed SVG
        return 'svgz'
    if _looks_like_svg(head):
        return 'svg'
    return None


def sniff_matches_extension(head, ext):
    """
    Verify that a file's bytes agree with its declared extension.

    Returns:
        tuple: (ok: bool, detected_format_id: str or None)
    """
    expected = format_for_extension(ext)
    detected = sniff_format(head)
    if expected is None or detected is None:
        return (False, detected)
    # .svgz is gzip-wrapped SVG; both ids are vector and interchangeable only
    # in that direction (a plain .svg must not be gzip data).
    return (expected == detected, detected)


# ============================================================================
# SVG SANITIZATION
# ============================================================================

# Elements kept in a sanitized logo. Anything not listed is dropped with its
# subtree. Scripting, external content and animation are all excluded: none of
# it renders in a PDF and all of it has been an XSS vector at some point.
SVG_ALLOWED_ELEMENTS = {
    'svg', 'g', 'defs', 'symbol', 'use', 'title', 'desc', 'switch', 'a',
    'path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon',
    'text', 'tspan', 'textPath', 'image', 'marker', 'style',
    'linearGradient', 'radialGradient', 'stop', 'pattern',
    'clipPath', 'mask', 'filter',
    'feBlend', 'feColorMatrix', 'feComponentTransfer', 'feComposite',
    'feConvolveMatrix', 'feDiffuseLighting', 'feDisplacementMap',
    'feDistantLight', 'feDropShadow', 'feFlood', 'feFuncA', 'feFuncB',
    'feFuncG', 'feFuncR', 'feGaussianBlur', 'feMerge', 'feMergeNode',
    'feMorphology', 'feOffset', 'fePointLight', 'feSpecularLighting',
    'feSpotLight', 'feTile', 'feTurbulence',
}

# Attributes dropped regardless of element.
SVG_FORBIDDEN_ATTRS = {
    'externalresourcesrequired', 'requiredextensions', 'systemlanguage',
    'contentscripttype', 'contentstyletype',
}

_STYLE_BAD_RE = re.compile(
    r'(@import|expression\s*\(|behaviou?r\s*:|-moz-binding|javascript\s*:)',
    re.IGNORECASE,
)
_CSS_URL_RE = re.compile(r'url\s*\(\s*([\'"]?)([^\'")]*)\1\s*\)', re.IGNORECASE)


def _local_name(tag):
    """Strip the {namespace} prefix ElementTree puts on parsed tags."""
    if isinstance(tag, str) and tag.startswith('{'):
        return tag.split('}', 1)[1]
    return tag if isinstance(tag, str) else ''


def _safe_reference(value):
    """Allow only same-document fragments and inline data: images."""
    if value is None:
        return False
    v = value.strip()
    if not v:
        return False
    # Reject control characters used to smuggle schemes (e.g. "java\tscript:")
    v_clean = re.sub(r'[\s\x00-\x1f]', '', v).lower()
    if v.startswith('#'):
        return True
    if v_clean.startswith('data:image/') and 'svg' not in v_clean.split(';', 1)[0]:
        return True
    return False


def _sanitize_css(text):
    """Strip dangerous constructs from <style> content or a style attribute."""
    if not text:
        return text
    if _STYLE_BAD_RE.search(text):
        return ''

    def _url(match):
        return 'none' if not _safe_reference(match.group(2)) else match.group(0)

    return _CSS_URL_RE.sub(_url, text)


_DOCTYPE_RE = re.compile(
    r'<!DOCTYPE\s[^>\[]*(\[.*?\])?[^>]*>',
    re.IGNORECASE | re.DOTALL,
)


def _strip_doctype(text):
    """
    Remove a leading DOCTYPE declaration from an SVG document.

    Design tools (Illustrator in particular) emit the harmless SVG 1.1 public
    DOCTYPE, so rejecting every DOCTYPE outright would turn away a large share
    of real brand assets. An *internal subset* is a different matter: that is
    where entity declarations - and therefore XXE - live, so it is refused.

    Raises:
        ValueError: when the DOCTYPE carries an internal subset
    """
    match = _DOCTYPE_RE.search(text)
    if not match:
        return text

    if match.group(1):
        raise ValueError(
            'SVG contains an internal DTD subset (entity declarations), '
            'which is not allowed. Re-export the file as plain SVG.'
        )

    return text[:match.start()] + text[match.end():]


def _sanitize_element(element):
    """Recursively filter one element's attributes and children in place."""
    for name in list(element.attrib):
        local = _local_name(name).lower() if name.startswith('{') else name.lower()
        value = element.attrib[name]

        if local.startswith('on'):
            del element.attrib[name]
            continue
        if local in SVG_FORBIDDEN_ATTRS:
            del element.attrib[name]
            continue
        if local == 'href':
            if not _safe_reference(value):
                del element.attrib[name]
            continue
        if local == 'style':
            cleaned = _sanitize_css(value)
            if cleaned:
                element.attrib[name] = cleaned
            else:
                del element.attrib[name]
            continue

    if _local_name(element.tag) == 'style':
        element.text = _sanitize_css(element.text)

    for child in list(element):
        tag = _local_name(child.tag)
        if tag not in SVG_ALLOWED_ELEMENTS:
            element.remove(child)
            continue
        _sanitize_element(child)


def sanitize_svg(data):
    """
    Parse and sanitize an SVG document.

    Blocks XXE / entity expansion / external DTDs at parse time (defusedxml),
    then applies an element allowlist and strips event handlers, external
    references and dangerous CSS.

    Args:
        data: raw SVG bytes (gzip-compressed SVGZ is decompressed first)

    Returns:
        bytes: sanitized SVG document

    Raises:
        ValueError: when the document is not parseable SVG
    """
    from defusedxml.ElementTree import fromstring as defused_fromstring

    if data[:2] == b'\x1f\x8b':
        try:
            data = gzip.decompress(data)
        except OSError as exc:
            raise ValueError(f'Could not decompress SVGZ file: {exc}')

    text = _strip_doctype(data.decode('utf-8', errors='replace'))

    try:
        root = defused_fromstring(
            text,
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        )
    except Exception as exc:
        raise ValueError(f'Not a valid SVG document: {exc}')

    if _local_name(root.tag) != 'svg':
        raise ValueError('Root element is not <svg>')

    _sanitize_element(root)

    ET.register_namespace('', SVG_NS)
    ET.register_namespace('xlink', XLINK_NS)
    body = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    return body


def svg_dimensions(data):
    """
    Best-effort intrinsic pixel size of an SVG, for display purposes only.

    Returns:
        tuple: (width: int or None, height: int or None)
    """
    try:
        root = ET.fromstring(data.decode('utf-8', errors='replace'))
    except ET.ParseError:
        return (None, None)

    def _px(value):
        if not value:
            return None
        match = re.match(r'^\s*([0-9]*\.?[0-9]+)\s*(px)?\s*$', value)
        return int(round(float(match.group(1)))) if match else None

    width = _px(root.get('width'))
    height = _px(root.get('height'))

    if width is None or height is None:
        viewbox = (root.get('viewBox') or '').replace(',', ' ').split()
        if len(viewbox) == 4:
            try:
                width = width or int(round(float(viewbox[2])))
                height = height or int(round(float(viewbox[3])))
            except ValueError:
                pass

    return (width, height)


# ============================================================================
# RASTER HANDLING
# ============================================================================

def _open_verified(data):
    """Open raster bytes with Pillow after an integrity check."""
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

    try:
        probe = Image.open(io.BytesIO(data))
        probe.verify()
    except Exception as exc:
        raise ValueError(f'File is not a readable image: {exc}')

    # verify() leaves the image unusable; reopen for real work.
    return Image.open(io.BytesIO(data))


def raster_dimensions(data):
    """
    Pixel size of raster bytes.

    Returns:
        tuple: (width, height)

    Raises:
        ValueError: when the data is not a readable image
    """
    with _open_verified(data) as image:
        return image.size


def normalize_raster(data, max_dimension=DEFAULT_MAX_DIMENSION):
    """
    Convert raster bytes to an RGBA PNG suitable for kast report embedding.

    Multi-frame inputs (GIF, TIFF) use the first frame; ICO uses the largest
    frame Pillow selects. Oversized images are downscaled to max_dimension on
    the longest edge.

    Args:
        data: raw image bytes
        max_dimension: longest-edge cap in pixels

    Returns:
        tuple: (png_bytes, width, height)

    Raises:
        ValueError: when the data is not a readable image
    """
    from PIL import Image

    with _open_verified(data) as image:
        try:
            image.seek(0)
        except (AttributeError, EOFError, ValueError):
            pass

        converted = image.convert('RGBA')

        if max_dimension and max(converted.size) > max_dimension:
            converted.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

        buffer = io.BytesIO()
        converted.save(buffer, format='PNG', optimize=True)
        return (buffer.getvalue(), converted.width, converted.height)


# ============================================================================
# UNIFIED ENTRY POINT
# ============================================================================

def prepare_logo(data, filename, max_dimension=DEFAULT_MAX_DIMENSION):
    """
    Validate uploaded bytes and build the pair of artifacts a logo needs.

    The original is preserved byte-for-byte except for SVG/SVGZ, where the
    sanitized document replaces it (we never retain unsanitized markup).

    Args:
        data: raw uploaded bytes
        filename: original filename, used for the declared extension
        max_dimension: longest-edge cap for raster normalization

    Returns:
        dict with keys:
            format_id, label, kind, mime, extension
            original_bytes, original_extension
            render_bytes, render_extension, render_mime
            width, height

    Raises:
        ValueError: when the file is unsupported, corrupt, or mislabeled
    """
    ext = extension_of(filename)
    fmt_id = format_for_extension(ext)
    if fmt_id is None:
        raise ValueError(
            f'Unsupported file type ".{ext}". Supported formats: '
            f'{format_list_text()}.'
        )

    ok, detected = sniff_matches_extension(data[:SVG_PROBE_BYTES], ext)
    if not ok:
        if detected is None:
            raise ValueError(
                'File contents are not a recognized image format. '
                'The file may be corrupt or renamed.'
            )
        raise ValueError(
            f'File contents do not match the ".{ext}" extension '
            f'(detected {LOGO_FORMATS[detected]["label"]}). '
            'Rename the file to its real format and try again.'
        )

    spec = LOGO_FORMATS[fmt_id]

    if spec['kind'] == 'vector':
        sanitized = sanitize_svg(data)
        width, height = svg_dimensions(sanitized)
        return {
            'format_id': fmt_id,
            'label': spec['label'],
            'kind': 'vector',
            'mime': 'image/svg+xml',
            'extension': 'svg',
            'original_bytes': sanitized,
            'original_extension': 'svg',
            'render_bytes': sanitized,
            'render_extension': 'svg',
            'render_mime': 'image/svg+xml',
            'width': width,
            'height': height,
        }

    if spec['needs_normalize']:
        png_bytes, width, height = normalize_raster(data, max_dimension)
        render_bytes, render_ext, render_mime = png_bytes, 'png', 'image/png'
    else:
        width, height = raster_dimensions(data)
        render_bytes, render_ext, render_mime = data, ext, spec['mime']

    return {
        'format_id': fmt_id,
        'label': spec['label'],
        'kind': 'raster',
        'mime': spec['mime'],
        'extension': ext,
        'original_bytes': data,
        'original_extension': ext,
        'render_bytes': render_bytes,
        'render_extension': render_ext,
        'render_mime': render_mime,
        'width': width,
        'height': height,
    }
