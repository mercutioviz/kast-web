"""
AIService — cost-gated executive summary generation for kast-web.

Reads processed scan results from disk, calls the Anthropic API, and
persists results in AISummary. All LLM calls are optional; if AI is
disabled the caller gets a graceful None back.

Key resolution order:
  1. User's personal Anthropic key (all roles)
  2. Org-level key — admins and power_users only
  3. KAST_AI_API_KEY / KAST_AI_BASE_URL env vars (system-level default)
  4. No key → ValueError with a user-facing message
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Approximate token costs (USD per million tokens) for cost-estimate display.
_COST_PER_M_INPUT = {
    'claude-haiku-4-5-20251001': 0.80,
    'claude-sonnet-4-6': 3.00,
    'claude-opus-4-7': 15.00,
}
_COST_PER_M_OUTPUT = {
    'claude-haiku-4-5-20251001': 4.00,
    'claude-sonnet-4-6': 15.00,
    'claude-opus-4-7': 75.00,
}
_DEFAULT_MODEL = 'claude-sonnet-4-6'

_SYSTEM_PROMPT = (
    "You are a senior application security consultant writing a concise executive "
    "summary for a sales prospect. The summary will accompany a web-application "
    "security scan report. Write 3-4 paragraphs suitable for a non-technical "
    "executive audience. Emphasise business risk over technical detail. Do not "
    "include CVSS scores or raw vulnerability IDs. Do not mention the tool that "
    "performed the scan. Focus on the prospect's exposure and how a WAF/WaaS "
    "solution would reduce their risk. Write in a professional but approachable tone."
)

_SUMMARY_PROMPT_TEMPLATE = """The following security scan was conducted against {target}.

Scan mode: {scan_mode}
Completed: {completed_at}

FINDINGS SUMMARY
================
{findings_text}

