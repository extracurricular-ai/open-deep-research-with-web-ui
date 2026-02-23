/**
 * Output rendering for Open Deep Research UI
 * Handles structured JSON events from the agent subprocess via SSE.
 *
 * Event types from run.py:
 *   action_step    — step_number, agent_name, tool_calls[], code_action,
 *                     observations, error, is_final_answer, action_output,
 *                     duration, token_usage
 *   planning_step  — plan, agent_name, duration, token_usage
 *   final_answer   — output, agent_name (null for top-level)
 *   info           — content
 *   error          — content
 *   message        — content
 */

// State for step timeline
let currentStepContainer = null;
let stepStartTime = null;
let totalStartTime = null;
let elapsedInterval = null;
let skeletonShown = false;

// Track which agents have sub-agent containers
let lastAgentName = null; // null = top-level agent
let subAgentContainer = null;

/**
 * Get the append target — inside sub-agent container if active, else output div
 */
function getAppendTarget() {
    if (subAgentContainer && lastAgentName) {
        return subAgentContainer.querySelector('.sub-agent-children') || subAgentContainer;
    }
    return document.getElementById('output');
}

/**
 * Ensure we're in the right agent context. If agent_name changes,
 * open or close sub-agent containers as needed.
 */
function ensureAgentContext(agentName) {
    if (agentName === lastAgentName) return;

    if (agentName && !lastAgentName) {
        // Entering a sub-agent
        openSubAgent(agentName);
    } else if (!agentName && lastAgentName) {
        // Returning to top-level agent
        closeSubAgent();
    } else if (agentName !== lastAgentName) {
        // Switching between sub-agents
        closeSubAgent();
        openSubAgent(agentName);
    }
    lastAgentName = agentName;
}

function openSubAgent(agentName) {
    const container = document.createElement('div');
    container.className = 'sub-agent-container';

    const header = document.createElement('div');
    header.className = 'sub-agent-header';
    header.innerHTML = `<span>\u{1F916}</span> <span>Sub-agent: ${escapeHtml(agentName)}</span>`;
    container.appendChild(header);

    const childrenDiv = document.createElement('div');
    childrenDiv.className = 'sub-agent-children';
    container.appendChild(childrenDiv);

    // Append to current step children or main output
    const target = currentStepContainer
        ? (currentStepContainer.querySelector('.step-children') || currentStepContainer)
        : document.getElementById('output');
    target.appendChild(container);

    subAgentContainer = container;
    currentStepContainer = null; // Reset step for sub-agent's own steps
}

function closeSubAgent() {
    subAgentContainer = null;
    currentStepContainer = null;
}

/**
 * Render a structured output event from the SSE stream
 */
function renderOutput(data) {
    const outputDiv = document.getElementById('output');
    outputDiv.classList.remove('empty');

    // Remove skeleton on first real output
    if (skeletonShown) {
        const skeleton = outputDiv.querySelector('.skeleton-container');
        if (skeleton) skeleton.remove();
        skeletonShown = false;
    }

    let item;

    switch (data.type) {
        case 'action_step':
            item = renderActionStep(data);
            break;

        case 'planning_step':
            item = renderPlanningStep(data);
            break;

        case 'final_answer':
            item = renderFinalAnswer(data);
            break;

        case 'info':
            item = document.createElement('div');
            item.className = 'output-item info';
            item.textContent = data.content;
            break;

        case 'error':
            item = document.createElement('div');
            item.className = 'output-item error';
            item.textContent = data.content;
            break;

        case 'message':
        default:
            item = document.createElement('div');
            item.className = 'output-item message';
            item.innerHTML = renderMarkdown(data.content || JSON.stringify(data));
            break;
    }

    if (item) {
        const target = getAppendTarget();
        target.appendChild(item);
        outputDiv.scrollTop = outputDiv.scrollHeight;
    }
}

/**
 * Render an action_step event with timeline, tool calls, code, observations
 */
