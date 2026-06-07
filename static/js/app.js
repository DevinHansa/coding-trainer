/* ═══════════════════════════════════════════════════════════
   SDE PREP — Client-Side Application Logic
   ═══════════════════════════════════════════════════════════ */

let editor = null;
let timerInterval = null;
let elapsedSeconds = 0;
let hintsUsed = 0;
let isSubmitting = false;

// ── Theme Toggle ──────────────────────────────────────────
function toggleTheme() {
    const html = document.documentElement;
    const isDark = html.getAttribute('data-theme') === 'dark';
    if (isDark) {
        html.removeAttribute('data-theme');
        localStorage.setItem('theme', 'light');
        document.getElementById('themeIcon').textContent = '🌙';
    } else {
        html.setAttribute('data-theme', 'dark');
        localStorage.setItem('theme', 'dark');
        document.getElementById('themeIcon').textContent = '☀️';
    }
}

// Restore saved theme before paint
(function() {
    const saved = localStorage.getItem('theme');
    if (saved === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
    }
})();

// ── Gemini Status Check ───────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    checkGeminiStatus();
    // Update theme icon to match current state
    const icon = document.getElementById('themeIcon');
    if (icon) {
        icon.textContent = document.documentElement.getAttribute('data-theme') === 'dark' ? '☀️' : '🌙';
    }
});

async function checkGeminiStatus() {
    const statusEl = document.getElementById('geminiStatus');
    if (!statusEl) return;
    try {
        const resp = await fetch('/api/gemini-status');
        const data = await resp.json();
        const dot = statusEl.querySelector('.status-dot');
        const text = statusEl.querySelector('.status-text');
        if (data.connected) {
            dot.classList.add('connected');
            dot.classList.remove('disconnected');
            if (data.throttled) {
                text.textContent = `AI Ready — Quota Limited`;
            } else {
                text.textContent = `AI Ready (${data.model || 'Gemini'})`;
            }
        } else {
            dot.classList.add('disconnected');
            dot.classList.remove('connected');
            text.textContent = 'AI Offline';
        }
    } catch (e) {
        const dot = statusEl.querySelector('.status-dot');
        const text = statusEl.querySelector('.status-text');
        if (dot) dot.classList.add('disconnected');
        if (text) text.textContent = 'AI Offline';
    }
}

// ── Exercise Initialization ───────────────────────────────
function initExercise(category) {
    const editorEl = document.getElementById('codeEditor');
    if (!editorEl) return;

    const mode = category === 'sql' ? 'text/x-sql' : 'python';
    editor = CodeMirror(editorEl, {
        mode: mode,
        theme: 'material-darker',
        lineNumbers: true,
        lineWrapping: true,
        tabSize: 4,
        indentWithTabs: false,
        placeholder: category === 'sql'
            ? '-- Write your SQL query here...'
            : category === 'pyspark'
                ? '# Write your PySpark code here...'
                : '# Write your Python code here...',
        extraKeys: {
            'Ctrl-Enter': () => submitCode(),
            'Ctrl-Shift-T': () => runTests(),
            'Tab': (cm) => cm.replaceSelection('    ', 'end')
        }
    });

    startTimer();

    document.getElementById('submitBtn')?.addEventListener('click', submitCode);
    document.getElementById('runTestsBtn')?.addEventListener('click', runTests);
    document.getElementById('hintBtn')?.addEventListener('click', requestHint);
    document.getElementById('clearBtn')?.addEventListener('click', () => {
        editor.setValue('');
        editor.focus();
    });
    document.getElementById('resetBtn')?.addEventListener('click', () => {
        editor.setValue('');
        hintsUsed = 0;
        updateHintCounter();
        document.getElementById('hintDisplay').style.display = 'none';
        document.getElementById('feedbackPanel').style.display = 'none';
        document.getElementById('testResultsCard').style.display = 'none';
        document.getElementById('mcqPanel').style.display = 'none';
        document.getElementById('consoleOutput').innerHTML = '<div class="console-placeholder">Run tests or submit to see output here...</div>';
        document.getElementById('consoleStatus').textContent = 'Ready';
        document.getElementById('consoleStatus').className = 'console-status';
        editor.focus();
    });
    document.getElementById('retryBtn')?.addEventListener('click', () => {
        document.getElementById('feedbackPanel').style.display = 'none';
        editor.focus();
    });
    document.getElementById('showSolutionBtn')?.addEventListener('click', () => {
        const section = document.getElementById('solutionSection');
        section.style.display = section.style.display === 'none' ? 'block' : 'none';
    });
}

