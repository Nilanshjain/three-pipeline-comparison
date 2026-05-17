import React, { useState, useEffect } from 'react';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Send, Loader2, AlertCircle, Cpu, Database, Network, Trophy, Zap, DollarSign, CheckCircle2, FileQuestion, Info } from 'lucide-react';

// Backend port 8765 (avoids conflicts with the user's other local services on 8000/8001).
// Configurable API base. Locally defaults to the dev backend; on deployed
// static sites (e.g. Vercel) set REACT_APP_API_BASE_URL to your backend, or
// leave unset and the dashboard will run in read-only "static mode" using
// the bundled data files under /data/.
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8765/api/v1';
// Pre-bundled fallbacks served as static assets from the React public/ dir.
const STATIC_EVAL_QUESTIONS_URL = '/data/eval-questions.json';
const STATIC_SAVED_RESULTS_URL = '/data/saved-results.json';

const PIPELINE_META = {
  llm_only: {
    label: 'LLM-Only',
    description: 'Baseline. No retrieval.',
    icon: Cpu,
    accent: 'border-metal-600',
  },
  basic_rag: {
    label: 'Basic RAG',
    description: 'Vector embeddings + LLM.',
    icon: Database,
    accent: 'border-blue-700',
  },
  graph_rag: {
    label: 'GraphRAG',
    description: 'TigerGraph multi-hop reasoning.',
    icon: Network,
    accent: 'border-rust-600',
  },
};

const ORDER = ['llm_only', 'basic_rag', 'graph_rag'];

function formatCost(usd) {
  if (usd == null) return '—';
  if (usd === 0) return '$0';
  if (usd < 0.0001) return `$${usd.toExponential(2)}`;
  return `$${usd.toFixed(4)}`;
}

function formatLatency(ms) {
  if (ms == null) return '—';
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

// Category badge styling. The eval set deliberately includes three difficulty
// classes — single_fact (LLM-Only can sometimes win), multi_hop (vector search
// often misses), synthesis (where GraphRAG should shine).
const CATEGORY_STYLES = {
  single_fact: 'bg-blue-900/40 text-blue-300 border-blue-700',
  multi_hop:   'bg-amber-900/40 text-amber-300 border-amber-700',
  synthesis:   'bg-purple-900/40 text-purple-300 border-purple-700',
};

function CategoryBadge({ category }) {
  const cls = CATEGORY_STYLES[category] || 'bg-metal-800 text-metal-300 border-metal-700';
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono uppercase ${cls}`}>
      {category}
    </span>
  );
}

function EvalQuestionsPanel({ questions, onPick, disabled, activeId }) {
  const [open, setOpen] = useState(true);
  if (!questions || questions.length === 0) return null;

  return (
    <Card className="border-metal-600 shadow-2xl">
      <CardHeader className="pb-3">
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex items-center justify-between w-full text-left"
        >
          <div className="flex items-center gap-2">
            <FileQuestion className="w-4 h-4 text-rust-500" />
            <CardTitle className="text-base">Curated eval set</CardTitle>
            <span className="text-xs text-metal-400">({questions.length} questions)</span>
          </div>
          <span className="text-metal-500 text-xs">{open ? 'hide' : 'show'}</span>
        </button>
        {open && (
          <CardDescription className="text-xs">
            Click any question to run the benchmark. Reference answer appears above the
            pipeline cards so you can verify which pipeline got the answer right.
          </CardDescription>
        )}
      </CardHeader>
      {open && (
        <CardContent className="pt-0">
          <div className="space-y-1.5">
            {questions.map((q) => {
              const active = activeId === q.id;
              return (
                <button
                  key={q.id}
                  onClick={() => onPick(q)}
                  disabled={disabled}
                  className={`w-full text-left p-2 rounded-md border text-sm flex items-start gap-2 transition-colors ${
                    active
                      ? 'border-rust-600 bg-rust-900/30'
                      : 'border-metal-700 bg-steel-900/40 hover:bg-steel-800/60 hover:border-metal-500'
                  } disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  <span className="text-metal-500 font-mono text-xs mt-0.5 w-5 flex-shrink-0">
                    #{q.id}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <CategoryBadge category={q.category} />
                    </div>
                    <div className="text-metal-200 break-words">{q.question}</div>
                  </div>
                </button>
              );
            })}
          </div>
        </CardContent>
      )}
    </Card>
  );
}

