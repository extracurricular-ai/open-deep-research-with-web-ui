/**
 * Run history management using localStorage
 */

const HISTORY_KEY = 'open_deep_research_history';
const MAX_HISTORY = 20;

/**
 * Save a completed run to history
 */
function saveRunToHistory(question, modelId, finalAnswer) {
    const history = getRunHistory();
    history.unshift({
        id: Date.now(),
        question: question,
        modelId: modelId,
        timestamp: new Date().toISOString(),
        finalAnswer: finalAnswer ? finalAnswer.substring(0, 500) : null
    });
    if (history.length > MAX_HISTORY) history.length = MAX_HISTORY;
    try {
        localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
    } catch (e) {
        // localStorage full — remove oldest entries
        history.length = Math.floor(MAX_HISTORY / 2);
        localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
    }
}

/**
 * Get all saved runs
 */
function getRunHistory() {
    try {
        return JSON.parse(localStorage.getItem(HISTORY_KEY)) || [];
    } catch {
        return [];
    }
}

/**
 * Clear all history
 */
function clearRunHistory() {
    localStorage.removeItem(HISTORY_KEY);
}

/**
 * Render history panel contents
 */
function renderHistoryPanel() {
    const listEl = document.getElementById('historyList');
    if (!listEl) return;

    const history = getRunHistory();
    if (history.length === 0) {
        listEl.innerHTML = '<div class="history-empty">No previous runs</div>';
        return;
    }

    listEl.innerHTML = '';
    history.forEach(run => {
        const item = document.createElement('div');
        item.className = 'history-item';

        const questionDiv = document.createElement('div');
        questionDiv.className = 'history-question';
        questionDiv.textContent = run.question;
        item.appendChild(questionDiv);

        const metaDiv = document.createElement('div');
        metaDiv.className = 'history-meta';
        const date = new Date(run.timestamp);
        metaDiv.textContent = `${date.toLocaleDateString()} ${date.toLocaleTimeString()} \u2022 ${run.modelId}`;
        item.appendChild(metaDiv);

        if (run.finalAnswer) {
            const answerDiv = document.createElement('div');
            answerDiv.className = 'history-meta';
            answerDiv.textContent = run.finalAnswer.substring(0, 100) + (run.finalAnswer.length > 100 ? '...' : '');
            item.appendChild(answerDiv);
        }

        item.addEventListener('click', () => {
            const questionInput = document.getElementById('question');
            const modelSelect = document.getElementById('modelSelect');
            if (questionInput) questionInput.value = run.question;
            if (modelSelect) {
                // Try to select the model, fall back to first option
                const option = modelSelect.querySelector(`option[value="${run.modelId}"]`);
                if (option) modelSelect.value = run.modelId;
            }
            // Hide history panel
            const panel = document.getElementById('historyPanel');
            if (panel) panel.style.display = 'none';
        });

        listEl.appendChild(item);
    });
}

/**
 * Toggle history panel visibility
 */
function toggleHistoryPanel() {
    const panel = document.getElementById('historyPanel');
    if (!panel) return;
    if (panel.style.display === 'none' || !panel.style.display) {
        renderHistoryPanel();
        panel.style.display = 'block';
    } else {
        panel.style.display = 'none';
    }
}
