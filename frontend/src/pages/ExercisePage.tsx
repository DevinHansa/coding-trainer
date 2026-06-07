import { useEffect, useRef, useState, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { toast } from 'sonner';
import { useAuth } from '@/AuthContext';

/* ─── Types ─────────────────────────────────────────────────── */
interface Exercise {
  id: number;
  title: string;
  description: string;
  category: string;
  difficulty: number;
  topic: string;
  tags: string[];
  hints: string[];
  sample_data?: string;
  expected_output?: string;
  solution?: string;
  starter_code?: string;
}

interface TestResult {
  passed: boolean;
  error?: string;
  output?: string;
  execution_time?: number;
  test_results?: Array<{
    passed: boolean;
    expected?: string;
    actual?: string;
    description?: string;
  }>;
}

interface FeedbackResult {
  score: number;
  works_correctly: boolean;
  feedback: string;
  what_worked?: string;
  efficiency_notes?: string;
  issues?: Array<{ description: string; your_code?: string; better_approach?: string }>;
  solution?: string;
  execution?: TestResult;
  weaknesses?: string[];
  failure_action?: any;
}

/* ─── Helpers ────────────────────────────────────────────────── */
function escapeHtml(text: string) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatTime(seconds: number) {
  const m = Math.floor(seconds / 60).toString().padStart(2, '0');
  const s = (seconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

/* ─── Component ─────────────────────────────────────────────── */
interface NextExercise {
  id: number | null;
  title: string;
  category: string;
  difficulty: number;
  message?: string;
}

export default function ExercisePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { token } = useAuth();

  const [exercise, setExercise] = useState<Exercise | null>(null);
  const [attempts, setAttempts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const [code, setCode] = useState('');
  const [running, setRunning] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [feedback, setFeedback] = useState<FeedbackResult | null>(null);
  const [nextExercise, setNextExercise] = useState<NextExercise | null>(null);

  const [hintLevel, setHintLevel] = useState(0);
  const [currentHint, setCurrentHint] = useState<string | null>(null);
  const [hintLoading, setHintLoading] = useState(false);

  const [timer, setTimer] = useState(0);
  const timerRef = useRef<number | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  /* ── Fetch exercise ── */
  useEffect(() => {
    if (!id) return;
    setLoading(true);
    fetch(`/api/exercises/${id}`, {
      headers: {
        'x-auth-token': token || '',
      },
    })
      .then(r => r.json())
      .then(data => {
        setExercise(data.exercise);
        setAttempts(data.attempts || []);
        const saved = localStorage.getItem(`code_${id}`);
        setCode(saved ?? data.exercise.starter_code ?? '');
        setLoading(false);
      })
      .catch(console.error);
  }, [id, token]);

  /* ── Timer ── */
  useEffect(() => {
    timerRef.current = window.setInterval(() => setTimer(t => t + 1), 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, []);

  /* ── Auto-save code ── */
  useEffect(() => {
    if (id && code) localStorage.setItem(`code_${id}`, code);
  }, [code, id]);

  /* ── Tab key support in textarea ── */
  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const el = e.currentTarget;
      const start = el.selectionStart;
      const end = el.selectionEnd;
      const newCode = code.substring(0, start) + '    ' + code.substring(end);
      setCode(newCode);
      setTimeout(() => {
        el.selectionStart = el.selectionEnd = start + 4;
      }, 0);
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSubmit();
    }
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'T') {
      e.preventDefault();
      handleRunTests();
    }
  }, [code]);

  /* ── Run Tests ── */
  async function handleRunTests() {
    if (!exercise || running) return;
    setRunning(true);
    setTestResult(null);
    setFeedback(null);
    try {
      const res = await fetch('/run-tests', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'x-auth-token': token || '',
        },
        body: JSON.stringify({ exercise_id: exercise.id, code }),
      });
      const data: TestResult = await res.json();
      setTestResult(data);
      if (data.passed) toast.success('All tests passed! ✅');
      else toast.error('Some tests failed. Check the results.');
    } catch (err) {
      toast.error('Failed to run tests. Is Flask running?');
    } finally {
      setRunning(false);
    }
  }

  /* ── Submit ── */
  async function handleSubmit() {
    if (!exercise || submitting) return;
    if (timerRef.current) clearInterval(timerRef.current);
    setSubmitting(true);
    setFeedback(null);
    setNextExercise(null);
    try {
      const res = await fetch('/submit', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'x-auth-token': token || '',
        },
        body: JSON.stringify({
          exercise_id: exercise.id,
          code,
          time_spent: timer,
          hints_used: hintLevel,
          logical_steps: '',
        }),
      });
      const data: FeedbackResult = await res.json();
      setFeedback(data);
      if (data.score >= 70) {
        toast.success(`Score: ${data.score}/100 🎉`);
      } else {
        toast.warning(`Score: ${data.score}/100. Review the feedback.`);
      }
      // Fetch the next recommended exercise in the background
      fetchNextExercise(exercise.id, exercise.category);
    } catch (err) {
      toast.error('Submission failed. Is Flask running?');
    } finally {
      setSubmitting(false);
    }
  }

  /* ── Fetch next exercise ── */
  async function fetchNextExercise(currentId: number, category: string) {
    try {
      const res = await fetch(`/api/next-exercise?current_id=${currentId}&category=${category}`, {
        headers: {
          'x-auth-token': token || '',
        },
      });
      const data: NextExercise = await res.json();
      setNextExercise(data);
    } catch {
      // silently ignore — next button just won't show
    }
  }

  /* ── Hint ── */
  async function handleHint() {
    if (!exercise || hintLevel >= 3 || hintLoading) return;
    const nextLevel = hintLevel + 1;
    setHintLoading(true);
    try {
      const res = await fetch('/hint', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'x-auth-token': token || '',
        },
        body: JSON.stringify({ exercise_id: exercise.id, code, hint_level: nextLevel }),
      });
      const data = await res.json();
      setHintLevel(nextLevel);
      setCurrentHint(data.hint);
    } catch (err) {
      toast.error('Failed to get hint.');
    } finally {
      setHintLoading(false);
    }
  }

  /* ── Render ── */
  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-16 w-full" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-[600px] w-full" />
          <Skeleton className="h-[600px] w-full" />
        </div>
      </div>
    );
  }

  if (!exercise) {
    return (
      <div className="text-center py-20">
        <div className="text-5xl mb-4">🔍</div>
        <h1 className="text-2xl font-bold mb-2">Exercise Not Found</h1>
        <Button asChild><Link to="/exercises">Back to Exercises</Link></Button>
      </div>
    );
  }


  return (
    <div className="space-y-4 fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <Badge variant="outline" className={
              exercise.category === 'sql' ? 'border-blue-500 text-blue-500' :
              exercise.category === 'python' ? 'border-purple-500 text-purple-500' :
              'border-amber-500 text-amber-500'
            }>
              {exercise.category.toUpperCase()}
            </Badge>
            <Badge variant="secondary">Level {exercise.difficulty}</Badge>
            {exercise.tags?.slice(0, 2).map(tag => (
              <Badge key={tag} variant="outline" className="text-xs">
                {tag.replace(`${exercise.category}:`, '')}
              </Badge>
            ))}
          </div>
          <h1 className="text-2xl font-bold">{exercise.title}</h1>
        </div>
        <div className="flex items-center gap-3 text-muted-foreground font-mono bg-card border rounded-lg px-4 py-2">
          <span>⏱</span>
          <span className="text-lg font-medium">{formatTime(timer)}</span>
        </div>
      </div>

      {/* Split Pane */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Problem */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">📋 Problem</CardTitle>
            </CardHeader>
            <CardContent>
              <div
                className="prose prose-sm dark:prose-invert max-w-none text-foreground leading-relaxed"
                dangerouslySetInnerHTML={{
                  __html: exercise.description
                    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="bg-muted rounded p-3 text-sm overflow-x-auto"><code>$2</code></pre>')
                    .replace(/`([^`]+)`/g, '<code class="bg-muted px-1 rounded text-sm">$1</code>')
                    .replace(/\n/g, '<br/>')
                }}
              />
              {exercise.sample_data && (
                <div className="mt-4">
                  <p className="text-sm font-semibold text-muted-foreground mb-2">Sample Data:</p>
                  <pre className="bg-muted p-3 rounded text-sm overflow-x-auto">{exercise.sample_data}</pre>
                </div>
              )}
              {exercise.expected_output && (
                <div className="mt-4">
                  <p className="text-sm font-semibold text-muted-foreground mb-2">Expected Output:</p>
                  <pre className="bg-muted p-3 rounded text-sm overflow-x-auto">{exercise.expected_output}</pre>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Hints */}
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between mb-3">
                <span className="font-semibold flex items-center gap-2">💡 Hints ({hintLevel}/3)</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleHint}
                  disabled={hintLevel >= 3 || hintLoading}
                >
                  {hintLoading ? 'Loading...' : hintLevel >= 3 ? 'All hints used' : 'Get Hint'}
                </Button>
              </div>
              {currentHint && (
                <div className="bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded-lg p-4 text-sm text-amber-900 dark:text-amber-100">
                  {currentHint}
                </div>
              )}
              {exercise.hints?.slice(0, hintLevel).map((hint, i) => (
                <div key={i} className="mt-2 bg-muted rounded-lg p-3 text-sm">
                  <span className="font-medium">Hint {i + 1}:</span> {hint}
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Test Results */}
          {testResult && (
            <Card className={testResult.passed ? 'border-emerald-500' : 'border-destructive'}>
              <CardHeader>
                <CardTitle className={`text-lg ${testResult.passed ? 'text-emerald-500' : 'text-destructive'}`}>
                  {testResult.passed ? '✅ Tests Passed!' : '❌ Tests Failed'}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {testResult.error && (
                  <pre className="bg-destructive/10 text-destructive text-sm p-3 rounded overflow-x-auto mb-4">
                    {testResult.error}
                  </pre>
                )}
                {testResult.output && (
                  <div className="mb-4">
                    <p className="text-sm font-medium text-muted-foreground mb-1">Output:</p>
                    <pre className="bg-muted text-sm p-3 rounded overflow-x-auto">{testResult.output}</pre>
                  </div>
                )}
                {testResult.test_results?.map((t, i) => (
                  <div key={i} className={`flex items-start gap-2 py-2 border-b last:border-0 text-sm ${t.passed ? 'text-emerald-600' : 'text-destructive'}`}>
                    <span className="mt-0.5 flex-shrink-0">{t.passed ? '✓' : '✗'}</span>
                    <div>
                      {t.description && <p className="font-medium">{t.description}</p>}
                      {!t.passed && t.expected && <p className="text-muted-foreground">Expected: {t.expected}</p>}
                      {!t.passed && t.actual && <p className="text-muted-foreground">Got: {t.actual}</p>}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Feedback */}
          {feedback && (
            <Card className={feedback.score >= 100 ? 'border-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/10' : 'border-amber-500'}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">
                    {feedback.score >= 100 ? '🎉 Result' : '🤖 AI Feedback'}
                  </CardTitle>
                  <span className={`text-3xl font-bold ${
                    feedback.score >= 100 ? 'text-emerald-500' :
                    feedback.score >= 60 ? 'text-amber-500' : 'text-destructive'
                  }`}>
                    {feedback.score}/100
                  </span>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Pass state — clean and celebratory */}
                {feedback.score >= 100 && (
                  <div className="text-center py-4">
                    <div className="text-5xl mb-3">✅</div>
                    <p className="text-emerald-700 dark:text-emerald-300 font-semibold text-lg">
                      All tests passed!
                    </p>
                    <p className="text-muted-foreground text-sm mt-1">
                      {feedback.what_worked}
                    </p>
                  </div>
                )}

                {/* Fail state — show AI coaching */}
                {feedback.score < 100 && (
                  <>
                    {feedback.feedback && (
                      <p className="text-sm leading-relaxed">{feedback.feedback}</p>
                    )}
                    {(feedback.what_worked || feedback.efficiency_notes || (feedback.issues && feedback.issues.length > 0)) && (
                      <Separator />
                    )}
                    {feedback.what_worked && (
                      <div>
                        <p className="text-sm font-semibold text-emerald-600 mb-1">✅ What Worked</p>
                        <p className="text-sm text-muted-foreground">{feedback.what_worked}</p>
                      </div>
                    )}
                    {feedback.efficiency_notes && (
                      <div>
                        <p className="text-sm font-semibold text-blue-500 mb-1">⚡ Efficiency</p>
                        <p className="text-sm text-muted-foreground">{feedback.efficiency_notes}</p>
                      </div>
                    )}
                    {feedback.issues && feedback.issues.length > 0 && (
                      <div>
                        <p className="text-sm font-semibold text-destructive mb-2">🐛 Issues</p>
                        {feedback.issues.map((issue: any, i: number) => (
                          <div key={i} className="bg-destructive/5 border border-destructive/20 rounded p-3 text-sm mb-2">
                            <p className="font-medium">{issue.description || issue.issue}</p>
                            {(issue.better_approach || issue.what_it_should_be) && (
                              <p className="text-muted-foreground mt-1">
                                Suggestion: {issue.better_approach || issue.what_it_should_be}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    {feedback.solution && (
                      <div>
                        <p className="text-sm font-semibold text-muted-foreground mb-2">📖 Reference Solution</p>
                        <pre className="bg-muted p-3 rounded text-sm overflow-x-auto">{escapeHtml(feedback.solution)}</pre>
                      </div>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right: Editor */}
        <div className="space-y-4 lg:sticky lg:top-24 lg:self-start">
          <Card className="overflow-hidden">
            <CardHeader className="py-3 px-4 border-b bg-muted/30">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium">
                  📝 Code Editor
                  <span className="text-xs text-muted-foreground ml-2">
                    ({exercise.category === 'sql' ? 'SQL' : 'Python'})
                  </span>
                </CardTitle>
                <div className="flex gap-1">
                  <span className="w-3 h-3 rounded-full bg-destructive/60" />
                  <span className="w-3 h-3 rounded-full bg-amber-400/60" />
                  <span className="w-3 h-3 rounded-full bg-emerald-400/60" />
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <textarea
                ref={textareaRef}
                value={code}
                onChange={e => setCode(e.target.value)}
                onKeyDown={handleKeyDown}
                className="w-full h-[400px] p-4 font-mono text-sm bg-zinc-950 text-zinc-100 resize-none border-0 focus:outline-none focus:ring-0 leading-relaxed"
                placeholder={`Write your ${exercise.category} code here...\n\nCtrl+Enter → Submit\nCtrl+Shift+T → Run Tests\nTab → 4 spaces`}
                spellCheck={false}
                autoComplete="off"
                autoCapitalize="off"
              />
            </CardContent>
          </Card>

          {/* Action Buttons */}
          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={handleRunTests}
              disabled={running || submitting || !code.trim()}
              className="flex-1"
            >
              {running ? '⏳ Running...' : '▶ Run Tests'}
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={submitting || running || !code.trim()}
              className="flex-1 font-semibold"
            >
              {submitting ? '⏳ Evaluating...' : '🚀 Submit'}
            </Button>
          </div>

          {/* Next Question — appears after submission */}
          {feedback && (
            <div className="flex flex-col gap-2">
              {nextExercise?.id ? (
                <Button
                  onClick={() => navigate(`/exercise/${nextExercise.id}`)}
                  className="w-full font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-md"
                  size="lg"
                >
                  <span className="flex items-center justify-center gap-2">
                    Next Question →
                    <span className="text-sm font-normal opacity-80 truncate max-w-[180px]">{nextExercise.title}</span>
                  </span>
                </Button>
              ) : nextExercise?.message ? (
                <div className="text-center py-3 px-4 bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800 rounded-lg">
                  <p className="text-emerald-700 dark:text-emerald-300 font-semibold text-sm">🏆 {nextExercise.message}</p>
                  <Button variant="outline" className="mt-2 w-full" asChild>
                    <Link to="/exercises">Browse All Exercises</Link>
                  </Button>
                </div>
              ) : null}
            </div>
          )}

          {/* Previous Attempts */}
          {attempts.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">Previous Attempts</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {attempts.map((attempt, i) => (
                  <div key={i} className="flex justify-between items-center py-2 border-b last:border-0 text-sm">
                    <span className={attempt.score >= 70 ? 'text-emerald-500' : 'text-destructive'}>
                      {attempt.score >= 70 ? '✓' : '✗'} Score: {attempt.score}
                    </span>
                    <span className="text-muted-foreground text-xs">
                      {new Date(attempt.timestamp).toLocaleDateString()}
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
