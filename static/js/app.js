/**
 * Main application controller for Open Deep Research UI
 * Handles form submission, SSE streaming, theme, filters, and model loading
 */

(function() {
    'use strict';

    // DOM references
    const form = document.getElementById('queryForm');
    const questionInput = document.getElementById('question');
    const modelSelect = document.getElementById('modelSelect');
    const submitBtn = document.getElementById('submitBtn');
    const stopBtn = document.getElementById('stopBtn');
    const clearBtn = document.getElementById('clearBtn');
    const historyBtn = document.getElementById('historyBtn');
    const outputDiv = document.getElementById('output');
    const statusDiv = document.getElementById('status');
    const answerBox = document.getElementById('answerBox');

    // Stream state
    let currentReader = null;
    let currentSessionId = null;
    let isStopped = false;
    let lastFinalAnswer = null;
    let hasError = false;

    // ===== Theme Management =====
    function initTheme() {
        const saved = localStorage.getItem('odr-theme');
        if (saved) {
            document.documentElement.setAttribute('data-theme', saved);
            updateHighlightTheme(saved);
        }
    }

    function toggleTheme() {
        const current = document.documentElement.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('odr-theme', next);
        updateHighlightTheme(next);
    }

    function updateHighlightTheme(theme) {
        const hlLink = document.getElementById('highlight-theme');
        if (!hlLink) return;
        if (theme === 'dark') {
            hlLink.href = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css';
        } else {
            hlLink.href = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css';
        }
    }

    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }
    initTheme();

    // ===== Dynamic Model Loading =====
    async function loadModels() {
        try {
            const response = await fetch('/api/models');
            if (!response.ok) throw new Error('Failed to load models');
            const models = await response.json();
            modelSelect.innerHTML = '';
            models.forEach((model, index) => {
                const option = document.createElement('option');
                option.value = model.id;
                option.textContent = model.name;
                option.title = model.description || '';
                if (index === 0) option.selected = true;
                modelSelect.appendChild(option);
            });
        } catch (e) {
            console.error('Failed to load models:', e);
            // Fallback
            if (modelSelect.children.length <= 1) {
                modelSelect.innerHTML = '<option value="o1">OpenAI o1</option>';
            }
        }
    }
    loadModels();

    // ===== Output Filters =====
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const filter = btn.dataset.filter;
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const items = outputDiv.querySelectorAll('.output-item, .step-container, .sub-agent-container');
            items.forEach(item => {
                if (filter === 'all') {
                    item.style.display = '';
                } else {
                    // Check if item matches or contains the filter type
                    const matches = item.classList.contains(filter) ||
                        item.querySelector(`.output-item.${filter}`);
                    item.style.display = matches ? '' : 'none';
                }
            });
        });
    });

    // ===== Stop Button =====
    stopBtn.addEventListener('click', async () => {
        if (currentReader && currentSessionId) {
            isStopped = true;

            try {
                await fetch(`/api/stop/${currentSessionId}`, { method: 'POST' });
            } catch (error) {
                console.error('Error stopping session:', error);
            }

            currentReader.cancel();
            currentReader = null;
            currentSessionId = null;

            const stoppedItem = document.createElement('div');
            stoppedItem.className = 'output-item error';
            stoppedItem.innerHTML = '<strong>\u23F9 Stopped:</strong> Agent execution cancelled by user';
            outputDiv.appendChild(stoppedItem);

            showStatus('\u23F9 Stopped by user', 'error');
            stopElapsedTracking();
            submitBtn.disabled = false;
            stopBtn.style.display = 'none';
        }
    });

    // ===== Clear Button =====
    clearBtn.addEventListener('click', () => {
        questionInput.value = '';
        outputDiv.innerHTML = '';
        outputDiv.classList.add('empty');
        outputDiv.textContent = 'Waiting for input...';
        answerBox.style.display = 'none';
        statusDiv.textContent = '';
        statusDiv.className = 'status';
        resetRendererState();
        lastFinalAnswer = null;
    });

    // ===== History Button =====
    if (historyBtn) {
        historyBtn.addEventListener('click', () => {
            if (typeof toggleHistoryPanel === 'function') {
                toggleHistoryPanel();
            }
        });
    }

    // ===== Form Submission with SSE Streaming =====
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const question = questionInput.value.trim();
        const modelId = modelSelect.value;

        if (!question) {
            showStatus('Please enter a question', 'error');
            return;
        }

        // Reset state
        outputDiv.innerHTML = '';
        outputDiv.classList.remove('empty');
        answerBox.style.display = 'none';
        submitBtn.disabled = true;
        stopBtn.style.display = 'inline-block';
        isStopped = false;
        lastFinalAnswer = null;
        hasError = false;
        resetRendererState();

        // Show loading skeleton
        showLoadingSkeleton();
        showStatus('Running agent... This may take a moment.', 'loading');
        startElapsedTracking();

        try {
            const response = await fetch('/api/run/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question, model_id: modelId }),
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({ error: 'Unknown error' }));
                showStatus(`Error: ${escapeHtml(error.error || 'Unknown error')}`, 'error');

                const errorItem = document.createElement('div');
                errorItem.className = 'output-item error';
                errorItem.innerHTML = `<strong>Server Error:</strong> ${escapeHtml(error.error || 'Unknown error')}`;
                outputDiv.innerHTML = '';
                outputDiv.appendChild(errorItem);

                stopElapsedTracking();
                submitBtn.disabled = false;
                stopBtn.style.display = 'none';
                return;
            }

            const reader = response.body.getReader();
            currentReader = reader;
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                if (isStopped) break;

                const { done, value } = await reader.read();

                if (done) {
                    if (hasError) {
                        showStatus('\u2717 Completed with errors', 'error');
                    } else {
                        showStatus('\u2713 Completed successfully!', 'success');
                    }
                    break;
                }

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');

                for (let i = 0; i < lines.length - 1; i++) {
                    const line = lines[i];
                    if (line.startsWith('data: ')) {
                        const jsonStr = line.slice(6);
                        try {
                            const jsonData = JSON.parse(jsonStr);

                            if (jsonData.session_id) {
                                currentSessionId = jsonData.session_id;
                            } else if (jsonData.done) {
                                break;
                            } else {
                                renderOutput(jsonData);
                                // Track errors
                                if (jsonData.type === 'error') {
                                    hasError = true;
                                }
                                // Track final answer for history
                                if (jsonData.type === 'final_answer' && !jsonData.agent_name) {
                                    lastFinalAnswer = jsonData.output || jsonData.content;
                                }
                            }
                        } catch (parseErr) {
                            console.error('Failed to parse:', jsonStr, parseErr);
                        }
                    }
                }

                buffer = lines[lines.length - 1];
            }
        } catch (error) {
            showStatus(`Connection Error: ${escapeHtml(error.message)}`, 'error');

            const errorItem = document.createElement('div');
            errorItem.className = 'output-item error';
            errorItem.innerHTML = `<strong>Network Error:</strong> ${escapeHtml(error.message)}`;
            outputDiv.appendChild(errorItem);
        } finally {
            stopElapsedTracking();
            submitBtn.disabled = false;
            stopBtn.style.display = 'none';
            currentReader = null;
            currentSessionId = null;

            // Save to history
            if (typeof saveRunToHistory === 'function') {
                saveRunToHistory(questionInput.value.trim(), modelSelect.value, lastFinalAnswer);
            }
        }
    });

    // ===== Status Display =====
    function showStatus(message, type) {
        statusDiv.className = `status ${type}`;
        const statusText = document.getElementById('statusText');
        if (type === 'loading') {
            if (statusText) {
                statusText.innerHTML = `<span class="spinner"></span> ${escapeHtml(message)}`;
            } else {
                statusDiv.innerHTML = `<span class="spinner"></span> <span id="statusText">${escapeHtml(message)}</span><span id="totalElapsed" class="total-elapsed"></span>`;
            }
        } else {
            if (statusText) {
                statusText.textContent = message;
            } else {
                statusDiv.innerHTML = `<span id="statusText">${escapeHtml(message)}</span><span id="totalElapsed" class="total-elapsed"></span>`;
            }
            // Show final total elapsed on completion
            const totalEl = document.getElementById('totalElapsed');
            if (totalEl && totalStartTime) {
                const elapsed = Math.round((Date.now() - totalStartTime) / 1000);
                totalEl.textContent = formatElapsedTime(elapsed);
            }
        }
    }

})();
