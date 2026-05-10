import { DashboardSections } from '@/components/console/dashboard-sections';
import { Badge } from '@/components/ui/badge';
import { consoleDemo, type ActionItem, type NavItem } from '@/data/console-demo';
import { cn } from '@/lib/utils';
import {
  BookCopy,
  Boxes,
  Ellipsis,
  FileCog,
  FolderKanban,
  LayoutDashboard,
  ListTodo,
  RefreshCcw,
  Settings2,
  ShieldCheck,
  Sparkles,
  Workflow
} from 'lucide-react';

const navIcons = {
  overview: LayoutDashboard,
  projects: FolderKanban,
  tasks: ListTodo,
  contexts: BookCopy,
  runtime: Workflow,
  artifacts: Boxes,
  review: ShieldCheck,
  settings: Settings2
} as const;

const actionIcons = {
  plan: Sparkles,
  context: FileCog,
  refresh: RefreshCcw,
  more: Ellipsis
} as const;

export function DashboardShell() {
  return (
    <div className='min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(99,102,241,0.16),transparent_22%),radial-gradient(circle_at_top_right,rgba(56,189,248,0.12),transparent_24%),linear-gradient(180deg,#eef4ff_0%,#f7f9fc_42%,#f4f7fb_100%)] text-slate-900'>
      <div className='mx-auto grid min-h-screen max-w-[1760px] lg:grid-cols-[280px_minmax(0,1fr)]'>
        <ConsoleSidebar navigation={consoleDemo.navigation} />

        <main className='relative overflow-hidden px-4 py-4 sm:px-6 lg:px-8 lg:py-6'>
          <div className='pointer-events-none absolute left-12 top-0 h-52 w-52 rounded-full bg-indigo-200/30 blur-3xl' />
          <div className='pointer-events-none absolute right-0 top-24 h-64 w-64 rounded-full bg-sky-200/30 blur-3xl' />

          <div className='relative flex flex-col gap-5'>
            <MobileNavigation navigation={consoleDemo.navigation} />

            <header className='rounded-[34px] border border-white/75 bg-white/88 px-5 py-5 shadow-[0_30px_80px_rgba(99,102,241,0.08)] backdrop-blur-xl sm:px-7'>
              <div className='flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between'>
                <div>
                  <div className='flex flex-wrap items-center gap-3'>
                    <h1 className='font-display text-3xl font-semibold tracking-tight text-slate-950 sm:text-[2.35rem]'>
                      {consoleDemo.project.title}
                    </h1>
                    <Badge tone='success'>{consoleDemo.project.status}</Badge>
                  </div>
                  <p className='mt-3 max-w-3xl text-sm leading-7 text-slate-500 sm:text-base'>
                    {consoleDemo.project.subtitle}
                  </p>
                  <div className='mt-3 text-sm font-medium text-indigo-600'>
                    {consoleDemo.project.statusDetail}
                  </div>
                </div>

                <div className='flex flex-wrap gap-3 xl:max-w-[560px] xl:justify-end'>
                  {consoleDemo.quickActions.map((action) => (
                    <QuickActionButton key={action.title} action={action} />
                  ))}
                </div>
              </div>
            </header>

            <DashboardSections
              stages={consoleDemo.stages}
              taskColumns={consoleDemo.taskColumns}
              runtimeAssets={consoleDemo.runtimeAssets}
              contextItems={consoleDemo.contextItems}
              events={consoleDemo.events}
              metrics={consoleDemo.metrics}
              agents={consoleDemo.agents}
              artifacts={consoleDemo.artifacts}
              capabilities={consoleDemo.capabilities}
              workflow={consoleDemo.workflow}
            />
          </div>
        </main>
      </div>
    </div>
  );
}

