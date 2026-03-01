import { html } from '../htm.js';
import { useStore } from '../state.js';
import { formatElapsedTime, renderMarkdown } from '../utils.js';
import { Collapsible } from './Collapsible.js';
import { ToolCall } from './ToolCall.js';
import { SubAgent } from './SubAgent.js';
import { MetricsBar } from './PlanStep.js';

function extractPreview(text, maxLen) {
    if (!text) return '';
    const paraEnd = text.indexOf('\n\n');
    if (paraEnd > 0 && paraEnd <= maxLen) {
        return text.substring(0, paraEnd).trim();
    }
    if (text.length <= maxLen) return text;
    const truncated = text.substring(0, maxLen);
    const lastSpace = truncated.lastIndexOf(' ');
    return lastSpace > maxLen * 0.5 ? truncated.substring(0, lastSpace) : truncated;
}

export function StepContainer({ node }) {
    const isLive = useStore(s => s.isRunning || s.viewingLiveSession);
    const data = node.data;
    if (!data) {
        // Pending placeholder (no action_step merged yet)
        // If session is no longer live, show as interrupted instead of spinning
        const interrupted = !isLive;
        return html`
            <div class="step-container ${interrupted ? '' : 'pending'}">
                <div class="step-number ${interrupted ? '' : 'active'}">${interrupted ? '\u2717' : '...'}</div>
                <div class="step-header">
                    ${interrupted
                        ? html`<span>${node.label || 'Processing'} — <em>interrupted</em></span>`
                        : html`<span class="spinner" /> ${node.label || 'Processing'}...`
                    }
                </div>
                <div class="step-children">
                    ${Object.entries(node.subAgents || {}).map(([name, agent]) => html`
                        <${SubAgent} name=${name} events=${agent.events} key=${name} />
                    `)}
                </div>
            </div>
        `;
    }

    const isCodeAgent = !!data.code_action;
    const callsSubAgent = isCodeAgent &&
        /\w+_agent\s*\(/.test(data.code_action || '');
    const hasSubAgents = Object.keys(node.subAgents || {}).length > 0;

    return html`
        <div class="step-container" data-step=${data.step_number}>
            <div class="step-number ${!data.duration ? 'active' : ''}">
                ${data.step_number}
            </div>
            ${data.duration != null && html`
                <div class="step-elapsed">${formatElapsedTime(Math.round(data.duration))}</div>
            `}
            <div class="step-header">
                <span>Step ${data.step_number}</span>
                ${data.agent_name && html`
                    <span class="agent-badge">${data.agent_name}</span>
                `}
            </div>
            ${(data.duration != null || data.token_usage) && html`
                <${MetricsBar} data=${data} />
            `}
            <div class="step-children">
                <!-- LLM reasoning -->
                ${data.model_output && html`
                    <div class="model-output" dangerouslySetInnerHTML=${{ __html: renderMarkdown(data.model_output) }} />
                `}

                <!-- Code or Tool calls -->
                ${isCodeAgent ? html`
                    <${Collapsible}
                        title=${callsSubAgent ? 'Agent Call' : 'Code'}
                        content=${data.code_action}
                        type="code_block"
                    />
                    ${!callsSubAgent && data.observations && html`
                        <${Collapsible}
                            title="Execution Log"
                            content=${data.observations}
                            type="observation"
                        />
                    `}
                    ${data.action_output && !data.is_final_answer && html`
                        <${Collapsible}
                            title="Return Value"
                            content=${data.action_output}
                            type="code_execution"
                        />
                    `}
                ` : html`
                    ${renderToolCalls(data)}
                `}

                <!-- Sub-agents -->
                ${hasSubAgents && Object.entries(node.subAgents).map(([name, agent]) => html`
                    <${SubAgent} name=${name} events=${agent.events} key=${name} />
                `)}

                <!-- Error -->
                ${data.error && html`
                    <div class="event-error">
                        ${callsSubAgent && /execution time|max.steps|timed?\s*out/i.test(data.error)
                            ? 'Sub-agent did not finish in time'
                            : data.error}
                    </div>
                `}
            </div>
        </div>
    `;
}

function renderToolCalls(data) {
    const toolCalls = data.tool_calls || [];

    if (toolCalls.length === 1) {
        return html`
            <${ToolCall}
                toolName=${toolCalls[0].name}
                args=${toolCalls[0].arguments}
                result=${data.observations}
            />
        `;
    }

    return html`
        ${toolCalls.map((tc, i) => html`
            <${ToolCall}
                toolName=${tc.name}
                args=${tc.arguments}
                key=${i}
            />
        `)}
        ${data.observations && html`
            <${Collapsible}
                title="Results"
                content=${data.observations}
                type="observation"
                isMarkdown=${true}
            />
        `}
    `;
}
