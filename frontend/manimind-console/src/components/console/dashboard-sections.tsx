import { Badge } from '@/components/ui/badge';
import { Panel } from '@/components/ui/panel';
import type {
  AgentItem,
  ArtifactItem,
  ArtifactScore,
  ContextItem,
  EventItem,
  MetricItem,
  RuntimeAsset,
  StageItem,
  TaskColumn,
  WorkflowStep
} from '@/data/console-demo';
import { cn } from '@/lib/utils';
import {
  ArrowRight,
  Book,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  FileText,
  Flag,
  Play,
  Ruler,
  Send,
  Sparkles,
  Target,
  TrendingUp,
  Users,
  Zap
} from 'lucide-react';

type DashboardSectionsProps = {
  stages: StageItem[];
  taskColumns: TaskColumn[];
  runtimeAssets: RuntimeAsset[];
  contextItems: ContextItem[];
  events: EventItem[];
  metrics: MetricItem[];
  agents: AgentItem[];
  artifacts: ArtifactItem[];
  artifactScores: ArtifactScore[];
  capabilities: string[];
  workflow: WorkflowStep[];
};

/* --- PLACEHOLDER_SECTIONS --- */

const stageStyles = {
  done: {
    circle: 'bg-emerald-500 text-white',
    label: 'text-slate-900 font-bold',
    summary: 'text-emerald-600'
  },
  active: {
    circle: 'bg-indigo-500 text-white ring-8 ring-indigo-100/80',
    label: 'text-indigo-700 font-bold',
    summary: 'text-indigo-600'
  },
  waiting: {
    circle: 'bg-slate-100 text-slate-400',
    label: 'text-slate-400',
    summary: 'text-slate-400'
  }
} as const;

const columnStyles = {
  pending: 'bg-slate-100 text-slate-600',
  in_progress: 'bg-indigo-100 text-indigo-700',
  completed: 'bg-emerald-100 text-emerald-700'
} as const;

const eventStyles = {
  success: 'bg-emerald-500',
  warning: 'bg-amber-500',
  info: 'bg-indigo-500',
  critical: 'bg-rose-500'
} as const;

const contextIcons = {
  target: Target,
  users: Users,
  formula: TrendingUp,
  constraint: Ruler,
  book: Book
} as const;

export function DashboardSections({
  stages,
  taskColumns,
  runtimeAssets,
  contextItems,
  events,
  metrics,
  agents,
  artifacts,
  artifactScores,
  capabilities,
  workflow
}: DashboardSectionsProps) {
  return (
    <>
      <PipelineRail stages={stages} />

      <div className='grid gap-5 xl:grid-cols-[1.4fr_0.82fr_0.85fr_0.92fr]'>
        <TaskBoard taskColumns={taskColumns} />
        <RuntimePanel runtimeAssets={runtimeAssets} />
        <ContextPanel contextItems={contextItems} />
        <EventPanel events={events} />
      </div>

      <div className='grid gap-5 xl:grid-cols-[0.9fr_1fr_1.28fr_0.92fr]'>
        <MetricsPanel metrics={metrics} />
        <AgentsPanel agents={agents} />
        <ArtifactsPanel artifacts={artifacts} scores={artifactScores} />
        <CapabilityPanel capabilities={capabilities} />
      </div>

      <WorkflowStrip workflow={workflow} />
    </>
  );
}

/* --- PLACEHOLDER_PIPELINE --- */

