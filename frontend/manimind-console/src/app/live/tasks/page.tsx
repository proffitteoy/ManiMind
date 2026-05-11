import { Panel } from '@/components/ui/panel';
import { Badge } from '@/components/ui/badge';
import { transformTaskColumns, type RuntimeResponse } from '@/lib/live-transform';

export const dynamic = 'force-dynamic';

const API_BASE =
  process.env.NEXT_PUBLIC_MANIMIND_API_BASE_URL ??
  process.env.MANIMIND_API_BASE_URL ??
  'http://127.0.0.1:8000';

const PROJECT_ID = 'max-function-review-demo';

export default async function TasksPage() {
  let runtime: RuntimeResponse | null = null;
  try {
    const res = await fetch(`${API_BASE}/api/projects/${PROJECT_ID}/runtime`, { cache: 'no-store' });
    if (res.ok) runtime = await res.json();
  } catch {}

  const tasks = runtime?.execution_tasks?.execution_tasks ?? [];
  const columns = transformTaskColumns(tasks);

  return (
    <>
      <header className='rounded-[24px] border border-white/75 bg-white/90 px-5 py-4 backdrop-blur-xl sm:px-7'>
        <h1 className='text-2xl font-semibold text-slate-950'>任务看板</h1>
        <p className='mt-1 text-sm text-slate-500'>共 {tasks.length} 个任务</p>
      </header>

      <div className='grid gap-5 xl:grid-cols-3'>
        {columns.map((col) => (
          <Panel key={col.status} className='p-5'>
            <div className='mb-4 flex items-center justify-between'>
              <h2 className='text-base font-semibold text-slate-900'>{col.title}</h2>
              <Badge tone={col.status === 'completed' ? 'success' : col.status === 'in_progress' ? 'active' : 'neutral'}>
                {col.count}
              </Badge>
            </div>
            <div className='space-y-2'>
              {tasks
                .filter((t) => t.status === col.status)
                .map((task) => (
                  <div key={task.id} className='rounded-xl border border-slate-200/80 bg-white px-3 py-3 shadow-sm'>
                    <div className='text-sm font-medium text-slate-900'>{task.subject}</div>
                    <div className='mt-1 flex items-center gap-2 text-xs text-slate-500'>
                      <span>{task.stage}</span>
                      <span>·</span>
                      <span>{task.owner_role}</span>
                    </div>
                    {task.blocked_reason && (
                      <div className='mt-2 rounded-lg bg-rose-50 px-2 py-1 text-xs text-rose-600'>
                        阻塞：{task.blocked_reason}
                      </div>
                    )}
                    {task.last_progress && (
                      <div className='mt-1 text-xs text-slate-400'>进度：{task.last_progress}</div>
                    )}
                  </div>
                ))}
            </div>
          </Panel>
        ))}
      </div>
    </>
  );
}