// ── Timer ──────────────────────────────────────────────────
function startTimer() {
    const display = document.getElementById('timerDisplay');
    if (!display) return;
    timerInterval = setInterval(() => {
        elapsedSeconds++;
        const mins = Math.floor(elapsedSeconds / 60).toString().padStart(2, '0');
        const secs = (elapsedSeconds % 60).toString().padStart(2, '0');
        display.textContent = `${mins}:${secs}`;
    }, 1000);
}

function stopTimer() {
    if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
}

// ── Run Tests (no AI) ─────────────────────────────────────
async function runTests() {
    if (!editor) return;
    const code = editor.getValue().trim();
    if (!code) { showToast('Write some code first!', 'warning'); return; }

    const exerciseId = document.querySelector('.exercise-page')?.dataset.exerciseId;
    if (!exerciseId) return;

    const btn = document.getElementById('runTestsBtn');
    const consoleStatus = document.getElementById('consoleStatus');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Running...';
    consoleStatus.textContent = 'Running...';
    consoleStatus.className = 'console-status running';

    try {
        const resp = await fetch('/run-tests', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ exercise_id: parseInt(exerciseId), code: code })
        });
        const result = await resp.json();
        displayTestResults(result);
        displayConsoleOutput(result);
    } catch (err) {
        showToast('Failed to run tests.', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '▶ Run Tests';
    }
}

function displayTestResults(result) {
    const card = document.getElementById('testResultsCard');
    const list = document.getElementById('testResultsList');
    const consoleStatus = document.getElementById('consoleStatus');

    if (!result.test_results || result.test_results.length === 0) {
        card.style.display = 'none';
        return;
    }

    list.innerHTML = result.test_results.map(t => `
        <div class="test-result-item ${t.passed ? 'pass' : 'fail'}">
            <span class="test-result-icon">${t.passed ? '✅' : '❌'}</span>
            <span class="test-result-name">${escapeHtml(t.name)}</span>
            <span class="test-result-detail">${t.passed ? '' : escapeHtml((t.actual || '').substring(0, 80))}</span>
        </div>
    `).join('');
    card.style.display = 'block';

    const allPassed = result.test_results.every(t => t.passed);
    consoleStatus.textContent = allPassed ? 'All tests passed' : 'Some tests failed';
    consoleStatus.className = `console-status ${allPassed ? 'passed' : 'failed'}`;
}

function displayConsoleOutput(result) {
    const output = document.getElementById('consoleOutput');
    let lines = [];

    if (result.error) {
        lines.push(`<div class="console-line error">Error: ${escapeHtml(result.error)}</div>`);
    }
    if (result.actual_output) {
        lines.push(`<div class="console-line">${escapeHtml(result.actual_output)}</div>`);
    }
    if (result.execution_time_ms) {
        lines.push(`<div class="console-line success">Execution time: ${result.execution_time_ms}ms</div>`);
    }
    if (result.patterns_found?.length) {
        lines.push(`<div class="console-line success">Patterns found: ${result.patterns_found.join(', ')}</div>`);
    }
    if (result.patterns_missing?.length) {
        lines.push(`<div class="console-line error">Missing patterns: ${result.patterns_missing.join(', ')}</div>`);
    }

    output.innerHTML = lines.length ? lines.join('') : '<div class="console-placeholder">No output.</div>';
}

