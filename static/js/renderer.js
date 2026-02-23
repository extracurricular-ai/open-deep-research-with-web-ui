/**
 * Output rendering for Open Deep Research UI
 * Handles structured JSON events from the agent subprocess via SSE.
 *
 * Event types from run.py:
 *   action_step    — step_number, agent_name, model_output, tool_calls[],
 *                     code_action, observations, error, is_final_answer,
 *                     action_output, duration, token_usage
 *   planning_step  — plan, agent_name, duration, token_usage
 *   final_answer   — output, agent_name (null for top-level)
 *   code_running   — title, code (lightweight, from logger — fires before execution)
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

// Lightweight "step starting" indicator (replaced when full action_step arrives)
let pendingStepIndicator = null;

// Track the most recently closed sub-agent container so the parent CodeAgent
// step can be inserted *before* it (the parent step triggers the sub-agent,
// so visually it should appear above the sub-agent's work).
let lastClosedSubAgentContainer = null;

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
    lastClosedSubAgentContainer = subAgentContainer;
    subAgentContainer = null;
    currentStepContainer = null;
}

/**
 * Remove pending step indicator if present
 */
function removePendingIndicator() {
    if (pendingStepIndicator && pendingStepIndicator.parentNode) {
        pendingStepIndicator.remove();
    }
    pendingStepIndicator = null;
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
        case 'code_running':
            // Lightweight indicator — code is about to execute
            handleCodeRunning(data);
            outputDiv.scrollTop = outputDiv.scrollHeight;
            return;

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
        removePendingIndicator();
        const target = getAppendTarget();

        // If this is a CodeAgent step that called a sub-agent, insert it
        // BEFORE the sub-agent container (the parent triggers the sub-agent,
        // so it should appear above the sub-agent's work).
        if (item.dataset && item.dataset.callsSubAgent === '1'
            && lastClosedSubAgentContainer
            && lastClosedSubAgentContainer.parentNode === target) {
            target.insertBefore(item, lastClosedSubAgentContainer);
            lastClosedSubAgentContainer = null;
        } else {
            target.appendChild(item);
        }

        outputDiv.scrollTop = outputDiv.scrollHeight;
    }
}

/**
 * Handle code_running event — show a lightweight "executing code" indicator.
 * Removed when the next action_step/planning_step arrives.
 */
