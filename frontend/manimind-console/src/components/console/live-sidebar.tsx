'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { cn } from '@/lib/utils';
import {
  Activity,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  LayoutDashboard,
  ListTodo,
  Package,
  Pause,
  Sparkles,
  Zap
} from 'lucide-react';

type NavItem = {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
};

const navItems: NavItem[] = [
  { href: '/live', label: '总览', icon: LayoutDashboard },
  { href: '/live/tasks', label: '任务', icon: ListTodo },
  { href: '/live/review', label: '审核', icon: ClipboardCheck },
  { href: '/live/artifacts', label: '产物', icon: Package },
];

export type SidebarData = {
  projectTitle: string;
  currentStage: string;
  completed: number;
  inProgress: number;
  pending: number;
  blocked: number;
};

const STAGE_CN: Record<string, string> = {
  prestart: '预启动',
  ingest: '素材导入',
  summarize: '内容摘要',
  plan: '计划生成',
  dispatch: '任务分发',
  review: '审核关卡',
  post_produce: '后期制作',
  package: '打包交付',
  done: '已完成',
  blocked: '已阻塞',
  unknown: '未知'
};

export function LiveSidebar({ data }: { data: SidebarData }) {
  const pathname = usePathname();

  function isActive(href: string) {
    if (href === '/live') return pathname === '/live';
    return pathname.startsWith(href);
  }

  return (
    <aside className='hidden bg-[linear-gradient(180deg,#07122f_0%,#08162f_38%,#091a34_100%)] px-5 py-7 text-white lg:flex lg:min-h-screen lg:flex-col'>
      <div>
        <div className='flex items-center gap-3'>
          <div className='flex h-12 w-12 items-center justify-center rounded-2xl bg-white/10 shadow-[0_16px_40px_rgba(59,130,246,0.16)] backdrop-blur'>
            <Sparkles className='h-6 w-6 text-indigo-200' />
          </div>
          <div>
            <div className='text-[1.75rem] font-semibold tracking-tight text-white'>ManiMind</div>
            <div className='text-sm text-slate-300'>编排控制台</div>
          </div>
        </div>

        <nav className='mt-9 space-y-2'>
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'flex w-full items-center gap-3 rounded-[20px] px-4 py-3 text-left text-sm font-medium transition',
                  active
                    ? 'bg-[linear-gradient(135deg,#355cff_0%,#4f46e5_50%,#6d28d9_100%)] text-white shadow-[0_20px_40px_rgba(79,70,229,0.28)]'
                    : 'text-slate-300 hover:bg-white/6 hover:text-white'
                )}
              >
                <Icon className='h-5 w-5' />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className='mt-8 rounded-[20px] border border-white/10 bg-white/6 px-4 py-4'>
          <div className='flex items-center gap-2'>
            <Activity className='h-4 w-4 text-indigo-300' />
            <span className='text-xs font-semibold tracking-wide text-slate-400'>当前阶段</span>
          </div>
          <div className='mt-2 text-lg font-semibold text-white'>
            {STAGE_CN[data.currentStage] ?? data.currentStage}
          </div>
        </div>

        <div className='mt-4 rounded-[20px] border border-white/10 bg-white/6 px-4 py-4'>
          <span className='text-xs font-semibold tracking-wide text-slate-400'>任务概览</span>
          <div className='mt-3 space-y-2'>
            <StatRow icon={<CheckCircle2 className='h-3.5 w-3.5 text-emerald-400' />} label='已完成' value={data.completed} />
            <StatRow icon={<Zap className='h-3.5 w-3.5 text-amber-400' />} label='进行中' value={data.inProgress} />
            <StatRow icon={<Clock3 className='h-3.5 w-3.5 text-slate-400' />} label='待处理' value={data.pending} />
            {data.blocked > 0 && (
              <StatRow icon={<Pause className='h-3.5 w-3.5 text-rose-400' />} label='已阻塞' value={data.blocked} />
            )}
          </div>
        </div>
      </div>

      <div className='mt-auto'>
        <div className='rounded-[24px] border border-white/10 bg-white/6 px-4 py-4 backdrop-blur'>
          <div className='text-xs font-semibold tracking-[0.2em] text-slate-400 uppercase'>当前项目</div>
          <div className='mt-3 text-base font-semibold text-white'>{data.projectTitle}</div>
          <div className='mt-2 inline-flex items-center gap-2 text-sm text-emerald-300'>
            <span className='h-2.5 w-2.5 rounded-full bg-emerald-400' />
            {data.currentStage === 'done' ? '已完成' : '运行中'}
          </div>
        </div>
      </div>
    </aside>
  );
}

function StatRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return (
    <div className='flex items-center justify-between'>
      <div className='flex items-center gap-2'>
        {icon}
        <span className='text-sm text-slate-300'>{label}</span>
      </div>
      <span className='text-sm font-semibold text-white'>{value}</span>
    </div>
  );
}
