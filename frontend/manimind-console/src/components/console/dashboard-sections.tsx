import { Badge } from '@/components/ui/badge';
import { Panel } from '@/components/ui/panel';
import type {
  AgentItem,
  ArtifactItem,
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
  Check,
  Clock3,
  FileStack,
  Flag,
  Play,
  Sparkles,
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
  capabilities: string[];
  workflow: WorkflowStep[];
};

const stageStyles = {
  done: {
    wrapper: 'border-emerald-200/80 bg-emerald-50/80',
    icon: 'bg-emerald-500 text-white',
    label: 'text-emerald-700'
  },
  active: {
    wrapper: 'border-indigo-200/90 bg-indigo-50/85 shadow-[0_0_0_1px_rgba(99,102,241,0.1)]',
    icon: 'bg-indigo-500 text-white ring-8 ring-indigo-100/80',
    label: 'text-indigo-700'
  },
  waiting: {
    wrapper: 'border-slate-200/90 bg-slate-50/70',
    icon: 'bg-slate-100 text-slate-500',
    label: 'text-slate-500'
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

export function DashboardSections({
  stages,
  taskColumns,
  runtimeAssets,
  contextItems,
  events,
  metrics,
  agents,
  artifacts,
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
        <ArtifactsPanel artifacts={artifacts} />
        <CapabilityPanel capabilities={capabilities} />
      </div>

      <WorkflowStrip workflow={workflow} />
    </>
  );
}

function PipelineRail({ stages }: { stages: StageItem[] }) {
  return (
    <Panel className='p-4 sm:p-5'>
      <div className='grid gap-3 sm:grid-cols-4 xl:grid-cols-8'>
        {stages.map((stage, index) => {
          const style = stageStyles[stage.status];
          const Icon = stage.status === 'done' ? Check : stage.status === 'active' ? Play : Clock3;

          return (
            <div key={stage.key} className='relative'>
              <div
                className={cn(
                  'min-h-[96px] rounded-[22px] border px-4 py-3 transition-transform duration-300 hover:-translate-y-1',
                  style.wrapper
                )}
              >
                <div className={cn('mb-2.5 flex h-9 w-9 items-center justify-center rounded-full', style.icon)}>
                  <Icon className='h-4 w-4' />
                </div>
                <div className='space-y-1'>
                  <div className='text-[0.72rem] font-semibold tracking-[0.22em] text-slate-400'>
                    {stage.title}
                  </div>
                  <div className='text-sm text-slate-500'>{stage.at}</div>
                  <div className={cn('text-sm font-semibold', style.label)}>{stage.summary}</div>
                </div>
              </div>
              {index < stages.length - 1 ? (
                <ArrowRight className='pointer-events-none absolute -right-2 top-1/2 z-10 h-4 w-4 -translate-y-1/2 text-indigo-300' />
              ) : null}
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function TaskBoard({ taskColumns }: { taskColumns: TaskColumn[] }) {
  return (
    <Panel className='p-5'>
      <div className='mb-4 flex items-center justify-between'>
        <div>
          <div className='text-xs font-semibold tracking-[0.22em] text-indigo-500 uppercase'>A 任务看板</div>
          <h2 className='mt-1 text-lg font-semibold text-slate-900'>按状态驱动的执行队列</h2>
        </div>
        <Badge tone='active'>Dispatch</Badge>
      </div>

      <div className='grid gap-4 xl:grid-cols-3'>
        {taskColumns.map((column) => (
          <div key={column.title} className='rounded-[22px] border border-slate-200/80 bg-slate-50/70 p-4'>
            <div className='mb-4 flex items-center justify-between'>
              <span className='text-sm font-semibold text-slate-900'>{column.title}</span>
              <span
                className={cn(
                  'rounded-full px-2.5 py-1 text-xs font-semibold',
                  columnStyles[column.status]
                )}
              >
                {column.count}
              </span>
            </div>
            <div className='space-y-3'>
              {column.tasks.map((task) => (
                <div
                  key={task.title}
                  className='rounded-[18px] border border-white bg-white px-3 py-3 shadow-[0_10px_25px_rgba(15,23,42,0.04)]'
                >
                  <div className='flex items-start justify-between gap-3'>
                    <div>
                      <div className='text-sm font-medium text-slate-900'>{task.title}</div>
                      <div className='mt-2 text-xs font-semibold tracking-[0.18em] text-indigo-500 uppercase'>
                        {task.stage}
                      </div>
                    </div>
                    {task.owner ? (
                      <div className='flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-600'>
                        {task.owner}
                      </div>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
            <button
              type='button'
              className='mt-4 text-sm font-medium text-indigo-600 transition hover:text-indigo-800'
            >
              + {column.footer}
            </button>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function RuntimePanel({ runtimeAssets }: { runtimeAssets: RuntimeAsset[] }) {
  return (
    <Panel>
      <PanelHeader eyebrow='B 项目 Runtime' title='Runtime 驱动的单一事实源' />
      <div className='space-y-3'>
        {runtimeAssets.map((asset) => (
          <div
            key={asset.title}
            className='rounded-[20px] border border-slate-200/80 bg-slate-50/70 px-4 py-3'
          >
            <div className='flex items-center justify-between gap-3'>
              <div className='flex items-center gap-3'>
                <div className='flex h-10 w-10 items-center justify-center rounded-2xl bg-indigo-100 text-indigo-600'>
                  <FileStack className='h-4 w-4' />
                </div>
                <div>
                  <div className='text-sm font-medium text-slate-900'>{asset.title}</div>
                  <div className='text-xs text-slate-500'>{asset.updatedAt}</div>
                </div>
              </div>
              <Badge tone={asset.state === '最新' ? 'active' : 'success'}>{asset.state}</Badge>
            </div>
          </div>
        ))}
      </div>
      <button type='button' className='mt-4 text-sm font-medium text-indigo-600 hover:text-indigo-800'>
        打开 Runtime 目录
      </button>
    </Panel>
  );
}

function ContextPanel({ contextItems }: { contextItems: ContextItem[] }) {
  return (
    <Panel>
      <PanelHeader eyebrow='C Context Packet' title='给 Worker 的显式输入快照' />
      <div className='space-y-4'>
        {contextItems.map((item) => (
          <div key={item.title} className='rounded-[20px] border border-slate-200/70 bg-white px-4 py-3'>
            <div className='text-sm font-medium text-slate-900'>{item.title}</div>
            <div className='mt-1 text-sm leading-6 text-slate-500'>{item.summary}</div>
          </div>
        ))}
      </div>
      <button type='button' className='mt-4 text-sm font-medium text-indigo-600 hover:text-indigo-800'>
        查看详情
      </button>
    </Panel>
  );
}

function EventPanel({ events }: { events: EventItem[] }) {
  return (
    <Panel>
      <PanelHeader eyebrow='D 事件日志' title='所有推进都可追溯到 events.jsonl' />
      <div className='space-y-4'>
        {events.map((event) => (
          <div key={`${event.at}-${event.type}`} className='flex gap-3'>
            <div className='flex flex-col items-center'>
              <span className={cn('mt-2 h-3 w-3 rounded-full', eventStyles[event.tone])} />
              <span className='mt-2 h-full min-h-8 w-px bg-slate-200 last:hidden' />
            </div>
            <div className='pb-2'>
              <div className='text-sm text-slate-500'>{event.at}</div>
              <div className='mt-1 text-sm font-semibold text-slate-900'>{event.type}</div>
              <div className='mt-1 text-sm leading-6 text-slate-500'>{event.detail}</div>
            </div>
          </div>
        ))}
      </div>
      <button type='button' className='mt-2 text-sm font-medium text-indigo-600 hover:text-indigo-800'>
        查看完整日志
      </button>
    </Panel>
  );
}

function MetricsPanel({ metrics }: { metrics: MetricItem[] }) {
  return (
    <Panel>
      <PanelHeader eyebrow='系统概览' title='编排进展快照' />
      <div className='grid gap-4 sm:grid-cols-2'>
        {metrics.map((metric) => (
          <div key={metric.title} className='rounded-[22px] border border-slate-200/80 bg-slate-50/70 p-4'>
            <div className='text-sm text-slate-500'>{metric.title}</div>
            <div className='mt-3 text-3xl font-semibold text-slate-900'>{metric.value}</div>
            <div className='mt-2 flex items-end justify-between gap-3'>
              <div className='text-xs font-medium text-emerald-600'>{metric.delta}</div>
              <div className='font-mono text-xs tracking-[0.2em] text-indigo-400'>{metric.sparkline}</div>
            </div>
          </div>
        ))}
      </div>
      <div className='mt-4 text-sm text-slate-500'>数据更新时间 2025-05-19 10:18:32</div>
    </Panel>
  );
}

function AgentsPanel({ agents }: { agents: AgentItem[] }) {
  return (
    <Panel>
      <div className='mb-4 flex items-start justify-between gap-3'>
        <div>
          <div className='text-xs font-semibold tracking-[0.22em] text-indigo-500 uppercase'>Agent 状态</div>
          <h2 className='mt-1 text-lg font-semibold text-slate-900'>角色在线与今日任务</h2>
        </div>
        <Badge tone='success'>全部在线 8/8</Badge>
      </div>

      <div className='overflow-hidden rounded-[22px] border border-slate-200/80'>
        <div className='grid grid-cols-[1.3fr_0.8fr_0.8fr_0.7fr] bg-slate-50 px-4 py-3 text-xs font-semibold tracking-[0.18em] text-slate-500 uppercase'>
          <span>角色</span>
          <span>状态</span>
          <span>成功率</span>
          <span>今日任务</span>
        </div>
        {agents.map((agent) => (
          <div
            key={agent.name}
            className='grid grid-cols-[1.3fr_0.8fr_0.8fr_0.7fr] items-center border-t border-slate-200/70 px-4 py-3 text-sm text-slate-700'
          >
            <span className='font-medium text-slate-900'>{agent.name}</span>
            <span className='inline-flex items-center gap-2'>
              <span
                className={cn(
                  'h-2.5 w-2.5 rounded-full',
                  agent.status === '在线'
                    ? 'bg-emerald-500'
                    : agent.status === '繁忙'
                      ? 'bg-amber-500'
                      : 'bg-slate-300'
                )}
              />
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

function ArtifactsPanel({ artifacts }: { artifacts: ArtifactItem[] }) {
  return (
    <Panel>
      <div className='mb-4 flex items-start justify-between gap-3'>
        <div>
          <div className='text-xs font-semibold tracking-[0.22em] text-indigo-500 uppercase'>产物预览</div>
          <h2 className='mt-1 text-lg font-semibold text-slate-900'>从结构化中间产物到可交付内容</h2>
        </div>
        <button type='button' className='text-sm font-medium text-indigo-600 hover:text-indigo-800'>
          全部产物
        </button>
      </div>

      <div className='grid grid-cols-2 gap-4'>
        {artifacts.map((artifact) => (
          <div
            key={artifact.title}
            className='overflow-hidden rounded-[24px] border border-slate-200/80 bg-white'
          >
            <div
              className={cn(
                'relative h-32 overflow-hidden bg-gradient-to-br p-4',
                artifact.gradient,
                artifact.title === 'Manim 动画' ? 'text-white' : 'text-slate-900'
              )}
            >
              <div className='absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.9),transparent_45%)] opacity-80' />
              {artifact.title === 'Manim 动画' ? (
                <>
                  <div className='absolute left-4 top-4 z-10'>
                    <Badge tone='active'>{artifact.version}</Badge>
                  </div>
                  <div className='relative flex h-full items-center justify-center'>
                    <div className='flex h-[4.5rem] w-[4.5rem] items-center justify-center rounded-full border border-white/25 bg-white/12 backdrop-blur'>
                      <Play className='h-7 w-7' />
                    </div>
                  </div>
                </>
              ) : (
                <div className='relative flex h-full flex-col justify-between'>
                  <Badge tone='neutral'>{artifact.version}</Badge>
                  <div className='flex h-14 w-14 items-center justify-center rounded-[20px] border border-slate-200/70 bg-white/70 text-indigo-500 backdrop-blur'>
                    <Sparkles className='h-5 w-5' />
                  </div>
                </div>
              )}
            </div>
            <div className='p-4'>
              <div className='text-base font-semibold text-slate-900'>{artifact.title}</div>
              <div className='mt-2 text-sm leading-6 text-slate-500'>{artifact.caption}</div>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function CapabilityPanel({ capabilities }: { capabilities: string[] }) {
  return (
    <Panel>
      <PanelHeader eyebrow='控制台 MVP 能力' title='先把闭环验证跑通' />
      <div className='space-y-3'>
        {capabilities.map((capability) => (
          <div key={capability} className='flex items-start gap-3 rounded-[18px] border border-slate-200/80 bg-slate-50/70 px-4 py-3'>
            <span className='mt-0.5 flex h-6 w-6 items-center justify-center rounded-full bg-indigo-100 text-indigo-600'>
              <Zap className='h-3.5 w-3.5' />
            </span>
            <span className='text-sm leading-6 text-slate-700'>{capability}</span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function WorkflowStrip({ workflow }: { workflow: WorkflowStep[] }) {
  return (
    <Panel className='overflow-hidden'>
      <div className='grid gap-3 lg:grid-cols-[repeat(8,minmax(0,1fr))_220px]'>
        {workflow.map((step) => (
          <div
            key={step.index}
            className='rounded-[22px] border border-slate-200/80 bg-slate-50/70 px-4 py-4'
          >
            <div className='mb-3 flex items-center gap-2 text-indigo-500'>
              <span className='flex h-7 w-7 items-center justify-center rounded-full bg-indigo-100 text-xs font-semibold'>
                {step.index}
              </span>
              {step.index < workflow.length ? <ArrowRight className='h-4 w-4 text-indigo-300' /> : null}
            </div>
            <div className='text-sm font-semibold text-slate-900'>{step.title}</div>
            <div className='mt-1 text-xs leading-5 text-slate-500'>{step.detail}</div>
          </div>
        ))}
        <div className='rounded-[24px] border border-indigo-200/80 bg-gradient-to-br from-indigo-50 via-white to-violet-50 px-5 py-5'>
          <div className='flex h-full flex-col justify-between'>
            <div className='flex h-12 w-12 items-center justify-center rounded-full bg-indigo-500 text-white shadow-[0_12px_30px_rgba(99,102,241,0.22)]'>
              <Flag className='h-5 w-5' />
            </div>
            <div>
              <div className='text-lg font-semibold text-slate-900'>闭环完成</div>
              <div className='mt-2 text-sm leading-6 text-slate-500'>可追溯、可复用、可迭代</div>
            </div>
          </div>
        </div>
      </div>
    </Panel>
  );
}

function PanelHeader({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <div className='mb-4'>
      <div className='text-xs font-semibold tracking-[0.22em] text-indigo-500 uppercase'>{eyebrow}</div>
      <h2 className='mt-1 text-lg font-semibold text-slate-900'>{title}</h2>
    </div>
  );
}