// ── Submit Code ───────────────────────────────────────────
async function submitCode() {
    if (isSubmitting || !editor) return;
    const code = editor.getValue().trim();
    if (!code) { showToast('Write some code before submitting!', 'warning'); return; }

    const exerciseId = document.querySelector('.exercise-page')?.dataset.exerciseId;
    if (!exerciseId) return;

    const submitBtn = document.getElementById('submitBtn');
    isSubmitting = true;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Evaluating...';
    stopTimer();

    try {
        const resp = await fetch('/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                exercise_id: parseInt(exerciseId),
                code: code,
                logical_steps: '',
                time_spent: elapsedSeconds,
                hints_used: hintsUsed
            })
        });
        const result = await resp.json();

        // Display test results + console
        if (result.execution) {
            displayTestResults(result.execution);
            displayConsoleOutput(result.execution);
        }

        // Display AI feedback
        displayFeedback(result);

        // Check for MCQ drill trigger
        if (result.failure_action?.type === 'mcq_drill') {
            displayMCQDrill(result.failure_action.drill, result.failure_action.weakness_tag);
        }
    } catch (err) {
        showToast('Failed to submit.', 'error');
        startTimer();
    } finally {
        isSubmitting = false;
        submitBtn.disabled = false;
        submitBtn.innerHTML = 'Submit for Feedback';
    }
}

// ── Display Feedback ──────────────────────────────────────
function displayFeedback(result) {
    const panel = document.getElementById('feedbackPanel');
    const header = document.getElementById('feedbackHeader');
    const scoreEl = document.getElementById('feedbackScore');
    const statusEl = document.getElementById('feedbackStatus');

    const score = result.score || 0;
    const passed = score >= 70;
    header.className = `feedback-header ${passed ? 'passed' : score >= 40 ? 'warning' : 'failed'}`;
    scoreEl.textContent = `${score}%`;
    statusEl.textContent = passed ? 'Passed! Strong work.' : 'Keep pushing. Each attempt builds skill.';

    // What worked
    const whatWorked = document.getElementById('whatWorked');
    if (result.what_worked) {
        document.getElementById('whatWorkedText').textContent = result.what_worked;
        whatWorked.style.display = 'block';
    } else { whatWorked.style.display = 'none'; }

    // Efficiency notes
    const effNotes = document.getElementById('efficiencyNotes');
    if (result.efficiency_notes) {
        document.getElementById('efficiencyText').textContent = result.efficiency_notes;
        effNotes.style.display = 'block';
    } else { effNotes.style.display = 'none'; }

    // Issues
    const issuesSection = document.getElementById('issuesSection');
    const issuesList = document.getElementById('issuesList');
    if (result.issues?.length) {
        issuesList.innerHTML = result.issues.map(issue => {
            if (typeof issue === 'string') return `<div class="issue-card"><p>${escapeHtml(issue)}</p></div>`;
            return `
                <div class="issue-card">
                    <h4>${issue.severity ? `<span class="issue-severity ${issue.severity}">${issue.severity}</span> ` : ''}${escapeHtml(issue.issue || '')}</h4>
                    ${issue.what_they_wrote || issue.what_it_should_be ? `
                    <div class="issue-comparison">
                        <div class="issue-yours"><small>Your code:</small><br><code>${escapeHtml(issue.what_they_wrote || 'N/A')}</code></div>
                        <div class="issue-correct"><small>Should be:</small><br><code>${escapeHtml(issue.what_it_should_be || 'N/A')}</code></div>
                    </div>` : ''}
                    ${issue.explanation ? `<div class="issue-bridge"><strong>Why it matters:</strong> ${escapeHtml(issue.explanation)}</div>` : ''}
                </div>`;
        }).join('');
        issuesSection.style.display = 'block';
    } else { issuesSection.style.display = 'none'; }

    // Overall feedback
    document.getElementById('overallFeedbackText').textContent = result.overall_feedback || result.error || 'Check your .env for the Gemini API key.';

    // Solution
    if (result.solution) document.getElementById('solutionCode').textContent = result.solution;

    // XP update
    if (result.rank_info) {
        const rankMini = document.querySelector('.rank-badge-mini');
        if (rankMini) {
            rankMini.innerHTML = `<span>${result.rank_info.icon}</span><span class="rank-xp">${result.rank_info.total_xp} XP</span>`;
        }
    }

    panel.style.display = 'block';
    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── MCQ Drill ─────────────────────────────────────────────
function displayMCQDrill(drill, weaknessTag) {
    const panel = document.getElementById('mcqPanel');
    if (!panel || !drill) return;

    document.getElementById('mcqContext').textContent =
        `You're struggling with "${weaknessTag}". Let's reinforce the concept.`;
    document.getElementById('mcqQuestion').textContent = drill.question || '';

    const optionsEl = document.getElementById('mcqOptions');
    optionsEl.innerHTML = (drill.options || []).map((opt, i) =>
        `<div class="mcq-option" data-index="${i}" onclick="selectMCQ(this, ${i}, ${drill.correct_index}, '${escapeHtml(weaknessTag)}')">${escapeHtml(opt)}</div>`
    ).join('');

    document.getElementById('mcqExplanation').style.display = 'none';
    document.getElementById('mcqContinueBtn').style.display = 'none';
    panel.style.display = 'block';
    panel.scrollIntoView({ behavior: 'smooth' });
}

function selectMCQ(el, selected, correct, tag) {
    const options = document.querySelectorAll('.mcq-option');
    options.forEach(o => { o.classList.remove('selected', 'correct', 'wrong'); o.onclick = null; });

    if (selected === correct) {
        el.classList.add('correct');
    } else {
        el.classList.add('wrong');
        options[correct]?.classList.add('correct');
    }

    const explEl = document.getElementById('mcqExplanation');
    explEl.textContent = document.querySelector('.mcq-card')?._drill?.explanation || 'Review the concept and try again.';
    explEl.style.display = 'block';
    document.getElementById('mcqContinueBtn').style.display = 'inline-flex';

    // Notify server
    fetch('/mcq/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ selected_index: selected, correct_index: correct, concept_tag: tag })
    }).catch(() => {});
}