function ReferenceCard({ question }) {
  if (!question) return null;
  return (
    <Card className="border-green-700/60 bg-green-900/10 shadow-2xl">
      <CardContent className="py-4">
        <div className="flex items-start gap-3">
          <CheckCircle2 className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-green-300 font-semibold text-sm">Reference answer</span>
              <CategoryBadge category={question.category} />
              <span className="text-[10px] text-metal-500 font-mono">Q#{question.id}</span>
            </div>
            <div className="text-metal-100 text-sm leading-relaxed break-words">
              {question.reference}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function SavedResultsPanel({ entries, open, onToggle }) {
  if (!entries || entries.length === 0) return null;
  return (
    <Card className="border-amber-700/50 shadow-2xl">
      <CardHeader className="pb-3">
        <button
          type="button"
          onClick={onToggle}
          className="w-full flex items-center justify-between gap-2 text-left"
        >
          <div>
            <CardTitle className="flex items-center gap-2 text-amber-300">
              <Trophy className="w-5 h-5" />
              Saved benchmark runs — full 14-question aggregates
            </CardTitle>
            <CardDescription className="text-xs mt-1">
              Reproducible from the JSON files in <span className="font-mono">backend/tests/</span>. Click to {open ? 'hide' : 'show'}.
            </CardDescription>
          </div>
          <span className="text-xs text-amber-300 font-mono">{open ? '▾' : '▸'}</span>
        </button>
      </CardHeader>
      {open && (
        <CardContent>
          <div className="space-y-4">
            {entries.map((e) => (
              <div key={e.id} className="border border-metal-700 rounded-md overflow-hidden">
                <div className="bg-steel-800/60 px-4 py-3 border-b border-metal-700">
                  <div className="flex items-baseline justify-between flex-wrap gap-2">
                    <div>
                      <div className="text-metal-100 font-semibold text-sm">{e.label}</div>
                      <div className="text-metal-300 text-xs mt-0.5">{e.subtitle}</div>
                    </div>
                    <span className="text-[10px] text-metal-500 font-mono">{e.file}</span>
                  </div>
                  {e.rubric && (
                    <div className="text-[11px] text-emerald-300 mt-1.5">{e.rubric}</div>
                  )}
                  <div className="text-[11px] text-metal-500 mt-1 font-mono break-all">{e.config}</div>
                </div>
                {e.error ? (
                  <div className="px-4 py-3 text-xs text-red-400">Load error: {e.error}</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead className="bg-steel-900/80 text-metal-400">
                        <tr>
                          <th className="text-left px-3 py-2 font-semibold">Pipeline</th>
                          <th className="text-right px-3 py-2 font-semibold">Judge %</th>
                          <th className="text-right px-3 py-2 font-semibold">F1_raw</th>
                          <th className="text-right px-3 py-2 font-semibold">F1_resc</th>
                          <th className="text-right px-3 py-2 font-semibold">Avg tokens</th>
                          <th className="text-right px-3 py-2 font-semibold">n</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(e.summary || {}).map(([name, m]) => {
                          const isGraph = name === 'graph_rag';
                          const f1r = m.bertscore_f1_raw_mean;
                          const f1c = m.bertscore_f1_rescaled_mean;
                          const judgePct = m.judge_pass_rate != null ? (m.judge_pass_rate * 100) : null;
                          const judgeMet = isGraph && judgePct != null && judgePct >= 90;
                          return (
                            <tr key={name} className={`border-t border-metal-700 ${isGraph ? 'bg-amber-950/10' : ''}`}>
                              <td className="px-3 py-2">
                                <span className={isGraph ? 'text-amber-200 font-semibold' : 'text-metal-200'}>
                                  {PIPELINE_META[name]?.label || name}
                                </span>
                              </td>
                              <td className="px-3 py-2 text-right font-mono">
                                <span className={judgeMet ? 'text-emerald-300 font-semibold' : 'text-metal-200'}>
                                  {judgePct != null ? `${judgePct.toFixed(1)}%` : '—'}
                                </span>
                                {judgeMet && <span className="ml-1">✅</span>}
                              </td>
                              <td className="px-3 py-2 text-right font-mono">
                                <span className={isGraph && f1r != null && f1r >= 0.88 ? 'text-emerald-300 font-semibold' : 'text-metal-200'}>
                                  {f1r != null ? f1r.toFixed(3) : '—'}
                                </span>
                                {isGraph && f1r != null && f1r >= 0.88 && <span className="ml-1">✅</span>}
                              </td>
                              <td className="px-3 py-2 text-right font-mono text-metal-200">
                                {f1c != null ? f1c.toFixed(3) : '—'}
                              </td>
                              <td className="px-3 py-2 text-right font-mono text-metal-200">
                                {m.mean_total_tokens != null ? Math.round(m.mean_total_tokens).toLocaleString() : '—'}
                              </td>
                              <td className="px-3 py-2 text-right font-mono text-metal-400">
                                {m.judge_n != null ? m.judge_n : '—'}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ))}
            <div className="text-[11px] text-metal-500">
              ✅ = bonus criterion crossed. Maximum bonus (both criteria same run) requires judge ≥ 90% AND (F1_raw ≥ 0.88 OR F1_resc ≥ 0.55).
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  );
}

function PipelineCard({ result }) {
  const meta = PIPELINE_META[result.pipeline] || {
    label: result.pipeline,
    description: '',
    icon: Cpu,
    accent: 'border-metal-600',
  };
  const Icon = meta.icon;
  const errored = !!result.error;

  const calls = result.internal_llm_calls || 1;

  return (
    <Card className={`${meta.accent} shadow-2xl flex flex-col h-full`}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between gap-2 text-lg">
          <div className="flex items-center gap-2">
            <Icon className="w-5 h-5 text-rust-500" />
            {meta.label}
          </div>
          {/* LLM call count badge — for Pipeline 3 this shows whether
              we're in the cheap (combine=true, 1 call) or expensive
              (combine=false, 10+ calls) regime. Critical context judges
              need to interpret the token numbers fairly. */}
          {!errored && (
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded border font-mono ${
                calls === 1
                  ? 'bg-steel-800 text-metal-300 border-metal-700'
                  : 'bg-amber-900/40 text-amber-300 border-amber-700'
              }`}
              title="Total LLM calls this query consumed (synthesis + any internal scoring)"
            >
              {calls} LLM call{calls !== 1 ? 's' : ''}
            </span>
          )}
        </CardTitle>
        <CardDescription className="text-xs">{meta.description}</CardDescription>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col space-y-3">
        {/* Metrics row */}
        <div className="grid grid-cols-3 gap-2 text-center text-xs">
          <div className="bg-steel-800/60 border border-metal-700 rounded-md p-2">
            <div className="text-metal-400">Tokens</div>
            <div className="text-rust-400 font-mono font-semibold">
              {errored ? '—' : result.total_tokens.toLocaleString()}
            </div>
            {!errored && (
              <div className="text-[10px] text-metal-500 mt-0.5">
                {result.prompt_tokens}p + {result.completion_tokens}c
              </div>
            )}
          </div>
          <div className="bg-steel-800/60 border border-metal-700 rounded-md p-2">
            <div className="text-metal-400">Latency</div>
            <div className="text-rust-400 font-mono font-semibold">
              {errored ? '—' : formatLatency(result.latency_ms)}
            </div>
          </div>
          <div className="bg-steel-800/60 border border-metal-700 rounded-md p-2">
            <div className="text-metal-400">Cost</div>
            <div className="text-rust-400 font-mono font-semibold">
              {errored ? '—' : formatCost(result.cost_usd)}
            </div>
          </div>
        </div>

        {/* Answer */}
        <div className="flex-1 min-h-[200px] bg-steel-900/60 border border-metal-700 rounded-md p-3 overflow-y-auto max-h-[400px]">
          {errored ? (
            <div className="flex items-start gap-2 text-red-400 text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold">Pipeline error</div>
                <div className="text-xs mt-1 break-words">{result.error}</div>
              </div>
            </div>
          ) : (
            <div className="whitespace-pre-wrap text-sm text-metal-100 break-words">
              {result.answer || <span className="text-metal-500 italic">No answer returned</span>}
            </div>
          )}
        </div>

        {/* Retrieved chunks */}
        {!errored && result.retrieved_chunks && result.retrieved_chunks.length > 0 && (
          <details className="text-xs">
            <summary className="cursor-pointer text-metal-400 hover:text-metal-200">
              Retrieved context ({result.retrieved_chunks.length})
            </summary>
            <div className="mt-2 space-y-2 max-h-48 overflow-y-auto">
              {result.retrieved_chunks.map((c, i) => (
                <div key={i} className="bg-steel-900/80 border border-metal-700 rounded p-2">
                  <div className="flex justify-between text-[10px] text-metal-500 mb-1">
                    <span>{c.source}</span>
                    {c.score != null && <span>sim {c.score.toFixed(3)}</span>}
                  </div>
                  <div className="text-metal-300 break-words">{c.text.slice(0, 240)}{c.text.length > 240 ? '…' : ''}</div>
                </div>
              ))}
            </div>
          </details>
        )}

        {!errored && result.model && (
          <div className="text-[10px] text-metal-500 text-right">model: {result.model}</div>
        )}
      </CardContent>
    </Card>
  );
}

function SummaryStrip({ summary }) {
  if (!summary) return null;

  const reductionEntries = Object.entries(summary)
    .filter(([k]) => k.endsWith('_token_reduction_vs_basic_pct'))
    .map(([k, v]) => ({
      pipeline: k.replace('_token_reduction_vs_basic_pct', ''),
      pct: v,
    }));

  return (
    <Card className="border-metal-600 shadow-2xl">
      <CardContent className="py-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div className="flex items-center gap-3">
            <Trophy className="w-5 h-5 text-rust-500" />
            <div>
              <div className="text-metal-400 text-xs">Token reduction vs Basic RAG</div>
              <div className="font-mono">
                {reductionEntries.length === 0 ? (
                  <span className="text-metal-500">—</span>
                ) : (
                  reductionEntries.map(({ pipeline, pct }) => (
                    <div key={pipeline} className="text-metal-100">
                      {PIPELINE_META[pipeline]?.label || pipeline}:{' '}
                      <span className={pct > 0 ? 'text-green-400' : 'text-red-400'}>
                        {pct > 0 ? '+' : ''}{pct}%
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Zap className="w-5 h-5 text-rust-500" />
            <div>
              <div className="text-metal-400 text-xs">Fastest</div>
              <div className="text-metal-100 font-mono">
                {summary.fastest_pipeline ? PIPELINE_META[summary.fastest_pipeline]?.label || summary.fastest_pipeline : '—'}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <DollarSign className="w-5 h-5 text-rust-500" />
            <div>
              <div className="text-metal-400 text-xs">Cheapest</div>
              <div className="text-metal-100 font-mono">
                {summary.cheapest_pipeline ? PIPELINE_META[summary.cheapest_pipeline]?.label || summary.cheapest_pipeline : '—'}
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function Compare() {
  const [query, setQuery] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState(null);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState('');
  const [evalQuestions, setEvalQuestions] = useState([]);
  // The currently-selected eval question. We track this so the dashboard
  // can show the reference answer alongside the pipeline outputs after a
  // run — letting judges verify which pipeline got the answer right.
  const [activeEvalQuestion, setActiveEvalQuestion] = useState(null);
  // Adaptive fallback toggle — when on, Pipeline 3 retries with 2-hop graph
  // traversal hybrid retrieval if the community-summary primary returns a
  // refusal phrase. Triggers the C26 max-bonus path. Visible LLM-call-count
  // jump from 1 to 3+ confirms the fallback fired.
  const [adaptiveFallback, setAdaptiveFallback] = useState(false);
  // Saved benchmark runs — aggregate 14-question scores from saved JSONs.
  // Lets judges see our two hackathon wins (C11 headline, C26 max bonus)
  // without running 14 live queries (avoids judge variance during demo).
  const [savedResults, setSavedResults] = useState([]);
  const [showSavedResults, setShowSavedResults] = useState(false);
  // staticMode = true when the backend isn't reachable. We then serve the
  // bundled data files for eval questions + saved results, and disable the
  // live "Run benchmark" button with a notice.
  const [staticMode, setStaticMode] = useState(false);

  useEffect(() => {
    // Try the live backend first; fall back to the static JSON shipped with the build.
    fetch(`${API_BASE_URL}/benchmark/saved-results`, { signal: AbortSignal.timeout(2500) })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setSavedResults)
      .catch(() => {
        // Backend not reachable — switch to static mode and load the
        // bundled aggregates from public/data/.
        setStaticMode(true);
        fetch(STATIC_SAVED_RESULTS_URL)
          .then((r) => (r.ok ? r.json() : []))
          .then(setSavedResults)
          .catch(() => setSavedResults([]));
      });
  }, []);

  useEffect(() => {
    // Fetch curated eval set on mount. If the backend is unreachable, fall
    // back to the bundled copy under /data/ so the deployed static site can
    // still render the curated questions panel.
    fetch(`${API_BASE_URL}/benchmark/eval-questions`, { signal: AbortSignal.timeout(2500) })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setEvalQuestions)
      .catch(() => {
        fetch(STATIC_EVAL_QUESTIONS_URL)
          .then((r) => (r.ok ? r.json() : []))
          .then(setEvalQuestions)
          .catch(() => setEvalQuestions([]));
      });
  }, []);

  const pickEvalQuestion = (q) => {
    if (isRunning) return;
    setQuery(q.question);
    setActiveEvalQuestion(q);
    // In static mode there's no backend to query — just surface the
    // reference answer and let the user browse the saved aggregates.
    if (staticMode) return;
    setTimeout(() => runBenchmarkWith(q.question), 0);
  };

  const runBenchmarkWith = async (q) => {
    if (!q.trim() || isRunning) return;
    setIsRunning(true);
    setError('');
    setResults(null);
    setSummary(null);

    try {
      const body = { query: q };
      if (adaptiveFallback) {
        body.graphrag_config = { adaptive_fallback: true };
      }
      const response = await fetch(`${API_BASE_URL}/benchmark/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || `Request failed (${response.status})`);
      }

      const data = await response.json();
      const byName = Object.fromEntries(data.pipelines.map((p) => [p.pipeline, p]));
      const ordered = ORDER.map((n) => byName[n]).filter(Boolean);
      const extras = data.pipelines.filter((p) => !ORDER.includes(p.pipeline));
      setResults([...ordered, ...extras]);
      setSummary(data.summary);
    } catch (e) {
      setError(e.message);
    } finally {
      setIsRunning(false);
    }
  };

  const runBenchmark = () => {
    // Manual textarea submit — clear the eval-question link since this
    // is ad-hoc input, not an eval-set click.
    setActiveEvalQuestion(null);
    return runBenchmarkWith(query);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      runBenchmark();
    }
  };

  return (
    <div className="space-y-4">
      {staticMode && (
        <Card className="border-amber-700/50 bg-amber-950/15 shadow-2xl">
          <CardContent className="py-3">
            <div className="flex items-start gap-3 text-sm">
              <Info className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
              <div className="text-amber-100">
                <strong>Read-only mode.</strong> No live backend connected. Saved benchmark
                results below are the same numbers from the full eval runs in the repo.
                For live querying, follow the setup in the{' '}
                <a href="https://github.com/Nilanshjain/DevRAG#running-it" target="_blank" rel="noreferrer" className="text-amber-300 underline">
                  README
                </a>{' '}— spin up the local stack and the dashboard becomes interactive.
              </div>
            </div>
          </CardContent>
        </Card>
      )}
      <Card className="border-metal-600 shadow-2xl">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Run a query</CardTitle>
          <CardDescription className="text-xs">
            Same query → three pipelines, side by side.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-3">
            <Textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask anything (e.g. 'Which DeepMind researchers later joined OpenAI?')"
              disabled={isRunning}
              rows={2}
              className="flex-1"
            />
            <Button
              onClick={runBenchmark}
              disabled={!query.trim() || isRunning || staticMode}
              size="lg"
              className="h-auto px-6"
              title={staticMode ? 'Live querying requires the local backend — see README' : undefined}
            >
              {isRunning ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin mr-2" />
                  Running…
                </>
              ) : (
                <>
                  <Send className="w-5 h-5 mr-2" />
                  Run benchmark
                </>
              )}
            </Button>
          </div>
          {error && (
            <div className="mt-4 flex items-center gap-2 p-3 rounded-md text-sm bg-red-900/20 border border-red-700 text-red-400">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          )}
          {/* Adaptive fallback toggle — flips Pipeline 3 between cheap
              default and graph-traversal fallback. Visible LLM-call-count
              jump in the result card confirms the fallback fired. */}
          <div className="mt-3 flex items-center justify-between gap-3 text-sm border-t border-metal-700 pt-3">
            <div className="flex-1 min-w-0">
              <label htmlFor="adaptive-toggle" className="text-metal-200 cursor-pointer font-medium">
                Pipeline 3 mode:&nbsp;
                <span className={adaptiveFallback ? 'text-amber-300' : 'text-emerald-300'}>
                  {adaptiveFallback ? 'Adaptive (max-bonus path)' : 'Default (token-reduction path)'}
                </span>
              </label>
              <div className="text-xs text-metal-500 mt-0.5">
                {adaptiveFallback
                  ? 'On multi-hop questions, fires 2-hop graph traversal retry. ~3 LLM calls, ~2,500 tok. Targets bonus tier.'
                  : 'Single LLM call, community summary + 1 chunk. ~800 tok. Targets token reduction.'}
              </div>
            </div>
            <button
              id="adaptive-toggle"
              type="button"
              role="switch"
              aria-checked={adaptiveFallback}
              onClick={() => setAdaptiveFallback((v) => !v)}
              disabled={isRunning}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors flex-shrink-0 ${
                adaptiveFallback ? 'bg-amber-500' : 'bg-emerald-600'
              } ${isRunning ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  adaptiveFallback ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        </CardContent>
      </Card>

      <SavedResultsPanel
        entries={savedResults}
        open={showSavedResults}
        onToggle={() => setShowSavedResults((v) => !v)}
      />

      <EvalQuestionsPanel
        questions={evalQuestions}
        onPick={pickEvalQuestion}
        disabled={isRunning}
        activeId={activeEvalQuestion?.id}
      />

      {summary && <SummaryStrip summary={summary} />}

      {/* Reference answer only shows when a query came from the eval set —
          judges can fact-check each pipeline against the ground truth. */}
      {results && activeEvalQuestion && <ReferenceCard question={activeEvalQuestion} />}

      {results && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {results.map((r) => (
            <PipelineCard key={r.pipeline} result={r} />
          ))}
        </div>
      )}

      {!results && !isRunning && (
        <div className="text-center text-metal-500 text-sm py-12">
          Pick a curated question above or type your own to compare the three pipelines.
        </div>
      )}
    </div>
  );
}