function PipelineRail({ stages }: { stages: StageItem[] }) {
  return (
    <Panel className='px-6 py-5'>
      <div className='flex items-center justify-between'>
        {stages.map((stage, index) => {
          const style = stageStyles[stage.status];
          const Icon = stage.status === 'done' ? Check : stage.status === 'active' ? Send : Clock3;
          return (
            <div key={stage.key} className='flex items-center'>
              <div className='flex flex-col items-center gap-2'>
                <div className={cn('flex h-12 w-12 items-center justify-center rounded-full', style.circle)}>
                  <Icon className='h-5 w-5' />
                </div>
                <div className='text-center'>
                  <div className={cn('text-xs font-semibold tracking-wide', style.label)}>
                    {stage.title}
                  </div>
                  <div className='mt-0.5 text-[11px] text-slate-400'>{stage.at}</div>
                  <div className={cn('text-[11px] font-medium', style.summary)}>{stage.summary}</div>
                </div>
              </div>
              {index < stages.length - 1 && (
                <div className='mx-2 flex items-center'>
                  <div className={cn(
                    'h-0.5 w-8',
                    stage.status === 'done' ? 'bg-emerald-300' : 'bg-slate-200'
                  )} />
                  <ArrowRight className={cn(
                    'h-3.5 w-3.5',
                    stage.status === 'done' ? 'text-emerald-400' : 'text-slate-300'
                  )} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

/* --- PLACEHOLDER_TASKBOARD --- */

function TaskBoard({ taskColumns }: { taskColumns: TaskColumn[] }) {
  return (
    <Panel className='p-5'>
      <div className='mb-4 flex items-center gap-2'>
        <span className='flex h-6 w-6 items-center justify-center rounded-full bg-indigo-500 text-xs font-bold text-white'>A</span>
        <h2 className='text-base font-semibold text-slate-900'>任务看板</h2>
      </div>

      <div className='grid gap-3 xl:grid-cols-3'>
        {taskColumns.map((column) => (
          <div key={column.title} className='rounded-2xl border border-slate-200/80 bg-slate-50/70 p-3'>
            <div className='mb-3 flex items-center justify-between'>
              <span className='text-sm font-semibold text-slate-700'>{column.title}</span>
              <span className={cn('rounded-full px-2 py-0.5 text-xs font-semibold', columnStyles[column.status])}>
                {column.count}
              </span>
            </div>
            <div className='space-y-2'>
              {column.tasks.map((task) => (
                <div key={task.title} className='rounded-xl border border-white bg-white px-3 py-2.5 shadow-sm'>
                  <div className='flex items-start justify-between gap-2'>
                    <div>
                      <div className='text-sm font-medium text-slate-900'>{task.title}</div>
                      <div className='mt-1 text-[11px] font-semibold tracking-wide text-indigo-500 uppercase'>
                        {task.stage}
                      </div>
                    </div>
                    {task.owner && (
                      <div className='flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-100 text-[10px] font-semibold text-slate-600'>
                        {task.owner}
                      </div>
                    )}
                    {column.status === 'completed' && (
                      <div className='flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-white'>
                        <Check className='h-3 w-3' />
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
            <button type='button' className='mt-3 text-xs font-medium text-indigo-600 hover:text-indigo-800'>
              + {column.footer}
            </button>
          </div>
        ))}
      </div>
    </Panel>
  );
}

/* --- PLACEHOLDER_RUNTIME --- */

function RuntimePanel({ runtimeAssets }: { runtimeAssets: RuntimeAsset[] }) {
  return (
    <Panel className='p-5'>
      <div className='mb-4 flex items-center justify-between'>
        <div className='flex items-center gap-2'>
          <span className='flex h-6 w-6 items-center justify-center rounded-full bg-indigo-500 text-xs font-bold text-white'>B</span>
          <h2 className='text-base font-semibold text-slate-900'>项目运行时</h2>
        </div>
        <Badge tone='success'>事实源</Badge>
      </div>
      <p className='mb-4 text-xs text-slate-500'>运行时驱动的单一事实源</p>

      <div className='space-y-2.5'>
        {runtimeAssets.map((asset) => (
          <div key={asset.title} className='flex items-center justify-between gap-2 rounded-xl border border-slate-200/80 bg-slate-50/70 px-3 py-2.5'>
            <div className='flex min-w-0 items-center gap-2.5'>
              <FileText className='h-4 w-4 shrink-0 text-indigo-500' />
              <span className='truncate text-sm font-medium text-slate-900'>{asset.title}</span>
            </div>
            <div className='flex shrink-0 items-center gap-2'>
              <Badge tone={asset.state === '最新' ? 'active' : 'success'}>{asset.state}</Badge>
              <span className='text-xs text-slate-400'>{asset.updatedAt}</span>
            </div>
          </div>
        ))}
      </div>
      <button type='button' className='mt-4 flex items-center gap-1 text-sm font-medium text-indigo-600 hover:text-indigo-800'>
        打开运行时目录 <ArrowRight className='h-3.5 w-3.5' />
      </button>
    </Panel>
  );
}

/* --- PLACEHOLDER_CONTEXT --- */

function ContextPanel({ contextItems }: { contextItems: ContextItem[] }) {
  return (
    <Panel className='p-5'>
      <div className='mb-4 flex items-center justify-between'>
        <div className='flex items-center gap-2'>
          <span className='flex h-6 w-6 items-center justify-center rounded-full bg-indigo-500 text-xs font-bold text-white'>C</span>
          <h2 className='text-base font-semibold text-slate-900'>上下文包</h2>
        </div>
        <span className='text-xs text-slate-400'>最新 10:18</span>
      </div>

      <div className='space-y-2.5'>
        {contextItems.map((item) => {
          const Icon = contextIcons[item.icon];
          return (
            <div key={item.title} className='flex items-start gap-3 rounded-xl border border-slate-200/70 bg-white px-3 py-2.5'>
              <div className='mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-500'>
                <Icon className='h-3.5 w-3.5' />
              </div>
              <div className='min-w-0'>
                <div className='text-sm font-medium text-slate-900'>{item.title}</div>
                <div className='mt-0.5 truncate text-xs text-slate-500'>{item.summary}</div>
              </div>
            </div>
          );
        })}
      </div>
      <button type='button' className='mt-4 text-sm font-medium text-indigo-600 hover:text-indigo-800'>
        查看详情
      </button>
    </Panel>
  );
}

/* --- PLACEHOLDER_EVENT --- */

function EventPanel({ events }: { events: EventItem[] }) {
  return (
    <Panel className='p-5'>
      <div className='mb-4 flex items-center justify-between'>
        <div className='flex items-center gap-2'>
          <span className='flex h-6 w-6 items-center justify-center rounded-full bg-indigo-500 text-xs font-bold text-white'>D</span>
          <h2 className='text-base font-semibold text-slate-900'>事件日志</h2>
          <span className='text-xs text-slate-400'>事件流</span>
        </div>
        <span className='text-xs text-slate-400'>最新 10:18</span>
      </div>

      <div className='space-y-0'>
        {events.map((event, i) => (
          <div key={`${event.at}-${event.type}`} className='flex gap-3'>
            <div className='flex flex-col items-center'>
              <span className={cn('mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full', eventStyles[event.tone])} />
              {i < events.length - 1 && <span className='mt-1 h-full w-px bg-slate-200' />}
            </div>
            <div className='pb-3'>
              <div className='flex items-center gap-2'>
                <span className='text-xs text-slate-400'>{event.at}</span>
                <span className={cn(
                  'text-xs font-semibold',
                  event.tone === 'critical' ? 'text-rose-600' : event.tone === 'success' ? 'text-emerald-600' : event.tone === 'warning' ? 'text-amber-600' : 'text-indigo-600'
                )}>{event.type}</span>
              </div>
              <div className='mt-0.5 text-xs text-slate-600'>{event.detail}</div>
            </div>
          </div>
        ))}
      </div>
      <button type='button' className='mt-2 flex items-center gap-1 text-sm font-medium text-indigo-600 hover:text-indigo-800'>
        查看完整日志 <ArrowRight className='h-3.5 w-3.5' />
      </button>
    </Panel>
  );
}

/* --- PLACEHOLDER_METRICS --- */

function MetricsPanel({ metrics }: { metrics: MetricItem[] }) {
  return (
    <Panel className='p-5'>
      <div className='mb-4'>
        <h2 className='text-base font-semibold text-slate-900'>系统概览</h2>
      </div>
      <div className='grid grid-cols-2 gap-3'>
        {metrics.map((metric) => (
          <div key={metric.title} className='rounded-xl border border-slate-200/80 bg-slate-50/70 p-3'>
            <div className='text-xs text-slate-500'>{metric.title}</div>
            <div className='mt-2 text-2xl font-bold text-slate-900'>{metric.value}</div>
            <div className='mt-1.5 flex items-end justify-between'>
              <div className={cn(
                'text-[11px] font-medium',
                metric.delta.includes('+') ? 'text-emerald-600' : 'text-rose-500'
              )}>{metric.delta}</div>
              <div className='font-mono text-[10px] tracking-wider text-indigo-400'>{metric.sparkline}</div>
            </div>
          </div>
        ))}
      </div>
      <div className='mt-3 flex items-center gap-1 text-[11px] text-slate-400'>
        数据更新于 2025-05-19 10:18:32
        <span className='inline-flex h-4 w-4 items-center justify-center rounded-full border border-slate-300 text-[9px]'>i</span>
      </div>
    </Panel>
  );
}

/* --- PLACEHOLDER_AGENTS --- */

function AgentsPanel({ agents }: { agents: AgentItem[] }) {
  return (
    <Panel className='p-5'>
      <div className='mb-4 flex items-center justify-between'>
        <h2 className='text-base font-semibold text-slate-900'>Agent 状态</h2>
        <Badge tone='success'>全部在线 8/8</Badge>
      </div>

      <div className='overflow-hidden rounded-xl border border-slate-200/80'>
        <div className='grid grid-cols-[1.3fr_0.8fr_0.8fr_0.7fr] bg-slate-50 px-3 py-2 text-[11px] font-semibold text-slate-500'>
          <span>角色</span>
          <span>状态</span>
          <span>成功率</span>
          <span>今日任务</span>
        </div>
        {agents.map((agent) => (
          <div key={agent.name} className='grid grid-cols-[1.3fr_0.8fr_0.8fr_0.7fr] items-center border-t border-slate-100 px-3 py-2 text-xs text-slate-700'>
            <span className='font-medium text-slate-900'>{agent.name}</span>
            <span className='inline-flex items-center gap-1.5'>
              <span className={cn(
                'h-2 w-2 rounded-full',
                agent.status === '在线' ? 'bg-emerald-500' : agent.status === '繁忙' ? 'bg-amber-500' : 'bg-slate-300'
              )} />
              {agent.status}
            </span>
            <span>{agent.successRate}</span>
            <span>{agent.todayTasks}</span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

/* --- PLACEHOLDER_ARTIFACTS --- */

function ArtifactsPanel({ artifacts, scores }: { artifacts: ArtifactItem[]; scores: ArtifactScore[] }) {
  return (
    <Panel className='p-5'>
      <div className='mb-4 flex items-center justify-between'>
        <h2 className='text-base font-semibold text-slate-900'>产物预览</h2>
        <button type='button' className='flex items-center gap-1 text-sm font-medium text-indigo-600 hover:text-indigo-800'>
          全部产物 <ArrowRight className='h-3.5 w-3.5' />
        </button>
      </div>

      <div className='flex gap-4'>
        <div className='flex flex-1 items-center gap-2'>
          <button type='button' className='flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 hover:bg-slate-50'>
            <ChevronLeft className='h-4 w-4' />
          </button>
          <div className='grid flex-1 grid-cols-4 gap-2'>
            {artifacts.map((artifact) => (
              <div key={artifact.title} className='overflow-hidden rounded-xl border border-slate-200/80'>
                <div className={cn(
                  'relative flex h-20 items-center justify-center bg-gradient-to-br',
                  artifact.gradient,
                  artifact.title === 'Manim 动画' ? 'text-white' : 'text-slate-700'
                )}>
                  {artifact.title === 'Manim 动画' ? (
                    <div className='flex h-10 w-10 items-center justify-center rounded-full border border-white/30 bg-white/15'>
                      <Play className='h-5 w-5' />
                    </div>
                  ) : (
                    <Sparkles className='h-5 w-5 text-indigo-400' />
                  )}
                </div>
                <div className='bg-white px-2 py-2'>
                  <div className='flex items-center justify-between'>
                    <span className='text-xs font-medium text-slate-900'>{artifact.title}</span>
                    <span className='text-[10px] text-slate-400'>{artifact.version}</span>
                  </div>
                  <div className='mt-0.5 text-[10px] text-slate-400'>{artifact.updatedAt}</div>
                </div>
              </div>
            ))}
          </div>
          <button type='button' className='flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 hover:bg-slate-50'>
            <ChevronRight className='h-4 w-4' />
          </button>
        </div>

        <div className='w-36 shrink-0 rounded-xl border border-slate-200/80 bg-slate-50/70 p-3'>
          {scores.map((score, i) => (
            <div key={score.label} className={cn('flex items-center justify-between', i > 0 && 'mt-1.5')}>
              <span className={cn('text-[11px]', i === 0 ? 'font-semibold text-slate-900' : 'text-slate-500')}>
                {score.label}
              </span>
              <span className={cn('text-[11px] font-semibold', i === 0 ? 'text-indigo-600' : 'text-slate-700')}>
                {i === 0 ? `${score.value}/100` : score.value}
              </span>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

/* --- PLACEHOLDER_CAPABILITY --- */

function CapabilityPanel({ capabilities }: { capabilities: string[] }) {
  return (
    <Panel className='p-5'>
      <div className='mb-4 flex items-center gap-2'>
        <Zap className='h-4 w-4 text-indigo-500' />
        <h2 className='text-base font-semibold text-slate-900'>控制台核心能力</h2>
      </div>
      <div className='space-y-2'>
        {capabilities.map((capability) => (
          <div key={capability} className='flex items-center gap-2.5 rounded-lg px-1 py-1'>
            <span className='flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-indigo-600'>
              <Check className='h-3 w-3' />
            </span>
            <span className='text-sm text-slate-700'>{capability}</span>
          </div>
        ))}
      </div>
      <button type='button' className='mt-4 flex items-center gap-1 text-sm font-medium text-indigo-600 hover:text-indigo-800'>
        查看路线图 <ArrowRight className='h-3.5 w-3.5' />
      </button>
    </Panel>
  );
}

function WorkflowStrip({ workflow }: { workflow: WorkflowStep[] }) {
  return (
    <Panel className='px-5 py-4'>
      <div className='flex items-center gap-2'>
        {workflow.map((step, i) => (
          <div key={step.index} className='flex items-center'>
            <div className='flex items-center gap-2 rounded-xl border border-slate-200/80 bg-slate-50/70 px-3 py-2.5'>
              <span className='flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-[11px] font-semibold text-indigo-600'>
                {step.index}
              </span>
              <div>
                <div className='text-xs font-semibold text-slate-900'>{step.title}</div>
                <div className='text-[10px] text-slate-400'>{step.detail}</div>
              </div>
            </div>
            {i < workflow.length - 1 && (
              <ArrowRight className='mx-1 h-3.5 w-3.5 shrink-0 text-slate-300' />
            )}
          </div>
        ))}
        <div className='ml-2 flex items-center gap-3 rounded-xl border border-indigo-200/80 bg-gradient-to-br from-indigo-50 via-white to-violet-50 px-4 py-3'>
          <div className='flex h-9 w-9 items-center justify-center rounded-full bg-indigo-500 text-white'>
            <Check className='h-4 w-4' />
          </div>
          <div>
            <div className='text-sm font-semibold text-slate-900'>闭环完成</div>
            <div className='text-[10px] text-slate-500'>可追溯、可复用、可迭代</div>
          </div>
        </div>
      </div>
    </Panel>
  );
}