function handleCodeRunning(data) {
    removePendingIndicator();

    // Extract what's being called from the code to show a meaningful label
    const code = data.code || '';
    let label = 'Executing code';
    const agentMatch = code.match(/(\w+_agent)\s*\(/);
    if (agentMatch) {
        label = `Calling ${agentMatch[1]}`;
    } else {
        // Look for tool calls like visualizer(...) or inspect_file_as_text(...)
        const toolMatch = code.match(/(\w+)\s*\(/);
        if (toolMatch && toolMatch[1] !== 'print') {
            label = `Running ${toolMatch[1]}`;
        }
    }

    const indicator = document.createElement('div');
    indicator.className = 'output-item step-pending';
    indicator.innerHTML = `<span class="spinner"></span> ${escapeHtml(label)}\u2026`;

    const target = getAppendTarget();
    target.appendChild(indicator);
    pendingStepIndicator = indicator;
}

/**
 * Render an action_step event with timeline, tool calls, code, observations.
 * Always creates its own step container.
 */
function renderActionStep(data) {
    // Remove pending indicator (the real step replaces it)
    removePendingIndicator();

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
    container.dataset.stepNumber = data.step_number;

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

    // LLM reasoning/thinking text (before tool calls or code)
    if (data.model_output) {
        const thinking = document.createElement('div');
        thinking.className = 'output-item model-output';
        thinking.innerHTML = renderMarkdown(data.model_output);
        childrenDiv.appendChild(thinking);
    }

    const isCodeAgent = !!data.code_action;
    // Detect if code calls a managed agent (sub-agent). When it does,
    // the sub-agent's steps are already rendered as nested UI elements,
    // so the observations (full sub-agent dump) are duplicate.
    const callsSubAgent = isCodeAgent
        && /\w+_agent\s*\(|search_agent\s*\(|text_webbrowser_agent\s*\(/.test(data.code_action || '');

    if (isCodeAgent) {
        // --- CodeAgent step ---
        // code_action is the Python code, observations is execution logs,
        // action_output is the return value. tool_calls[0] is always
        // python_interpreter which is redundant — skip it.
        container.dataset.callsSubAgent = callsSubAgent ? '1' : '';

        if (callsSubAgent) {
            // Show code collapsed with "Agent Call" label
            childrenDiv.appendChild(
                createCollapsibleSection('Agent Call', data.code_action, 'code_block', false, false)
            );
            // Skip the huge Execution Log — sub-agent steps shown inline above.
            // If there was an error, it's shown separately below.
        } else {
            childrenDiv.appendChild(
                createCollapsibleSection('Code', data.code_action, 'code_block', false, false)
            );
            if (data.observations) {
                childrenDiv.appendChild(
                    createCollapsibleSection('Execution Log', data.observations, 'observation', false, false)
                );
            }
        }
        if (data.action_output && !data.is_final_answer) {
            childrenDiv.appendChild(
                createCollapsibleSection('Return Value', data.action_output, 'code_execution', false, false)
            );
        }
    } else {
        // --- ToolCallingAgent step ---
        // tool_calls are the invocations, observations is the concatenated
        // raw result from executing those tools (str(tool_result)).
        // When there's a single tool call, nest the result inside it.
        // When there are multiple, show tool calls then a combined result.
        const toolCalls = data.tool_calls || [];

        if (toolCalls.length === 1) {
            // Single tool call — pair invocation + result together
            const toolItem = createToolCallItem({
                tool_name: toolCalls[0].name,
                arguments: toolCalls[0].arguments,
                result: data.observations
            });
            childrenDiv.appendChild(toolItem);
        } else {
            // Multiple tool calls — show each, then combined result
            toolCalls.forEach(tc => {
                childrenDiv.appendChild(createToolCallItem({
                    tool_name: tc.name,
                    arguments: tc.arguments
                }));
            });
            if (data.observations) {
                childrenDiv.appendChild(
                    createCollapsibleSection('Results', data.observations, 'observation', false, true)
                );
            }
        }
    }

    // Step error — simplify when the error is from a sub-agent timeout
    if (data.error) {
        let errorText = data.error;
        if (callsSubAgent && /execution time|max.steps|timed?\s*out/i.test(errorText)) {
            errorText = 'Sub-agent did not finish in time';
        }
        const errorDiv = document.createElement('div');
        errorDiv.className = 'output-item error';
        errorDiv.textContent = errorText;
        childrenDiv.appendChild(errorDiv);
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

    // Remove pending indicator
    removePendingIndicator();

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

    // Remove pending indicator
    removePendingIndicator();

    // Sub-agent final answer — show as collapsible result.
    // Sub-agent results can be very long (especially on failure when the
    // agent dumps its internal planning state), so always collapse.
    if (data.agent_name) {
        ensureAgentContext(data.agent_name);

        const item = document.createElement('div');
        item.className = 'sub-agent-result';

        // Extract a short preview (first ~200 chars, first paragraph)
        const preview = extractPreview(answerContent, 200);
        const isLong = answerContent.length > 300;

        if (isLong) {
            // Long result — show preview + collapsible full text
            const previewDiv = document.createElement('div');
            previewDiv.className = 'output-item message';
            previewDiv.innerHTML = renderMarkdown(`**[${escapeHtml(data.agent_name)}] Result:** ${preview}\u2026`);
            item.appendChild(previewDiv);
            item.appendChild(
                createCollapsibleSection('Full Result', answerContent, 'observation', false, true)
            );
        } else {
            item.innerHTML = '';
            const msgDiv = document.createElement('div');
            msgDiv.className = 'output-item message';
            msgDiv.innerHTML = renderMarkdown(`**[${escapeHtml(data.agent_name)}] Result:** ${answerContent}`);
            item.appendChild(msgDiv);
        }

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

// Tools that operate on the current browser page (no URL in their args)
const BROWSER_NAV_TOOLS = new Set([
    'find_on_page_ctrl_f', 'find_next', 'page_up', 'page_down'
]);

/**
 * Extract "Address: <url>" from observation text (browser tool results)
 */
/**
 * Extract a short preview from text — first paragraph or first N chars,
 * breaking at a word boundary.
 */
function extractPreview(text, maxLen) {
    if (!text) return '';
    // Try to find first paragraph break
    const paraEnd = text.indexOf('\n\n');
    if (paraEnd > 0 && paraEnd <= maxLen) {
        return text.substring(0, paraEnd).trim();
    }
    if (text.length <= maxLen) return text;
    // Break at word boundary
    const truncated = text.substring(0, maxLen);
    const lastSpace = truncated.lastIndexOf(' ');
    return lastSpace > maxLen * 0.5 ? truncated.substring(0, lastSpace) : truncated;
}

function extractPageUrl(text) {
    if (!text) return null;
    const m = text.match(/^Address:\s*(https?:\/\/\S+)/m);
    return m ? m[1] : null;
}

/**
 * Create a tool_call output item with syntax-highlighted args.
 * If data.result is provided, nests a collapsible result section inside.
 */
function createToolCallItem(data) {
    const item = document.createElement('div');
    item.className = 'output-item tool_call';

    const nameDiv = document.createElement('div');
    nameDiv.className = 'tool-name';
    nameDiv.textContent = data.tool_name || 'Unknown tool';
    item.appendChild(nameDiv);

    // For browser nav tools, show which page they're operating on
    if (BROWSER_NAV_TOOLS.has(data.tool_name) && data.result) {
        const pageUrl = extractPageUrl(data.result);
        if (pageUrl) {
            const urlDiv = document.createElement('div');
            urlDiv.className = 'tool-page-url';
            urlDiv.textContent = pageUrl;
            item.appendChild(urlDiv);
        }
    }

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

    // Nested result (when single tool call, observations is paired here)
    if (data.result) {
        item.appendChild(
            createCollapsibleSection('Result', data.result, 'observation', false, true)
        );
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
    pendingStepIndicator = null;
    lastClosedSubAgentContainer = null;
    stopElapsedTracking();
}