// ── Hints ─────────────────────────────────────────────────
async function requestHint() {
    if (hintsUsed >= 3) { showToast('All 3 hints used!', 'info'); return; }
    const exerciseId = document.querySelector('.exercise-page')?.dataset.exerciseId;
    if (!exerciseId) return;

    const hintBtn = document.getElementById('hintBtn');
    const code = editor ? editor.getValue() : '';
    hintBtn.disabled = true;
    hintBtn.innerHTML = '<span class="spinner"></span> Thinking...';

    try {
        const resp = await fetch('/hint', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ exercise_id: parseInt(exerciseId), code: code, hint_level: hintsUsed + 1 })
        });
        const result = await resp.json();
        hintsUsed++;
        updateHintCounter();

        const display = document.getElementById('hintDisplay');
        display.innerHTML = `
            <div><strong>Hint ${hintsUsed}/3:</strong> ${escapeHtml(result.hint || '')}</div>
            ${result.encouragement ? `<div class="hint-encouragement">${escapeHtml(result.encouragement)}</div>` : ''}
        `;
        display.style.display = 'block';
    } catch (err) {
        showToast('Failed to get hint.', 'error');
    } finally {
        hintBtn.disabled = false;
        hintBtn.innerHTML = `💡 Hint <span class="hint-counter" id="hintCounter">(${hintsUsed}/3)</span>`;
    }
}

function updateHintCounter() {
    const counter = document.getElementById('hintCounter');
    if (counter) counter.textContent = `(${hintsUsed}/3)`;
}

// ── Generate Exercise ─────────────────────────────────────
async function generateExercise(category) {
    const status = document.getElementById('generateStatus');
    const btn = document.getElementById(`generate${category.charAt(0).toUpperCase() + category.slice(1)}Btn`);
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Generating...'; }
    status.style.display = 'block';
    status.textContent = 'Generating with Gemini AI... This may take 10-20 seconds.';

    try {
        const resp = await fetch('/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category })
        });
        const result = await resp.json();
        if (result.error) {
            status.textContent = `❌ Error: ${result.error}`;
        } else if (result.id) {
            status.innerHTML = `✅ Created! <a href="/exercise/${result.id}" class="btn btn-sm btn-primary">Open Exercise →</a>`;
        }
    } catch (err) {
        status.textContent = '❌ Failed to generate. Check Gemini API key.';
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = `✨ Generate ${category.charAt(0).toUpperCase() + category.slice(1)}`; }
    }
}

// ── Toast ─────────────────────────────────────────────────
function showToast(message, type = 'info') {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity 0.3s'; setTimeout(() => toast.remove(), 300); }, 3000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