Please write an executive summary of these findings."""


class AIService:
    """Stateless service — instantiate once per request or reuse across the app."""

    # ------------------------------------------------------------------ helpers

    def _get_settings(self):
        from app.models import AISettings
        return AISettings.get()

    def _resolve_model(self, user, settings):
        """Return the effective model ID for a user."""
        return (
            (user.ai_model_override if user else None)
            or settings.model_id
            or _DEFAULT_MODEL
        )

    def _get_client(self, user=None):
        """Return an Anthropic client, applying role-based key resolution.

        Resolution order:
          1. User's personal DB key + user's ai_base_url (falls back to KAST_AI_BASE_URL)
          2. Org DB key — admins and power_users only (falls back to KAST_AI_BASE_URL)
          3. KAST_AI_API_KEY / KAST_AI_BASE_URL env vars (system-level default)
          4. ValueError (no key available)

        A 60-second timeout is applied to all clients to prevent hung gunicorn workers.
        """
        import os
        from app.encryption import decrypt_value
        import anthropic

        env_key = os.environ.get('KAST_AI_API_KEY')
        env_base_url = os.environ.get('KAST_AI_BASE_URL')
        user_base_url = (user.ai_base_url or None) if user else None

        def _make_client(api_key, base_url=None):
            kwargs = {'api_key': api_key, 'timeout': 60.0}
            if base_url:
                kwargs['base_url'] = base_url
            return anthropic.Anthropic(**kwargs)

        # 1. User's personal key; inherit env base_url if user has no override
        if user and user.anthropic_api_key_encrypted:
            effective_base_url = user_base_url or env_base_url
            logger.info(
                '_get_client: using user personal key (user_id=%s) base_url=%r',
                user.id, effective_base_url,
            )
            return _make_client(
                decrypt_value(user.anthropic_api_key_encrypted),
                base_url=effective_base_url,
            )

        # 2. Org key — admins and power_users only
        if user and user.role in ('admin', 'power_user'):
            settings = self._get_settings()
            if settings.api_key_encrypted:
                effective_base_url = user_base_url or env_base_url
                logger.info(
                    '_get_client: using org key (user_id=%s role=%s) base_url=%r',
                    user.id, user.role, effective_base_url,
                )
                return _make_client(
                    decrypt_value(settings.api_key_encrypted),
                    base_url=effective_base_url,
                )

        # 3. System env vars — lowest-priority fallback (works for all roles)
        if env_key:
            logger.info('_get_client: using KAST_AI_API_KEY env var base_url=%r', env_base_url)
            return _make_client(env_key, base_url=env_base_url)

        user_id = user.id if user else None
        user_role = user.role if user else None
        logger.warning(
            '_get_client: no key resolved (user_id=%s role=%s env_key_set=%s)',
            user_id, user_role, bool(env_key),
        )
        raise ValueError(
            'No personal API key configured. '
            'Add your Anthropic API key in My Profile > AI Settings.'
        )

    def _read_findings(self, scan):
        """Read processed plugin JSON files and return a text summary of findings."""
        output_dir = Path(scan.output_dir) if scan.output_dir else None
        if not output_dir or not output_dir.exists():
            return 'No output directory found for this scan.'

        lines = []
        for processed_file in sorted(output_dir.glob('*_processed.json')):
            try:
                data = json.loads(processed_file.read_text())
                plugin_name = processed_file.stem.replace('_processed', '')
                findings = data.get('findings', [])
                if not findings:
                    lines.append(f'{plugin_name}: no findings')
                    continue
                if isinstance(findings, list):
                    lines.append(f'{plugin_name}: {len(findings)} finding(s)')
                    for f in findings[:50]:
                        severity = f.get('severity', 'unknown')
                        title = f.get('title') or f.get('name') or f.get('id', 'Unknown')
                        lines.append(f'  [{severity.upper()}] {title}')
                else:
                    # Dict-style findings (flat result object) — summarise key fields
                    disp = findings.get('disposition') or findings.get('status', '')
                    results = findings.get('results')
                    summary_parts = []
                    if disp:
                        summary_parts.append(f'disposition={disp}')
                    if results:
                        if isinstance(results, list):
                            summary_parts.append(f'{len(results)} result(s)')
                        elif isinstance(results, dict):
                            summary_parts.append(f'results: {str(results)[:200]}')
                    else:
                        # No nested results — surface top-level scalar values
                        for k, v in findings.items():
                            if isinstance(v, (str, int, float, bool)) and v:
                                summary_parts.append(f'{k}={v}')
                    lines.append(f'{plugin_name}: {"; ".join(summary_parts) or "data present"}')
            except Exception as exc:
                logger.warning('Could not read %s: %s', processed_file, exc)

        return '\n'.join(lines) if lines else 'No processed findings available.'

    def check_budget(self, estimated_tokens):
        """Return True if there is remaining budget for estimated_tokens.

        Treats None or 0 as unknown cost — allowed through.
        Budget of 0 means unlimited.
        """
        if not estimated_tokens:
            return True
        settings = self._get_settings()
        limit = settings.monthly_budget_tokens or 0
        if limit == 0:
            return True
        used = settings.current_period_tokens or 0
        return used + estimated_tokens <= limit

    def _estimate_tokens(self, prompt_text):
        """Rough token estimate: 1 token ≈ 4 chars."""
        system_tokens = len(_SYSTEM_PROMPT) // 4
        user_tokens = len(prompt_text) // 4
        output_tokens = 800  # typical summary length
        return system_tokens + user_tokens, output_tokens

    # ------------------------------------------------------------------ public API

    def is_enabled(self):
        return self._get_settings().ai_enabled

    def estimate_cost(self, scan, user=None):
        """Return dict with estimated token counts and USD cost for a scan."""
        settings = self._get_settings()
        findings_text = self._read_findings(scan)
        prompt = _SUMMARY_PROMPT_TEMPLATE.format(
            target=scan.target,
            scan_mode=scan.scan_mode,
            completed_at=scan.completed_at or 'unknown',
            findings_text=findings_text,
        )
        tokens_in, tokens_out = self._estimate_tokens(prompt)
        model = self._resolve_model(user, settings)
        known = model in _COST_PER_M_INPUT
        if known:
            cost_usd = round(
                tokens_in / 1_000_000 * _COST_PER_M_INPUT[model]
                + tokens_out / 1_000_000 * _COST_PER_M_OUTPUT[model],
                4,
            )
        else:
            cost_usd = None
        return {
            'tokens_in': tokens_in,
            'tokens_out': tokens_out,
            'cost_usd': cost_usd,
            'model': model,
            'cost_known': known,
        }

    def generate_summary(self, scan, mode=None, user=None):
        """Generate (or regenerate) an AI executive summary for a scan.

        Args:
            scan: Scan model instance.
            mode: 'auto' or 'review'. Defaults to the org setting.
            user: The requesting User instance (for key resolution).

        Returns the AISummary instance (check .status for 'error').
        Returns None only if AI is disabled at the org level.
        """
        import anthropic as _anthropic
        from app import db
        from app.models import AISummary

        settings = self._get_settings()
        if not settings.ai_enabled:
            logger.info('AI is disabled; skipping summary for scan %s', scan.id)
            return None

        effective_mode = mode or settings.default_mode
        logger.info(
            'generate_summary: scan_id=%s user_id=%s mode=%r',
            scan.id, user.id if user else None, effective_mode,
        )

        # Upsert the summary row and mark as generating
        summary = AISummary.query.filter_by(scan_id=scan.id).first()
        if summary is None:
            summary = AISummary(scan_id=scan.id)
            db.session.add(summary)
        summary.status = 'generating'
        summary.error_message = None
        db.session.commit()

        try:
            client = self._get_client(user=user)
        except ValueError as exc:
            summary.status = 'error'
            summary.error_message = str(exc)
            db.session.commit()
            return summary

        try:
            findings_text = self._read_findings(scan)
            prompt = _SUMMARY_PROMPT_TEMPLATE.format(
                target=scan.target,
                scan_mode=scan.scan_mode,
                completed_at=scan.completed_at or 'unknown',
                findings_text=findings_text,
            )
            model = self._resolve_model(user, settings)
            logger.info(
                'generate_summary: calling Anthropic model=%r prompt_chars=%d',
                model, len(prompt),
            )
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[{'role': 'user', 'content': prompt}],
            )
            logger.info(
                'generate_summary: API call succeeded tokens_in=%s tokens_out=%s',
                response.usage.input_tokens, response.usage.output_tokens,
            )

            summary.raw_text = response.content[0].text
            summary.edited_text = None
            summary.reviewed_by_user_id = None
            summary.tokens_in = response.usage.input_tokens
            summary.tokens_out = response.usage.output_tokens
            if model in _COST_PER_M_INPUT:
                summary.cost_usd = (
                    response.usage.input_tokens / 1_000_000 * _COST_PER_M_INPUT[model]
                    + response.usage.output_tokens / 1_000_000 * _COST_PER_M_OUTPUT[model]
                )
            else:
                summary.cost_usd = 0.0
            summary.generated_at = datetime.now(timezone.utc)
            summary.status = 'ready' if effective_mode == 'review' else 'accepted'
            summary.prompt_version = 'exec_summary_v1'

            # Update org-level period token counter (informational only for BYOK users)
            settings.current_period_tokens = (
                (settings.current_period_tokens or 0)
                + summary.tokens_in
                + summary.tokens_out
            )
            db.session.commit()
            return summary

        except _anthropic.RateLimitError:
            # Covers both rate limiting and exhausted credit balance
            summary.status = 'error'
            summary.error_message = (
                'API budget exceeded. '
                'Please top up your Anthropic credit balance and try again.'
            )
            db.session.commit()
            return summary

        except _anthropic.AuthenticationError:
            summary.status = 'error'
            summary.error_message = (
                'Invalid API key. '
                'Please update your Anthropic API key in My Profile > AI Settings.'
            )
            db.session.commit()
            return summary

        except _anthropic.APIError as exc:
            logger.exception('Anthropic API error for scan %s', scan.id)
            summary.status = 'error'
            summary.error_message = f'Anthropic API error: {exc}'
            db.session.commit()
            return summary

        except Exception as exc:
            logger.exception('Unexpected error generating AI summary for scan %s', scan.id)
            summary.status = 'error'
            summary.error_message = f'Unexpected error: {exc}'
            db.session.commit()
            return summary

    def submit_review(self, summary, edited_text, action, user_id):
        """Accept or discard an SA's edits to a generated summary.

        action='accept'  — store edited_text, mark accepted
        action='discard' — discard edits, keep raw_text, mark accepted
        """
        from app import db

        if action == 'accept':
            summary.edited_text = edited_text
            summary.reviewed_by_user_id = user_id
            summary.status = 'accepted'
        elif action == 'discard':
            summary.edited_text = None
            summary.reviewed_by_user_id = user_id
            summary.status = 'accepted'
        db.session.commit()

    def display_text(self, summary):
        """Return the text that should be shown/shared: edited if present, else raw."""
        if summary is None:
            return None
        return summary.edited_text or summary.raw_text
