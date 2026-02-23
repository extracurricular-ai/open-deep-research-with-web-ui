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
 *
 * DOM nesting strategy:
 *   The parent CodeAgent's action_step arrives AFTER the sub-agent finishes,
 *   but should visually CONTAIN the sub-agent's work. To solve this:
 *   - code_running creates a PLACEHOLDER step container when it detects an
 *     agent call (e.g. search_agent())
 *   - The sub-agent container opens inside the placeholder's step-children
 *   - When the real action_step arrives, its content MERGES into the placeholder
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

// Placeholder step container created by code_running when an agent call is
// detected. The real action_step merges into this instead of creating a new one.
let placeholderStepContainer = null;

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

    // Append to current step children or main output.
    // If a placeholder step exists, the sub-agent nests inside it.
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

        // If item is already in the DOM (e.g. placeholder was merged), skip append
        if (item.parentNode) {
            outputDiv.scrollTop = outputDiv.scrollHeight;
            return;
        }

        const target = getAppendTarget();
        target.appendChild(item);
        outputDiv.scrollTop = outputDiv.scrollHeight;
    }
}

/**
 * Handle code_running event — show a lightweight "executing code" indicator.
 * When the code calls a managed agent, creates a PLACEHOLDER step container
 * so the sub-agent's work nests inside it. When the real action_step arrives
 * later, it merges into this placeholder.
 */