function ConsoleSidebar({ navigation }: { navigation: NavItem[] }) {
  return (
    <aside className='hidden bg-[linear-gradient(180deg,#07122f_0%,#08162f_38%,#091a34_100%)] px-5 py-7 text-white lg:flex lg:min-h-screen lg:flex-col'>
      <div>
        <div className='flex items-center gap-3'>
          <div className='flex h-12 w-12 items-center justify-center rounded-2xl bg-white/10 shadow-[0_16px_40px_rgba(59,130,246,0.16)] backdrop-blur'>
            <Sparkles className='h-6 w-6 text-indigo-200' />
          </div>
          <div>
            <div className='font-display text-[1.75rem] font-semibold tracking-tight text-white'>ManiMind</div>
            <div className='text-sm text-slate-300'>数学科普自动化编排控制台</div>
          </div>
        </div>

        <nav className='mt-9 space-y-2'>
          {navigation.map((item) => {
            const Icon = navIcons[item.icon];
            return (
              <button
                key={item.title}
                type='button'
                className={cn(
                  'flex w-full items-center gap-3 rounded-[20px] px-4 py-3 text-left text-sm font-medium transition',
                  item.active
                    ? 'bg-[linear-gradient(135deg,#355cff_0%,#4f46e5_50%,#6d28d9_100%)] text-white shadow-[0_20px_40px_rgba(79,70,229,0.28)]'
                    : 'text-slate-300 hover:bg-white/6 hover:text-white'
                )}
              >
                <Icon className='h-5 w-5' />
                <span>{item.title}</span>
              </button>
            );
          })}
        </nav>
      </div>

      <div className='mt-auto space-y-4'>
        <div className='rounded-[24px] border border-white/10 bg-white/6 px-4 py-4 backdrop-blur'>
          <div className='text-xs font-semibold tracking-[0.2em] text-slate-400 uppercase'>当前项目</div>
          <div className='mt-3 text-base font-semibold text-white'>数学科普自动化项目</div>
          <div className='mt-2 inline-flex items-center gap-2 text-sm text-emerald-300'>
            <span className='h-2.5 w-2.5 rounded-full bg-emerald-400' />
            运行中
          </div>
        </div>

        <div className='flex items-center gap-3 rounded-[22px] border border-white/10 bg-white/6 px-4 py-4 backdrop-blur'>
          <div className='flex h-11 w-11 items-center justify-center rounded-full border border-white/15 bg-white/10 font-semibold text-white'>
            A
          </div>
          <div>
            <div className='font-medium text-white'>Admin</div>
            <div className='text-sm text-slate-400'>管理员</div>
          </div>
        </div>
      </div>
    </aside>
  );
}

function MobileNavigation({ navigation }: { navigation: NavItem[] }) {
  return (
    <div className='flex gap-2 overflow-x-auto lg:hidden'>
      {navigation.map((item) => {
        const Icon = navIcons[item.icon];
        return (
          <button
            key={item.title}
            type='button'
            className={cn(
              'inline-flex shrink-0 items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium backdrop-blur',
              item.active
                ? 'border-indigo-200 bg-indigo-500 text-white'
                : 'border-white/70 bg-white/70 text-slate-700'
            )}
          >
            <Icon className='h-4 w-4' />
            {item.title}
          </button>
        );
      })}
    </div>
  );
}

function QuickActionButton({ action }: { action: ActionItem }) {
  const Icon = actionIcons[action.icon];

  return (
    <button
      type='button'
      className={cn(
        'inline-flex items-center gap-2 rounded-2xl border px-4 py-3 text-sm font-medium transition',
        action.tone === 'primary'
          ? 'border-indigo-500 bg-[linear-gradient(135deg,#4f46e5_0%,#6d28d9_100%)] text-white shadow-[0_18px_40px_rgba(79,70,229,0.24)] hover:-translate-y-0.5'
          : 'border-slate-200/80 bg-white text-slate-700 shadow-[0_14px_30px_rgba(15,23,42,0.05)] hover:border-indigo-200 hover:text-indigo-700'
      )}
    >
      <Icon className='h-4 w-4' />
      {action.title}
    </button>
  );
}
