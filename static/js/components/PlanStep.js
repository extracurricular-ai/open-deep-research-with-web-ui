import { html } from '../htm.js';
import { formatElapsedTime } from '../utils.js';
import { Collapsible } from './Collapsible.js';

export function PlanStep({ data }) {
    const title = data.agent_name ? `Plan (${data.agent_name})` : 'Plan';

    return html`
        <div class="step-container plan-step">
            <div class="step-number plan-icon">\u{1F4CB}</div>
            ${data.duration != null && html`
                <div class="step-elapsed">${formatElapsedTime(Math.round(data.duration))}</div>
            `}
            <div class="step-header plan-header">
                <span>${title}</span>
                ${data.agent_name && html`
                    <span class="agent-badge">${data.agent_name}</span>
                `}
            </div>
            ${(data.duration != null || data.token_usage) && html`
                <${MetricsBar} data=${data} />
            `}
            <div class="step-children">
                <${Collapsible}
                    title=${title}
                    content=${data.plan}
                    type="plan"
                    expanded=${true}
                    isMarkdown=${true}
                />
            </div>
        </div>
    `;
}

export function MetricsBar({ data }) {
    const parts = [];
    if (data.duration != null) parts.push(`${data.duration.toFixed(1)}s`);
    if (data.token_usage) {
        if (data.token_usage.input_tokens != null) {
            parts.push(`${data.token_usage.input_tokens.toLocaleString()} in / ${data.token_usage.output_tokens.toLocaleString()} out`);
        }
    }
    if (parts.length === 0) return null;

    return html`<div class="step-metrics">${parts.join(' \u2022 ')}</div>`;
}
