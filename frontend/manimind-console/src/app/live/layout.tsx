import { LiveSidebar, type SidebarData } from '@/components/console/live-sidebar';

export const dynamic = 'force-dynamic';

const API_BASE =
  process.env.NEXT_PUBLIC_MANIMIND_API_BASE_URL ??
  process.env.MANIMIND_API_BASE_URL ??
  'http://127.0.0.1:8000';

const DEFAULT_PROJECT = 'max-function-review-demo';

type RuntimeResponse = {
  state?: { current_stage?: string } | null;
  execution_tasks?: { execution_tasks?: { status: string; blocked_reason?: string | null }[] } | null;
  project_plan?: { plan?: { title?: string } } | null;
};

async function fetchSidebarData(): Promise<SidebarData> {
  try {
    const res = await fetch(`${API_BASE}/api/projects/${DEFAULT_PROJECT}/runtime`, { cache: 'no-store' });
    if (!res.ok) throw new Error();
    const data: RuntimeResponse = await res.json();
    const tasks = data?.execution_tasks?.execution_tasks ?? [];
    return {
      projectTitle: data?.project_plan?.plan?.title ?? DEFAULT_PROJECT,
      currentStage: data?.state?.current_stage ?? 'unknown',
      completed: tasks.filter((t) => t.status === 'completed').length,
      inProgress: tasks.filter((t) => t.status === 'in_progress').length,
      pending: tasks.filter((t) => t.status === 'pending').length,
      blocked: tasks.filter((t) => t.blocked_reason).length,
    };
  } catch {
    return { projectTitle: DEFAULT_PROJECT, currentStage: 'unknown', completed: 0, inProgress: 0, pending: 0, blocked: 0 };
  }
}

export default async function LiveLayout({ children }: { children: React.ReactNode }) {
  const sidebarData = await fetchSidebarData();

  return (
    <div className='min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(99,102,241,0.16),transparent_22%),radial-gradient(circle_at_top_right,rgba(56,189,248,0.12),transparent_24%),linear-gradient(180deg,#eef4ff_0%,#f7f9fc_42%,#f4f7fb_100%)] text-slate-900'>
      <div className='mx-auto grid min-h-screen max-w-[1760px] lg:grid-cols-[280px_minmax(0,1fr)]'>
        <LiveSidebar data={sidebarData} />
        <main className='relative overflow-hidden px-4 py-4 sm:px-6 lg:px-8 lg:py-6'>
          <div className='pointer-events-none absolute left-12 top-0 h-52 w-52 rounded-full bg-indigo-200/30 blur-3xl' />
          <div className='pointer-events-none absolute right-0 top-24 h-64 w-64 rounded-full bg-sky-200/30 blur-3xl' />
          <div className='relative flex flex-col gap-5'>
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
