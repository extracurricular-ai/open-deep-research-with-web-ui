import { useEffect, useRef } from 'preact/hooks';
import { html } from '../htm.js';
import { useStore, setState, getStepTree } from '../state.js';
import { renderMarkdown } from '../utils.js';
import { StepContainer } from './StepContainer.js';
import { PlanStep } from './PlanStep.js';
import { AnswerBox } from './AnswerBox.js';
import { Collapsible } from './Collapsible.js';

const FILTERS = [
    { id: 'all', label: 'All' },
    { id: 'step', label: 'Steps' },
    { id: 'tool_call', label: 'Tools' },
    { id: 'plan', label: 'Plans' },
    { id: 'code_block', label: 'Code' },
    { id: 'observation', label: 'Results' },
    { id: 'final_answer', label: 'Answer' },
    { id: 'error', label: 'Errors' },
];

function Skeleton() {
    return html`
        <div class="skeleton">
            <div class="skeleton-step">
                <div class="skeleton-circle skeleton-pulse" />
                <div class="skeleton-line skeleton-pulse" style="width: 40%" />
            </div>
            <div class="skeleton-card skeleton-pulse" />
            <div class="skeleton-card skeleton-pulse" style="width: 80%" />
            <div class="skeleton-step" style="margin-top: 16px">
                <div class="skeleton-circle skeleton-pulse" />
                <div class="skeleton-line skeleton-pulse" style="width: 35%" />
            </div>
            <div class="skeleton-card skeleton-pulse" style="width: 90%" />
        </div>
    `;
}

export function OutputPanel() {
    const outputRef = useRef(null);
    const store = useStore();
    const tree = getStepTree();
    const filter = store.activeFilter;
    const hasEvents = store.events.length > 0;

    // Auto-scroll to bottom on new events
    useEffect(() => {
        if (outputRef.current) {
            outputRef.current.scrollTop = outputRef.current.scrollHeight;
        }
    }, [store.events.length]);

    function onFilter(id) {
        setState({ activeFilter: id });
    }

    function shouldShow(node) {
        if (filter === 'all') return true;
        if (filter === 'step' && (node.type === 'step' || node.type === 'pending')) return true;
        if (filter === 'plan' && node.type === 'plan') return true;
        if (filter === 'final_answer' && node.type === 'final_answer') return true;
        if (filter === 'error' && node.type === 'error') return true;
        if (node.type === 'step' && node.data) {
            if (filter === 'tool_call' && (node.data.tool_calls || []).length > 0) return true;
            if (filter === 'code_block' && node.data.code_action) return true;
            if (filter === 'observation' && node.data.observations) return true;
        }
        return false;
    }

    return html`
        <div class="panel output-panel">
            <div class="output-header">
                <h2>Output</h2>
                <div class="filter-bar">
                    ${FILTERS.map(f => html`
                        <button
                            class="filter-btn ${filter === f.id ? 'active' : ''}"
                            onClick=${() => onFilter(f.id)}
                            key=${f.id}
                        >
                            ${f.label}
                        </button>
                    `)}
                </div>
            </div>
            <div class="output-area" ref=${outputRef}>
                ${!hasEvents && store.isRunning && html`<${Skeleton} />`}
                ${!hasEvents && !store.isRunning && html`
                    <div class="output-empty">Waiting for input...</div>
                `}
                ${tree.map((node, i) => {
                    if (!shouldShow(node)) return null;
                    return html`<${EventNode} node=${node} key=${i} />`;
                })}
            </div>
            <${AnswerBox} />
        </div>
    `;
}

function EventNode({ node }) {
    switch (node.type) {
        case 'step':
        case 'pending':
            return html`<${StepContainer} node=${node} />`;
        case 'plan':
            return html`<${PlanStep} data=${node.data} />`;
        case 'final_answer': {
            const content = node.data.output || node.data.content || '';
            return html`
                <${Collapsible}
                    title="Final Answer"
                    content=${content}
                    type="final_answer"
                    expanded=${true}
                    isMarkdown=${true}
                />
            `;
        }
        case 'info':
            return html`<div class="event-info">${node.data.content}</div>`;
        case 'error':
            return html`<div class="event-error">${node.data.content}</div>`;
        case 'message':
        default:
            return html`<div class="event-message" dangerouslySetInnerHTML=${{ __html: renderMarkdown(node.data.content || JSON.stringify(node.data)) }} />`;
    }
}
