import { html } from '../htm.js';
import { getHistory, clearHistory, setState } from '../state.js';

export function HistoryPanel() {
    const history = getHistory();

    function onClickItem(run) {
        setState({
            question: run.question,
            selectedModel: run.modelId || '',
            historyOpen: false,
        });
    }

    function onClear() {
        clearHistory();
        setState({ historyOpen: false });
    }

    return html`
        <div class="history-panel">
            <div class="history-header">
                <span class="history-title">Recent Runs</span>
                ${history.length > 0 && html`
                    <button class="btn btn-ghost btn-sm" onClick=${onClear}>Clear</button>
                `}
            </div>
            ${history.length === 0
                ? html`<div class="history-empty">No previous runs</div>`
                : history.map(run => html`
                    <div class="history-item" onClick=${() => onClickItem(run)} key=${run.id}>
                        <div class="history-question">${run.question}</div>
                        <div class="history-meta">
                            ${new Date(run.timestamp).toLocaleDateString()}
                            ${' \u2022 '}
                            ${run.modelId}
                        </div>
                        ${run.finalAnswer && html`
                            <div class="history-answer">
                                ${run.finalAnswer.substring(0, 100)}${run.finalAnswer.length > 100 ? '...' : ''}
                            </div>
                        `}
                    </div>
                `)
            }
        </div>
    `;
}
