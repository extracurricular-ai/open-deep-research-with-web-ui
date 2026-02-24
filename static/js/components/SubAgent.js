import { html } from '../htm.js';
import { escapeHtml, renderMarkdown } from '../utils.js';
import { StepContainer } from './StepContainer.js';
import { PlanStep } from './PlanStep.js';
import { Collapsible } from './Collapsible.js';

function extractPreview(text, maxLen) {
    if (!text) return '';
    const paraEnd = text.indexOf('\n\n');
    if (paraEnd > 0 && paraEnd <= maxLen) return text.substring(0, paraEnd).trim();
    if (text.length <= maxLen) return text;
    const truncated = text.substring(0, maxLen);
    const lastSpace = truncated.lastIndexOf(' ');
    return lastSpace > maxLen * 0.5 ? truncated.substring(0, lastSpace) : truncated;
}

export function SubAgent({ name, events }) {
    return html`
        <div class="sub-agent">
            <div class="sub-agent-header">
                <span class="sub-agent-icon">\u25B8</span>
                <span>Sub-agent: ${escapeHtml(name)}</span>
            </div>
            <div class="sub-agent-children">
                ${events.map((node, i) => html`
                    <${SubAgentEvent} node=${node} agentName=${name} key=${i} />
                `)}
            </div>
        </div>
    `;
}

function SubAgentEvent({ node, agentName }) {
    switch (node.type) {
        case 'step':
            return html`<${StepContainer} node=${node} />`;
        case 'plan':
            return html`<${PlanStep} data=${node.data} />`;
        case 'final_answer': {
            const content = node.data.output || node.data.content || '';
            const isLong = content.length > 300;
            const preview = extractPreview(content, 200);

            return html`
                <div class="sub-agent-result">
                    <div class="sub-agent-result-label">[${escapeHtml(agentName)}] Result</div>
                    ${isLong ? html`
                        <div class="sub-agent-result-preview" dangerouslySetInnerHTML=${{ __html: renderMarkdown(`${preview}...`) }} />
                        <${Collapsible}
                            title="Full Result"
                            content=${content}
                            type="observation"
                            isMarkdown=${true}
                        />
                    ` : html`
                        <div class="sub-agent-result-content" dangerouslySetInnerHTML=${{ __html: renderMarkdown(content) }} />
                    `}
                </div>
            `;
        }
        case 'info':
            return html`<div class="event-info">${node.data.content}</div>`;
        case 'error':
            return html`<div class="event-error">${node.data.content}</div>`;
        case 'message':
        default:
            return html`<div class="event-message" dangerouslySetInnerHTML=${{ __html: renderMarkdown(node.data.content || '') }} />`;
    }
}
