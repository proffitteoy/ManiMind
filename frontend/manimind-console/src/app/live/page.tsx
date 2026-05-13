import { Panel } from '@/components/ui/panel';
import { Badge } from '@/components/ui/badge';
import {
  transformStages,
  transformMetrics,
  transformEvents,
  transformAgents,
  type RuntimeResponse,
  type EventsResponse
} from '@/lib/live-transform';

export const dynamic = 'force-dynamic';

const API_BASE =
  process.env.NEXT_PUBLIC_MANIMIND_API_BASE_URL ??
  process.env.MANIMIND_API_BASE_URL ??
  'http://127.0.0.1:8000';

const PROJECT_ID = 'max-function-review-demo';
const SESSION_ID = 'manual-session';

type TraceItem = {
  trace_id: string;
  role_id: string;
  stage: string;
  timestamp: string;
  duration_ms: number;
  failure_reason?: string | null;
  schema_validation?: string;
};

type TraceSummary = {
  total_traces?: number;
  failed_traces?: number;
  by_failure?: Record<string, number>;
};

type TraceResponse = {
  project_id: string;
  session_id: string;
  total: number;
  items: TraceItem[];
  summary?: TraceSummary | null;
};

async function fetchJson<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export default async function LiveOverviewPage() {
  const [runtime, events, tracesResp] = await Promise.all([
    fetchJson<RuntimeResponse>(
      `${API_BASE}/api/projects/${PROJECT_ID}/runtime`
    ),
    fetchJson<EventsResponse>(
      `${API_BASE}/api/projects/${PROJECT_ID}/events?session_id=${SESSION_ID}&limit=50`
    ),
    fetchJson<TraceResponse>(
      `${API_BASE}/api/projects/${PROJECT_ID}/trace?session_id=${SESSION_ID}&limit=24`
    ),
  ]);

  const tasks = runtime?.execution_tasks?.execution_tasks ?? [];
  const allEvents = events?.session_events ?? events?.project_events ?? [];
  const profiles = runtime?.project_plan?.plan?.agent_profiles ?? [];
  const currentStage = runtime?.state?.current_stage ?? 'unknown';
  const projectTitle = runtime?.project_plan?.plan?.title ?? PROJECT_ID;

  const stages = transformStages(runtime?.state ?? null, allEvents);
  const metrics = transformMetrics(tasks);
  const recentEvents = transformEvents(allEvents);
  const agents = transformAgents(profiles, tasks);
  const traces = tracesResp?.items ?? [];
  const traceSummary = tracesResp?.summary ?? null;
  const failedTraceCount = traces.filter((item) => Boolean(item.failure_reason)).length;

  return (
    <>
      <header className='rounded-[24px] border border-white/75 bg-white/90 px-5 py-4 shadow-[0_20px_60px_rgba(99,102,241,0.06)] backdrop-blur-xl sm:px-7'>
        <div className='flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between'>
          <div>
            <h1 className='text-2xl font-semibold tracking-tight text-slate-950'>{projectTitle}</h1>
            <p className='mt-1 text-sm text-slate-500'>从输入到交付的闭环控制</p>
          </div>
          <Badge tone={currentStage === 'done' ? 'success' : 'active'}>
            {currentStage.toUpperCase()}
          </Badge>
        </div>
      </header>

      <Panel className='px-6 py-5'>
        <h2 className='mb-4 text-base font-semibold text-slate-900'>阶段流水线</h2>
        <div className='flex items-center justify-between gap-2'>
          {stages.map((stage) => (
            <div key={stage.key} className='flex flex-col items-center gap-1 text-center'>
              <div className={`flex h-10 w-10 items-center justify-center rounded-full text-xs font-bold ${stage.status === 'done' ? 'bg-emerald-500 text-white' : stage.status === 'active' ? 'bg-indigo-500 text-white ring-4 ring-indigo-100' : 'bg-slate-100 text-slate-400'}`}>
                {stage.status === 'done' ? '✓' : stage.status === 'active' ? '▶' : '○'}
              </div>
              <span className={`text-[11px] font-medium ${stage.status === 'done' ? 'text-slate-900' : stage.status === 'active' ? 'text-indigo-700' : 'text-slate-400'}`}>
                {stage.title}
              </span>
              <span className='text-[10px] text-slate-400'>{stage.at}</span>
            </div>
          ))}
        </div>
      </Panel>

      <div className='grid gap-5 lg:grid-cols-2'>
        <Panel className='p-5'>
          <h2 className='mb-4 text-base font-semibold text-slate-900'>系统概览</h2>
          <div className='grid grid-cols-2 gap-3'>
            {metrics.map((m) => (
              <div key={m.title} className='rounded-xl border border-slate-200/80 bg-slate-50/70 p-3'>
                <div className='text-xs text-slate-500'>{m.title}</div>
                <div className='mt-1 text-2xl font-bold text-slate-900'>{m.value}</div>
                <div className='mt-1 text-[11px] text-slate-500'>{m.delta}</div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel className='p-5'>
          <h2 className='mb-4 text-base font-semibold text-slate-900'>最近事件</h2>
          {recentEvents.length === 0 ? (
            <p className='text-sm text-slate-400'>暂无事件</p>
          ) : (
            <div className='space-y-0'>
              {recentEvents.map((ev, i) => (
                <div key={`${ev.at}-${i}`} className='flex gap-3'>
                  <div className='flex flex-col items-center'>
                    <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${ev.tone === 'critical' ? 'bg-rose-500' : ev.tone === 'success' ? 'bg-emerald-500' : ev.tone === 'warning' ? 'bg-amber-500' : 'bg-indigo-500'}`} />
                    {i < recentEvents.length - 1 && <span className='mt-1 h-full w-px bg-slate-200' />}
                  </div>
                  <div className='pb-3'>
                    <div className='flex items-center gap-2'>
                      <span className='text-xs text-slate-400'>{ev.at}</span>
                      <span className='text-xs font-semibold text-slate-600'>{ev.type}</span>
                    </div>
                    <div className='mt-0.5 text-xs text-slate-600'>{ev.detail}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <Panel className='p-5'>
        <div className='mb-4 flex items-center justify-between gap-3'>
          <div>
            <h2 className='text-base font-semibold text-slate-900'>LLM Trace</h2>
            <p className='mt-1 text-xs text-slate-500'>会话级模型调用记录（最近 24 条）</p>
          </div>
          <div className='flex items-center gap-2'>
            <Badge tone={failedTraceCount > 0 ? 'active' : 'success'}>
              {failedTraceCount > 0 ? `失败 ${failedTraceCount}` : '无失败'}
            </Badge>
            <Badge tone='neutral'>总计 {traceSummary?.total_traces ?? traces.length}</Badge>
          </div>
        </div>

        {traces.length === 0 ? (
          <p className='text-sm text-slate-400'>暂无 trace 记录</p>
        ) : (
          <div className='space-y-2.5'>
            {traces.slice(0, 8).map((trace) => {
              const failed = Boolean(trace.failure_reason);
              return (
                <div
                  key={trace.trace_id}
                  className='rounded-xl border border-slate-200/80 bg-slate-50/70 px-3 py-2.5'
                >
                  <div className='flex flex-wrap items-center justify-between gap-2'>
                    <div className='flex items-center gap-2'>
                      <span className='text-sm font-medium text-slate-900'>
                        {trace.role_id}@{trace.stage}
                      </span>
                      <Badge tone={failed ? 'active' : 'success'}>
                        {failed ? 'failed' : 'pass'}
                      </Badge>
                    </div>
                    <span className='text-xs text-slate-400'>
                      {new Date(trace.timestamp).toLocaleTimeString()} · {trace.duration_ms}ms
                    </span>
                  </div>
                  {trace.failure_reason ? (
                    <p className='mt-1 text-xs text-rose-600'>{trace.failure_reason}</p>
                  ) : (
                    <p className='mt-1 text-xs text-slate-500'>
                      schema={trace.schema_validation ?? 'n/a'}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Panel>

      {agents.length > 0 && (
        <Panel className='p-5'>
          <h2 className='mb-4 text-base font-semibold text-slate-900'>Agent 状态</h2>
          <div className='overflow-hidden rounded-xl border border-slate-200/80'>
            <div className='grid grid-cols-4 bg-slate-50 px-3 py-2 text-[11px] font-semibold text-slate-500'>
              <span>角色</span><span>状态</span><span>完成率</span><span>任务数</span>
            </div>
            {agents.map((a) => (
              <div key={a.name} className='grid grid-cols-4 items-center border-t border-slate-100 px-3 py-2 text-xs text-slate-700'>
                <span className='font-medium text-slate-900'>{a.name}</span>
                <span className='inline-flex items-center gap-1.5'>
                  <span className={`h-2 w-2 rounded-full ${a.status === '繁忙' ? 'bg-amber-500' : a.status === '待命' ? 'bg-slate-300' : 'bg-emerald-500'}`} />
                  {a.status}
                </span>
                <span>{a.successRate}</span>
                <span>{a.todayTasks}</span>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </>
  );
}