function handleCodeRunning(data) {
    removePendingIndicator();

    // Extract what's being called from the code to show a meaningful label
    const code = data.code || '';
    const agentMatch = code.match(/(\w+_agent)\s*\(/);

    if (agentMatch) {
        // --- Agent call detected: create placeholder step container ---
        const label = `Calling ${agentMatch[1]}`;

        if (!totalStartTime) totalStartTime = Date.now();
        stepStartTime = Date.now();

        // Close previous step's active state
        if (currentStepContainer) {
            const prevNum = currentStepContainer.querySelector('.step-number');
            if (prevNum) prevNum.classList.remove('active');
        }

        const container = document.createElement('div');
        container.className = 'step-container';
        container.dataset.startTime = stepStartTime;
        container.dataset.placeholder = '1';

        const numCircle = document.createElement('div');
        numCircle.className = 'step-number active';
        numCircle.textContent = '...';
        container.appendChild(numCircle);

        const elapsedSpan = document.createElement('div');
        elapsedSpan.className = 'step-elapsed';
        container.appendChild(elapsedSpan);

        const header = document.createElement('div');
        header.className = 'output-item step_header';
        header.innerHTML = `<span class="spinner"></span> ${escapeHtml(label)}\u2026`;
        container.appendChild(header);

        const childrenDiv = document.createElement('div');
        childrenDiv.className = 'step-children';
        container.appendChild(childrenDiv);

        const target = getAppendTarget();
        target.appendChild(container);

        currentStepContainer = container;
        placeholderStepContainer = container;
        // Don't set pendingStepIndicator — placeholder persists until merge

    } else {
        // --- Regular code execution: lightweight spinner indicator ---
        let label = 'Executing code';
        const toolMatch = code.match(/(\w+)\s*\(/);
        if (toolMatch && toolMatch[1] !== 'print') {
            label = `Running ${toolMatch[1]}`;
        }

        const indicator = document.createElement('div');
        indicator.className = 'output-item step-pending';
        indicator.innerHTML = `<span class="spinner"></span> ${escapeHtml(label)}\u2026`;

        const target = getAppendTarget();
        target.appendChild(indicator);
        pendingStepIndicator = indicator;
    }
}

/**
 * Render an action_step event with timeline, tool calls, code, observations.
 * If a placeholderStepContainer exists and this is the matching parent step,
 * merge content into the placeholder instead of creating a new container.
 */
function renderActionStep(data) {
    // Remove pending indicator (the real step replaces it)
    removePendingIndicator();

    ensureAgentContext(data.agent_name || null);

    if (!totalStartTime) totalStartTime = Date.now();

    const isCodeAgent = !!data.code_action;
    const callsSubAgent = isCodeAgent
        && /\w+_agent\s*\(|search_agent\s*\(|text_webbrowser_agent\s*\(/.test(data.code_action || '');

    // --- Check if we should merge into a placeholder ---
    if (placeholderStepContainer && !data.agent_name && callsSubAgent) {
        return mergeIntoPlaceholder(data, callsSubAgent);
    }

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

    // Metrics bar
    if (data.duration != null || data.token_usage) {
        container.appendChild(createMetricsBar(data));
    }

    // Step children container
    const childrenDiv = document.createElement('div');
    childrenDiv.className = 'step-children';

    populateStepChildren(childrenDiv, data, isCodeAgent, callsSubAgent);

    container.appendChild(childrenDiv);
    currentStepContainer = container;

    return container;
}

/**
 * Merge an action_step's content into an existing placeholder step container.
 * The placeholder was created by handleCodeRunning and already contains the
 * sub-agent container nested inside its step-children.
 */
function mergeIntoPlaceholder(data, callsSubAgent) {
    const container = placeholderStepContainer;
    placeholderStepContainer = null;

    // Update step number
    container.dataset.stepNumber = data.step_number;
    delete container.dataset.placeholder;

    const numCircle = container.querySelector('.step-number');
    if (numCircle) {
        numCircle.textContent = data.step_number;
        numCircle.classList.remove('active');
    }

    // Update elapsed with server-side duration
    if (data.duration != null) {
        const elapsedSpan = container.querySelector('.step-elapsed');
        if (elapsedSpan) {
            elapsedSpan.textContent = formatElapsedTime(Math.round(data.duration));
            elapsedSpan.dataset.serverSet = '1';
        }
    }

    // Replace placeholder header
    const oldHeader = container.querySelector('.step_header');
    if (oldHeader) {
        const newHeader = document.createElement('div');
        newHeader.className = 'output-item step_header';
        newHeader.textContent = `Step ${data.step_number}`;
        oldHeader.replaceWith(newHeader);
    }

    // Add metrics bar after the header
    if (data.duration != null || data.token_usage) {
        const metricsBar = createMetricsBar(data);
        const header = container.querySelector('.step_header');
        if (header && header.nextSibling) {
            header.parentNode.insertBefore(metricsBar, header.nextSibling);
        } else {
            container.insertBefore(metricsBar, container.querySelector('.step-children'));
        }
    }

    // Prepend content into step-children (before the sub-agent container)
    const childrenDiv = container.querySelector('.step-children');
    const firstChild = childrenDiv ? childrenDiv.firstChild : null;

    // LLM reasoning
    if (data.model_output) {
        const thinking = document.createElement('div');
        thinking.className = 'output-item model-output';
        thinking.innerHTML = renderMarkdown(data.model_output);
        childrenDiv.insertBefore(thinking, firstChild);
    }

    // Agent Call code block (before sub-agent container)
    if (data.code_action) {
        const codeSection = createCollapsibleSection('Agent Call', data.code_action, 'code_block', false, false);
        // Insert after model_output but before sub-agent container
        const subAgentEl = childrenDiv.querySelector('.sub-agent-container');
        childrenDiv.insertBefore(codeSection, subAgentEl || firstChild);
    }

    // Error (after sub-agent container)
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

    currentStepContainer = container;

    // Return the container — renderOutput will detect it's already in DOM
    return container;
}

/**
 * Populate step-children div with the step's content (code, tools, observations, errors)
 */
function populateStepChildren(childrenDiv, data, isCodeAgent, callsSubAgent) {
    // LLM reasoning/thinking text (before tool calls or code)
    if (data.model_output) {
        const thinking = document.createElement('div');
        thinking.className = 'output-item model-output';
        thinking.innerHTML = renderMarkdown(data.model_output);
        childrenDiv.appendChild(thinking);
    }

    if (isCodeAgent) {
        // --- CodeAgent step ---
        if (callsSubAgent) {
            childrenDiv.appendChild(
                createCollapsibleSection('Agent Call', data.code_action, 'code_block', false, false)
            );
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
        const toolCalls = data.tool_calls || [];

        if (toolCalls.length === 1) {
            childrenDiv.appendChild(createToolCallItem({
                tool_name: toolCalls[0].name,
                arguments: toolCalls[0].arguments,
                result: data.observations
            }));
        } else {
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

    // Step error
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
}

/**
 * Create a metrics bar element
 */
function createMetricsBar(data) {
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
    return metrics;
}

/**
 * Render a planning_step event wrapped in a step-container with timeline visual
 */
function renderPlanningStep(data) {
    ensureAgentContext(data.agent_name || null);
    removePendingIndicator();

    const container = document.createElement('div');
    container.className = 'step-container plan-step';
    container.dataset.startTime = Date.now();

    // Plan icon instead of step number
    const numCircle = document.createElement('div');
    numCircle.className = 'step-number plan-icon';
    numCircle.textContent = '\u{1F4CB}';
    container.appendChild(numCircle);

    const elapsedSpan = document.createElement('div');
    elapsedSpan.className = 'step-elapsed';
    if (data.duration != null) {
        elapsedSpan.textContent = formatElapsedTime(Math.round(data.duration));
    }
    container.appendChild(elapsedSpan);

    // Step header
    const header = document.createElement('div');
    header.className = 'output-item step_header plan-header';
    header.textContent = data.agent_name ? `Plan (${data.agent_name})` : 'Plan';
    if (data.agent_name) {
        const badge = document.createElement('span');
        badge.className = 'agent-badge';
        badge.textContent = data.agent_name;
        header.appendChild(badge);
    }
    container.appendChild(header);

    // Metrics bar
    if (data.duration != null || data.token_usage) {
        container.appendChild(createMetricsBar(data));
    }

    // Step children with collapsible plan content
    const childrenDiv = document.createElement('div');
    childrenDiv.className = 'step-children';

    const title = data.agent_name ? `Plan (${escapeHtml(data.agent_name)})` : 'Plan';
    childrenDiv.appendChild(
        createCollapsibleSection(title, data.plan, 'plan', true, true)
    );

    container.appendChild(childrenDiv);
    currentStepContainer = container;

    return container;
}

/**
 * Render a final_answer event.
 *
 * Sub-agent final answer: appended INSIDE the sub-agent container, then
 * closes sub-agent context. Returns null (already appended).
 *
 * Top-level final answer: creates BOTH an inline compact version inside the
 * current step AND a prominent top-level block for quick copy.
 */
function renderFinalAnswer(data) {
    const answerContent = data.output || data.content || '';

    removePendingIndicator();

    // --- Sub-agent final answer ---
    if (data.agent_name) {
        ensureAgentContext(data.agent_name);

        const item = document.createElement('div');
        item.className = 'sub-agent-result';

        const preview = extractPreview(answerContent, 200);
        const isLong = answerContent.length > 300;

        if (isLong) {
            const previewDiv = document.createElement('div');
            previewDiv.className = 'output-item message';
            previewDiv.innerHTML = renderMarkdown(`**[${escapeHtml(data.agent_name)}] Result:** ${preview}\u2026`);
            item.appendChild(previewDiv);
            item.appendChild(
                createCollapsibleSection('Full Result', answerContent, 'observation', false, true)
            );
        } else {
            const msgDiv = document.createElement('div');
            msgDiv.className = 'output-item message';
            msgDiv.innerHTML = renderMarkdown(`**[${escapeHtml(data.agent_name)}] Result:** ${answerContent}`);
            item.appendChild(msgDiv);
        }

        // Append INSIDE sub-agent container BEFORE closing context
        const target = getAppendTarget();
        target.appendChild(item);

        // Close sub-agent context
        closeSubAgent();
        lastAgentName = null;

        // Return null — already appended, renderOutput should skip
        return null;
    }

    // --- Top-level final answer ---
    ensureAgentContext(null);

    // 1) Inline version inside current step (if one exists)
    if (currentStepContainer) {
        const stepChildren = currentStepContainer.querySelector('.step-children');
        if (stepChildren) {
            const inlineAnswer = createCollapsibleSection(
                'Final Answer', answerContent, 'plan', true, true
            );
            inlineAnswer.classList.add('inline-final-answer');
            stepChildren.appendChild(inlineAnswer);
        }
    }

    // 2) Top-level prominent block — placed in #answerBox (below output area)
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

    // Place in answer box below the output panel
    const answerBox = document.getElementById('answerBox');
    if (answerBox) {
        answerBox.innerHTML = '';
        answerBox.appendChild(item);
        answerBox.style.display = 'block';
    }

    return null; // Already placed — skip renderOutput append
}

// Tools that operate on the current browser page (no URL in their args)
const BROWSER_NAV_TOOLS = new Set([
    'find_on_page_ctrl_f', 'find_next', 'page_up', 'page_down'
]);

/**
 * Extract a short preview from text — first paragraph or first N chars,
 * breaking at a word boundary.
 */
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

/**
 * Extract "Address: <url>" from observation text (browser tool results)
 */
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
    placeholderStepContainer = null;
    stopElapsedTracking();
}
