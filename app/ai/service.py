"""
AIService — cost-gated executive summary generation for kast-web.

Reads processed scan results from disk, calls the Anthropic API, and
persists results in AISummary. All LLM calls are optional; if AI is
disabled or over budget the caller gets a graceful None back.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Approximate token costs (USD per million tokens) for budget checks.
# These are conservative estimates; actual costs depend on the model.
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

    def _get_client(self, settings):
        """Return an anthropic.Anthropic client using the stored API key."""
        from app.encryption import decrypt_value
        import anthropic

        if not settings.api_key_encrypted:
            raise ValueError('No API key configured — set one in Admin > AI Settings.')
        api_key = decrypt_value(settings.api_key_encrypted)
        return anthropic.Anthropic(api_key=api_key)

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
                lines.append(f'{plugin_name}: {len(findings)} finding(s)')
                for f in findings[:50]:  # cap to keep prompt size reasonable
                    severity = f.get('severity', 'unknown')
                    title = f.get('title') or f.get('name') or f.get('id', 'Unknown')
                    lines.append(f'  [{severity.upper()}] {title}')
            except Exception as exc:
                logger.warning('Could not read %s: %s', processed_file, exc)

        return '\n'.join(lines) if lines else 'No processed findings available.'

    def _estimate_tokens(self, prompt_text):
        """Rough token estimate: 1 token ≈ 4 chars."""
        system_tokens = len(_SYSTEM_PROMPT) // 4
        user_tokens = len(prompt_text) // 4
        output_tokens = 800  # typical summary length
        return system_tokens + user_tokens, output_tokens

    # ------------------------------------------------------------------ public API

    def is_enabled(self):
        return self._get_settings().ai_enabled

    def estimate_cost(self, scan):
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
        model = settings.model_id or _DEFAULT_MODEL
        cost_in = tokens_in / 1_000_000 * _COST_PER_M_INPUT.get(model, 3.00)
        cost_out = tokens_out / 1_000_000 * _COST_PER_M_OUTPUT.get(model, 15.00)
        return {
            'tokens_in': tokens_in,
            'tokens_out': tokens_out,
            'cost_usd': round(cost_in + cost_out, 4),
            'model': model,
        }

    def check_budget(self, estimated_cost_usd):
        """Return True if the estimated cost fits within the remaining monthly budget."""
        settings = self._get_settings()
        if not settings.monthly_budget_tokens:
            return True
        # Convert remaining token budget to dollars using sonnet rate as reference
        remaining_tokens = settings.monthly_budget_tokens - settings.current_period_tokens
        remaining_usd = remaining_tokens / 1_000_000 * _COST_PER_M_INPUT.get(
            settings.model_id or _DEFAULT_MODEL, 3.00
        )
        return estimated_cost_usd <= remaining_usd

    def generate_summary(self, scan, mode=None):
        """Generate (or regenerate) an AI executive summary for a scan.

        Creates or replaces the AISummary row for this scan.
        Returns the AISummary instance, or None on failure.
        """
        from app import db
        from app.models import AISummary

        settings = self._get_settings()
        if not settings.ai_enabled:
            logger.info('AI is disabled; skipping summary generation for scan %s', scan.id)
            return None

        effective_mode = mode or settings.default_mode

        # Upsert the summary row
        summary = AISummary.query.filter_by(scan_id=scan.id).first()
        if summary is None:
            summary = AISummary(scan_id=scan.id)
            db.session.add(summary)
        summary.status = 'generating'
        summary.error_message = None
        db.session.commit()

        try:
            findings_text = self._read_findings(scan)
            prompt = _SUMMARY_PROMPT_TEMPLATE.format(
                target=scan.target,
                scan_mode=scan.scan_mode,
                completed_at=scan.completed_at or 'unknown',
                findings_text=findings_text,
            )

            client = self._get_client(settings)
            model = settings.model_id or _DEFAULT_MODEL
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[{'role': 'user', 'content': prompt}],
            )

            summary.raw_text = response.content[0].text
            summary.edited_text = None
            summary.reviewed_by_user_id = None
            summary.tokens_in = response.usage.input_tokens
            summary.tokens_out = response.usage.output_tokens
            summary.cost_usd = (
                response.usage.input_tokens / 1_000_000 * _COST_PER_M_INPUT.get(model, 3.00)
                + response.usage.output_tokens / 1_000_000 * _COST_PER_M_OUTPUT.get(model, 15.00)
            )
            summary.generated_at = datetime.now(timezone.utc)
            summary.status = 'ready' if effective_mode == 'review' else 'accepted'
            summary.prompt_version = 'exec_summary_v1'

            # Update period token usage
            settings.current_period_tokens = (
                (settings.current_period_tokens or 0)
                + summary.tokens_in
                + summary.tokens_out
            )
            db.session.commit()
            return summary

        except Exception as exc:
            logger.exception('AI summary generation failed for scan %s', scan.id)
            summary.status = 'error'
            summary.error_message = str(exc)
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