function renderActionStep(data) {
    ensureAgentContext(data.agent_name || null);

    if (!totalStartTime) totalStartTime = Date.now();

    // Close previous step's active state
    if (currentStepContainer) {
        const prevNum = currentStepContainer.querySelector('.step-number');
        if (prevNum) prevNum.classList.remove('active');
    }

    stepStartTime = Date.now();

    // Create step timeline container
    const container = document.createElement('div');
    container.className = 'step-container';
    container.dataset.startTime = stepStartTime;

    const numCircle = document.createElement('div');
    numCircle.className = 'step-number active';
    numCircle.textContent = data.step_number;
    container.appendChild(numCircle);

    const elapsedSpan = document.createElement('div');
    elapsedSpan.className = 'step-elapsed';
    // Use server-side duration if available
    if (data.duration != null) {
        elapsedSpan.textContent = formatElapsedTime(Math.round(data.duration));
        numCircle.classList.remove('active');
    }
    container.appendChild(elapsedSpan);

    // Step header
    const header = document.createElement('div');
    header.className = 'output-item step_header';
    header.textContent = `Step ${data.step_number}`;
    if (data.agent_name) {
        const badge = document.createElement('span');
        badge.className = 'agent-badge';
        badge.textContent = data.agent_name;
        header.appendChild(badge);
    }
    container.appendChild(header);

    // Metrics bar (duration + token usage)
    if (data.duration != null || data.token_usage) {
        const metrics = document.createElement('div');
        metrics.className = 'step-metrics';
        const parts = [];
        if (data.duration != null) parts.push(`Duration: ${data.duration.toFixed(1)}s`);
        if (data.token_usage) {
            if (data.token_usage.input_tokens != null) {
                parts.push(`Tokens: ${data.token_usage.input_tokens.toLocaleString()} in / ${data.token_usage.output_tokens.toLocaleString()} out`);
            }
        }
        metrics.textContent = parts.join(' | ');
        container.appendChild(metrics);
    }

    // Step children container
    const childrenDiv = document.createElement('div');
    childrenDiv.className = 'step-children';

    // Code action (CodeAgent steps)
    if (data.code_action) {
        childrenDiv.appendChild(
            createCollapsibleSection('Code', data.code_action, 'code_block', false, false)
        );
    }

    // Tool calls (ToolCallingAgent steps)
    if (data.tool_calls && data.tool_calls.length > 0) {
        data.tool_calls.forEach(tc => {
            childrenDiv.appendChild(createToolCallItem({
                tool_name: tc.name,
                arguments: tc.arguments
            }));
        });
    }

    // Observations
    if (data.observations) {
        childrenDiv.appendChild(
            createCollapsibleSection('Observations', data.observations, 'observation', false, true)
        );
    }

    // Step error
    if (data.error) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'output-item error';
        errorDiv.textContent = data.error;
        childrenDiv.appendChild(errorDiv);
    }

    // Action output (non-final)
    if (data.action_output && !data.is_final_answer) {
        childrenDiv.appendChild(
            createCollapsibleSection('Output', data.action_output, 'code_execution', false, false)
        );
    }

    container.appendChild(childrenDiv);
    currentStepContainer = container;

    return container;
}

/**
 * Render a planning_step event
 */
function renderPlanningStep(data) {
    ensureAgentContext(data.agent_name || null);

    const container = document.createElement('div');
    container.className = 'planning-step-container';

    const title = data.agent_name ? `Plan (${escapeHtml(data.agent_name)})` : 'Plan';
    const section = createCollapsibleSection(title, data.plan, 'plan', true, true);
    container.appendChild(section);

    // Metrics bar
    if (data.duration != null || data.token_usage) {
        const metrics = document.createElement('div');
        metrics.className = 'step-metrics';
        const parts = [];
        if (data.duration != null) parts.push(`Duration: ${data.duration.toFixed(1)}s`);
        if (data.token_usage && data.token_usage.input_tokens != null) {
            parts.push(`Tokens: ${data.token_usage.input_tokens.toLocaleString()} in / ${data.token_usage.output_tokens.toLocaleString()} out`);
        }
        metrics.textContent = parts.join(' | ');
        container.appendChild(metrics);
    }

    return container;
}

