'use client';

import { useEffect, useRef, useState } from 'react';
import { Activity, CheckCircle2, Clock3, Play, Square, Zap } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_MANIMIND_API_BASE_URL || 'http://127.0.0.1:8000';
const PROJECT_ID = 'cauchy-backward-induction-real';

const STAGES = [
  { key: 'ingest', label: '素材导入' },
  { key: 'summarize', label: '内容摘要' },
  { key: 'plan', label: '计划生成' },
  { key: 'dispatch', label: '任务分发' },
  { key: 'review', label: '审核关卡' },
  { key: 'post_produce', label: '后期制作' },
  { key: 'package', label: '打包交付' },
];

type EventItem = {
  event_type: string;
  role_id?: string;
  stage?: string;
  timestamp?: string;
  [key: string]: any;
};

export default function ExecutionPage() {
  const [running, setRunning] = useState(false);
  const [currentStage, setCurrentStage] = useState('prestart');
  const [events, setEvents] = useState<EventItem[]>([]);
  const [tasks, setTasks] = useState<any[]>([]);
  const [error, setError] = useState('');
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const eventsEndRef = useRef<HTMLDivElement>(null);

  async function pollStatus() {
    try {
      const res = await fetch(`${API_BASE}/api/projects/${PROJECT_ID}/runtime`);
      if (res.ok) {
        const data = await res.json();
        setCurrentStage(data.state?.current_stage || 'prestart');
        setTasks(data.execution_tasks || []);
      }
      const evRes = await fetch(
        `${API_BASE}/api/projects/${PROJECT_ID}/events?limit=50`
      );
      if (evRes.ok) {
        const evData = await evRes.json();
        setEvents(evData.events || []);
      }
    } catch {}
  }

  useEffect(() => {
    pollStatus();
    intervalRef.current = setInterval(pollStatus, 3000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  useEffect(() => {
    eventsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events]);

  async function startExecution() {
    setRunning(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/api/projects/run-to-review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          manifest_path: `configs/${PROJECT_ID}.json`,
          session_id: `session-${Date.now()}`,
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || 'execution failed');
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setRunning(false);
      pollStatus();
    }
  }

  const completed = tasks.filter((t) => t.status === 'completed').length;
  const total = tasks.length || 1;
  const progress = Math.round((completed / total) * 100);

  const stageIdx = STAGES.findIndex((s) => s.key === currentStage);

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">执行控制</h1>
          <p className="mt-1 text-sm text-slate-400">启动 pipeline 并监控执行进度</p>
        </div>
        <button
          onClick={startExecution}
          disabled={running}
          className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg transition hover:from-indigo-500 hover:to-purple-500 disabled:opacity-50"
        >
          {running ? (
            <>
              <Square className="h-4 w-4" />
              执行中...
            </>
          ) : (
            <>
              <Play className="h-4 w-4" />
              启动 Run-to-Review
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-slate-300">总体进度</span>
          <span className="text-sm font-semibold text-white">{progress}%</span>
        </div>
        <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-white/10">
          <div
            className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>

        <div className="mt-6 flex items-center gap-1">
          {STAGES.map((stage, idx) => (
            <div key={stage.key} className="flex flex-1 flex-col items-center">
              <div
                className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold ${
                  idx < stageIdx
                    ? 'bg-emerald-500 text-white'
                    : idx === stageIdx
                    ? 'bg-indigo-500 text-white ring-2 ring-indigo-400/50'
                    : 'bg-white/10 text-slate-500'
                }`}
              >
                {idx < stageIdx ? (
                  <CheckCircle2 className="h-4 w-4" />
                ) : idx === stageIdx ? (
                  <Zap className="h-4 w-4" />
                ) : (
                  <Clock3 className="h-3.5 w-3.5" />
                )}
              </div>
              <span className="mt-1.5 text-[10px] text-slate-400">{stage.label}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-white/10 bg-white/5 p-5 backdrop-blur">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-indigo-400" />
            <h3 className="text-sm font-semibold text-slate-300">活跃任务</h3>
          </div>
          <div className="mt-3 space-y-2">
            {tasks
              .filter((t) => t.status === 'in_progress')
              .map((t) => (
                <div key={t.id} className="flex items-center gap-2 rounded-lg bg-white/5 px-3 py-2">
                  <Zap className="h-3.5 w-3.5 text-amber-400" />
                  <span className="text-sm text-white">{t.active_form || t.subject}</span>
                  <span className="ml-auto text-xs text-slate-400">{t.owner_role}</span>
                </div>
              ))}
            {tasks.filter((t) => t.status === 'in_progress').length === 0 && (
              <p className="text-xs text-slate-500">无活跃任务</p>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/5 p-5 backdrop-blur">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-emerald-400" />
            <h3 className="text-sm font-semibold text-slate-300">事件日志</h3>
          </div>
          <div className="mt-3 max-h-64 space-y-1.5 overflow-y-auto">
            {events.slice(-20).map((ev, idx) => (
              <div key={idx} className="flex items-start gap-2 text-xs">
                <span className="shrink-0 rounded bg-white/10 px-1.5 py-0.5 font-mono text-slate-400">
                  {ev.event_type}
                </span>
                {ev.role_id && <span className="text-indigo-300">{ev.role_id}</span>}
                {ev.stage && <span className="text-slate-500">@{ev.stage}</span>}
              </div>
            ))}
            <div ref={eventsEndRef} />
            {events.length === 0 && <p className="text-xs text-slate-500">暂无事件</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
