import { Badge } from '@/components/ui/badge';
import { Panel } from '@/components/ui/panel';

import { ReviewActions } from './review-actions';

export const dynamic = 'force-dynamic';

type SearchParams = {
  project_id?: string;
  session_id?: string;
  manifest_path?: string;
};

type RuntimeResponse = {
  project_id: string;
  state?: { current_stage?: string };
  execution_tasks?: { execution_tasks?: TaskSnapshot[] };
  context_records?: { contexts?: ContextSnapshot[] };
};

type TaskSnapshot = {
  id: string;
  stage: string;
  owner_role: string;
  status: string;
  last_progress?: string | null;
  blocked_reason?: string | null;
};

type ContextSnapshot = {
  key: string;
  scope: string;
  writer_role: string;
};

type EventsResponse = {
  project_events?: EventSnapshot[];
  session_events?: EventSnapshot[];
};

type EventSnapshot = {
  timestamp?: string;
  event?: string;
  role_id?: string;
  task_id?: string;
};

type ReviewReturnResponse = {
  payload?: Record<string, unknown> | null;
};

async function fetchJson<T>(url: string): Promise<T | null> {
  try {
    const response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

function toneByStage(stage: string | undefined): 'neutral' | 'active' | 'success' {
  if (stage === 'review') {
    return 'active';
  }
  if (stage === 'done') {
    return 'success';
  }
  return 'neutral';
}

export default async function LivePage({
  searchParams
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const projectId = params.project_id ?? 'max-function-review-demo';
  const sessionId = params.session_id ?? 'manual-session';
  const manifestPath = params.manifest_path ?? 'configs/max-function-review-demo.json';
  const apiBaseUrl =
    process.env.NEXT_PUBLIC_MANIMIND_API_BASE_URL ??
    process.env.MANIMIND_API_BASE_URL ??
    'http://127.0.0.1:8000';

  const runtime = await fetchJson<RuntimeResponse>(
    `${apiBaseUrl}/api/projects/${encodeURIComponent(projectId)}/runtime`
  );
  const events = await fetchJson<EventsResponse>(
    `${apiBaseUrl}/api/projects/${encodeURIComponent(projectId)}/events?session_id=${encodeURIComponent(sessionId)}&limit=50`
  );
  const reviewReturn = await fetchJson<ReviewReturnResponse>(
    `${apiBaseUrl}/api/projects/${encodeURIComponent(projectId)}/review-return?session_id=${encodeURIComponent(sessionId)}`
  );

  const tasks = runtime?.execution_tasks?.execution_tasks ?? [];
  const contexts = runtime?.context_records?.contexts ?? [];
  const sessionEvents = events?.session_events ?? [];
  const projectEvents = events?.project_events ?? [];
  const stage = runtime?.state?.current_stage;
  const latestReturn = reviewReturn?.payload ?? null;

  return (
    <main className='min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(99,102,241,0.16),transparent_22%),radial-gradient(circle_at_top_right,rgba(56,189,248,0.12),transparent_24%),linear-gradient(180deg,#eef4ff_0%,#f7f9fc_42%,#f4f7fb_100%)] px-4 py-6 text-slate-900 sm:px-6 lg:px-8'>
      <div className='mx-auto flex w-full max-w-[1400px] flex-col gap-5'>
        <Panel className='p-6'>
          <div className='flex flex-wrap items-center justify-between gap-3'>
            <div>
              <h1 className='text-2xl font-semibold text-slate-900'>ManiMind Live Console</h1>
              <p className='mt-2 text-sm text-slate-600'>
                project_id=<code>{projectId}</code>，session_id=<code>{sessionId}</code>
              </p>
              <p className='mt-1 text-sm text-slate-600'>
                manifest_path=<code>{manifestPath}</code>
              </p>
            </div>
            <div className='flex items-center gap-2'>
              <Badge tone={toneByStage(stage)}>{stage ?? 'unknown'}</Badge>
              <Badge tone='neutral'>tasks:{tasks.length}</Badge>
              <Badge tone='neutral'>events:{sessionEvents.length}</Badge>
            </div>
          </div>
        </Panel>

        <ReviewActions apiBaseUrl={apiBaseUrl} manifestPath={manifestPath} sessionId={sessionId} />

        <div className='grid gap-5 xl:grid-cols-3'>
          <Panel className='xl:col-span-2'>
            <h2 className='text-lg font-semibold text-slate-900'>Execution Tasks</h2>
            <div className='mt-4 overflow-auto rounded-xl border border-slate-200'>
              <table className='min-w-full text-sm'>
                <thead className='bg-slate-50 text-left text-slate-500'>
                  <tr>
                    <th className='px-3 py-2'>Task</th>
                    <th className='px-3 py-2'>Stage</th>
                    <th className='px-3 py-2'>Owner</th>
                    <th className='px-3 py-2'>Status</th>
                    <th className='px-3 py-2'>Progress / Blocker</th>
                  </tr>
                </thead>
                <tbody>
                  {tasks.map((task) => (
                    <tr key={task.id} className='border-t border-slate-200'>
                      <td className='px-3 py-2 font-medium text-slate-900'>{task.id}</td>
                      <td className='px-3 py-2 text-slate-600'>{task.stage}</td>
                      <td className='px-3 py-2 text-slate-600'>{task.owner_role}</td>
                      <td className='px-3 py-2 text-slate-600'>{task.status}</td>
                      <td className='px-3 py-2 text-slate-600'>
                        {task.blocked_reason ?? task.last_progress ?? '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel>
            <h2 className='text-lg font-semibold text-slate-900'>Latest Return Memo</h2>
            <pre className='mt-4 max-h-[320px] overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs leading-6 text-slate-700'>
              {latestReturn ? JSON.stringify(latestReturn, null, 2) : 'No return memo.'}
            </pre>
          </Panel>
        </div>

        <div className='grid gap-5 xl:grid-cols-2'>
          <Panel>
            <h2 className='text-lg font-semibold text-slate-900'>Session Events</h2>
            <pre className='mt-4 max-h-[320px] overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs leading-6 text-slate-700'>
              {JSON.stringify(sessionEvents, null, 2)}
            </pre>
          </Panel>
          <Panel>
            <h2 className='text-lg font-semibold text-slate-900'>Context Records (sample)</h2>
            <pre className='mt-4 max-h-[320px] overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs leading-6 text-slate-700'>
              {JSON.stringify(contexts.slice(0, 20), null, 2)}
            </pre>
          </Panel>
        </div>

        <Panel>
          <h2 className='text-lg font-semibold text-slate-900'>Project Events (tail)</h2>
          <pre className='mt-4 max-h-[260px] overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs leading-6 text-slate-700'>
            {JSON.stringify(projectEvents.slice(-30), null, 2)}
          </pre>
        </Panel>
      </div>
    </main>
  );
}