/**
 * Render a final_answer event
 */
function renderFinalAnswer(data) {
    const answerContent = data.output || data.content || '';

    // Sub-agent final answer — show as informational message
    if (data.agent_name) {
        ensureAgentContext(data.agent_name);
        const item = document.createElement('div');
        item.className = 'output-item message';
        item.innerHTML = renderMarkdown(`**[${escapeHtml(data.agent_name)}] Result:** ${answerContent}`);
        // Close sub-agent context — next event will be from parent
        closeSubAgent();
        lastAgentName = null;
        return item;
    }

    // Top-level final answer
    ensureAgentContext(null);

    const item = document.createElement('div');
    item.className = 'output-item final_answer';

    const headerDiv = document.createElement('div');
    headerDiv.className = 'final-answer-header';
    headerDiv.textContent = 'Final Answer';
    item.appendChild(headerDiv);

    const contentDiv = document.createElement('div');
    contentDiv.className = 'final-answer-content';
    contentDiv.innerHTML = renderMarkdown(answerContent);
    item.appendChild(contentDiv);

    const copyBtn = document.createElement('button');
    copyBtn.className = 'copy-btn';
    copyBtn.textContent = 'Copy Answer';
    copyBtn.addEventListener('click', () => copyToClipboard(answerContent, copyBtn));
    item.appendChild(copyBtn);

    // Update the answer box
    const answerText = document.getElementById('answerText');
    const answerBox = document.getElementById('answerBox');
    if (answerText && answerBox) {
        answerText.innerHTML = renderMarkdown(answerContent);
        answerBox.style.display = 'block';
    }

    return item;
}

/**
 * Create a tool_call output item with syntax-highlighted args
 */
function createToolCallItem(data) {
    const item = document.createElement('div');
    item.className = 'output-item tool_call';

    const nameDiv = document.createElement('div');
    nameDiv.className = 'tool-name';
    nameDiv.textContent = data.tool_name || 'Unknown tool';
    item.appendChild(nameDiv);

    if (data.arguments != null) {
        const jsonStr = typeof data.arguments === 'string'
            ? data.arguments
            : JSON.stringify(data.arguments, null, 2);

        const argsDiv = document.createElement('div');
        argsDiv.className = 'tool-args';
        argsDiv.innerHTML = highlightJson(jsonStr);
        item.appendChild(argsDiv);

        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';
        copyBtn.textContent = 'Copy';
        copyBtn.addEventListener('click', () => copyToClipboard(jsonStr, copyBtn));
        item.appendChild(copyBtn);
    }

    return item;
}

/**
 * Create a collapsible section with optional markdown rendering
 */
function createCollapsibleSection(title, content, type, expanded, isMarkdown) {
    const section = document.createElement('div');
    section.className = `output-item ${type} collapsible-section`;

    const header = document.createElement('div');
    header.className = `collapsible-header ${expanded ? 'open' : ''}`;

    const toggle = document.createElement('span');
    toggle.className = 'toggle';
    toggle.textContent = '\u25B6';
    header.appendChild(toggle);

    const titleSpan = document.createElement('span');
    titleSpan.textContent = title;
    header.appendChild(titleSpan);

    // Copy button in header
    const copyBtn = document.createElement('button');
    copyBtn.className = 'copy-btn';
    copyBtn.textContent = 'Copy';
    copyBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        copyToClipboard(content || '', copyBtn);
    });
    header.appendChild(copyBtn);

    const contentDiv = document.createElement('div');
    contentDiv.className = 'collapsible-content';

    if (isMarkdown && content) {
        const mdDiv = document.createElement('div');
        mdDiv.className = 'markdown-body';
        mdDiv.innerHTML = renderMarkdown(content);
        contentDiv.appendChild(mdDiv);
    } else {
        const pre = document.createElement('pre');
        pre.textContent = content || '';
        contentDiv.appendChild(pre);
    }

    // Toggle handler with JS-driven height
    header.addEventListener('click', () => {
        const isOpen = header.classList.toggle('open');
        if (isOpen) {
            contentDiv.classList.add('open');
            contentDiv.style.maxHeight = contentDiv.scrollHeight + 'px';
        } else {
            contentDiv.classList.remove('open');
            contentDiv.style.maxHeight = '0';
        }
    });

    section.appendChild(header);
    section.appendChild(contentDiv);

    // If initially expanded, set height after DOM insertion
    if (expanded) {
        requestAnimationFrame(() => {
            contentDiv.classList.add('open');
            contentDiv.style.maxHeight = contentDiv.scrollHeight + 'px';
        });
    }

    // ResizeObserver to handle dynamic content changes
    if (typeof ResizeObserver !== 'undefined') {
        const resizeObserver = new ResizeObserver(() => {
            if (header.classList.contains('open')) {
                contentDiv.style.maxHeight = contentDiv.scrollHeight + 'px';
            }
        });
        resizeObserver.observe(contentDiv);
    }

    return section;
}

/**
 * Show loading skeleton in the output area
 */
function showLoadingSkeleton() {
    const outputDiv = document.getElementById('output');
    outputDiv.classList.remove('empty');
    outputDiv.innerHTML = `
        <div class="skeleton-container">
            <div class="skeleton-step">
                <div class="skeleton-circle skeleton-pulse"></div>
                <div class="skeleton-line skeleton-pulse" style="width: 40%"></div>
            </div>
            <div class="skeleton-card skeleton-pulse"></div>
            <div class="skeleton-card skeleton-pulse" style="width: 80%; margin-left: 42px;"></div>
            <div class="skeleton-step" style="margin-top: 20px;">
                <div class="skeleton-circle skeleton-pulse"></div>
                <div class="skeleton-line skeleton-pulse" style="width: 35%"></div>
            </div>
            <div class="skeleton-card skeleton-pulse" style="width: 90%; margin-left: 42px;"></div>
        </div>
    `;
    skeletonShown = true;
}

/**
 * Start elapsed time tracking interval
 */
function startElapsedTracking() {
    totalStartTime = Date.now();
    elapsedInterval = setInterval(() => {
        if (currentStepContainer) {
            updateStepElapsed(currentStepContainer);
        }
        updateTotalElapsed();
    }, 1000);
}

/**
 * Stop elapsed time tracking
 */
function stopElapsedTracking() {
    if (elapsedInterval) {
        clearInterval(elapsedInterval);
        elapsedInterval = null;
    }
    if (currentStepContainer) {
        const numEl = currentStepContainer.querySelector('.step-number');
        if (numEl) numEl.classList.remove('active');
        updateStepElapsed(currentStepContainer);
    }
}

/**
 * Update elapsed time display for a step container
 */
function updateStepElapsed(container) {
    const startTime = parseInt(container.dataset.startTime);
    if (!startTime) return;
    const elapsed = Math.round((Date.now() - startTime) / 1000);
    const elapsedEl = container.querySelector('.step-elapsed');
    if (elapsedEl && !elapsedEl.dataset.serverSet) {
        elapsedEl.textContent = formatElapsedTime(elapsed);
    }
}

/**
 * Update total elapsed time in the status bar
 */
function updateTotalElapsed() {
    if (!totalStartTime) return;
    const elapsed = Math.round((Date.now() - totalStartTime) / 1000);
    const totalEl = document.getElementById('totalElapsed');
    if (totalEl) totalEl.textContent = formatElapsedTime(elapsed);
}

/**
 * Reset all renderer state for a new run
 */
function resetRendererState() {
    currentStepContainer = null;
    stepStartTime = null;
    totalStartTime = null;
    skeletonShown = false;
    lastAgentName = null;
    subAgentContainer = null;
    stopElapsedTracking();
}
