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

// --- API Response Types ---

export type RuntimeState = {
  project_id: string;
  current_stage: string;
  stages: string[];
  updated_at: string;
};

export type ApiExecutionTask = {
  id: string;
  subject: string;
  owner_role: string;
  active_form: string;
  stage: string;
  status: 'pending' | 'in_progress' | 'completed';
  blocked_reason: string | null;
  blocked_at: string | null;
  last_progress: string | null;
  last_progress_at: string | null;
  blocked_by: string[];
  blocks: string[];
  required_outputs: string[];
  verification_required: boolean;
};

export type ApiContextRecord = {
  key: string;
  scope: string;
  summary: string;
  writer_role: string;
  consumer_roles: string[];
  lifecycle: string;
  invalidation_rule: string;
  source_ids: string[];
  sticky: boolean;
};

export type ApiAgentProfile = {
  id: string;
  mode: string;
  responsibility: string;
  allowed_stages: string[];
  required_inputs: string[];
  owned_outputs: string[];
  output_contract: string;
};

export type ApiSegment = {
  id: string;
  title: string;
  goal: string;
  modality: string;
  estimated_seconds: number;
};

export type ApiProjectPlan = {
  project_id: string;
  title: string;
  stages: string[];
  segments: ApiSegment[];
  agent_profiles: ApiAgentProfile[];
  current_stage: string;
};

export type ApiEvent = {
  event: string;
  project_id: string;
  session_id: string;
  timestamp: string;
  role_id?: string;
  task_id?: string;
  payload?: Record<string, unknown>;
  from_stage?: string;
  to_stage?: string;
};

export type RuntimeResponse = {
  project_id: string;
  state: RuntimeState | null;
  execution_tasks: { execution_tasks: ApiExecutionTask[]; updated_at: string } | null;
  context_records: { contexts: ApiContextRecord[]; updated_at: string } | null;
  project_plan: { plan: ApiProjectPlan; updated_at: string } | null;
};

export type EventsResponse = {
  project_id: string;
  project_events: ApiEvent[];
  session_events?: ApiEvent[];
};

// --- Pipeline Stage Canonical Order ---

const STAGE_ORDER = [
  'ingest', 'summarize', 'plan', 'dispatch',
  'review', 'post_produce', 'package', 'done'
];

const STAGE_LABELS: Record<string, string> = {
  ingest: '素材导入',
  summarize: '内容摘要',
  plan: '计划生成',
  dispatch: '任务分发',
  review: '审核关卡',
  post_produce: '后期制作',
  package: '打包交付',
  done: '完成'
};

// --- Transform Functions ---

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`;
  } catch {
    return iso;
  }
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  } catch {
    return iso;
  }
}

export function transformStages(
  state: RuntimeState | null,
  events: ApiEvent[]
): StageItem[] {
  const stages = state?.stages ?? STAGE_ORDER;
  const currentStage = state?.current_stage ?? 'prestart';
  const currentIdx = stages.indexOf(currentStage);

  const stageTimestamps = new Map<string, string>();
  for (const ev of events) {
    if (ev.event === 'stage.changed' && ev.to_stage) {
      stageTimestamps.set(ev.to_stage, ev.timestamp);
    }
  }

  return stages
    .filter((s) => s !== 'prestart' && s !== 'blocked')
    .map((stage, idx) => {
      const stageIdx = stages.indexOf(stage);
      let status: 'done' | 'active' | 'waiting';
      let summary: string;
      if (stageIdx < currentIdx) {
        status = 'done';
        summary = '已完成';
      } else if (stageIdx === currentIdx) {
        status = 'active';
        summary = '进行中';
      } else {
        status = 'waiting';
        summary = '等待中';
      }
      const ts = stageTimestamps.get(stage);
      const at = ts ? formatDate(ts) : status === 'waiting' ? '待触发' : (state?.updated_at ? formatDate(state.updated_at) : '-');
      return {
        key: STAGE_LABELS[stage] ?? stage.toUpperCase(),
        title: STAGE_LABELS[stage] ?? stage.toUpperCase(),
        at,
        status,
        summary
      };
    });
}

export function transformTaskColumns(tasks: ApiExecutionTask[]): TaskColumn[] {
  const pending = tasks.filter((t) => t.status === 'pending');
  const inProgress = tasks.filter((t) => t.status === 'in_progress');
  const completed = tasks.filter((t) => t.status === 'completed');

  function ownerAbbrev(role: string): string {
    const parts = role.split('_');
    return parts.map((p) => p[0]?.toUpperCase() ?? '').join('').slice(0, 2);
  }

  return [
    {
      title: '待处理',
      status: 'pending' as const,
      count: pending.length,
      footer: '新建任务',
      tasks: pending.slice(0, 6).map((t) => ({
        title: t.subject,
        stage: STAGE_LABELS[t.stage] ?? t.stage,
        owner: ownerAbbrev(t.owner_role)
      }))
    },
    {
      title: '进行中',
      status: 'in_progress' as const,
      count: inProgress.length,
      footer: '新建任务',
      tasks: inProgress.slice(0, 6).map((t) => ({
        title: t.subject,
        stage: STAGE_LABELS[t.stage] ?? t.stage,
        owner: ownerAbbrev(t.owner_role)
      }))
    },
    {
      title: '已完成',
      status: 'completed' as const,
      count: completed.length,
      footer: '查看全部',
      tasks: completed.slice(0, 6).map((t) => ({
        title: t.subject,
        stage: STAGE_LABELS[t.stage] ?? t.stage
      }))
    }
  ];
}

export function transformRuntimeAssets(
  runtime: RuntimeResponse | null
): RuntimeAsset[] {
  const stateTime = runtime?.state?.updated_at;
  const tasksTime = runtime?.execution_tasks?.updated_at;
  const planTime = runtime?.project_plan?.updated_at;
  const ctxTime = runtime?.context_records?.updated_at;

  function stateLabel(data: unknown): string {
    return data ? '已同步' : '未加载';
  }

  return [
    { title: '项目状态', state: stateLabel(runtime?.state), updatedAt: stateTime ? formatTime(stateTime) : '-' },
    { title: '项目计划', state: runtime?.project_plan ? '最新' : '未加载', updatedAt: planTime ? formatTime(planTime) : '-' },
    { title: '执行任务', state: stateLabel(runtime?.execution_tasks), updatedAt: tasksTime ? formatTime(tasksTime) : '-' },
    { title: '上下文记录', state: runtime?.context_records ? '已落盘' : '未加载', updatedAt: ctxTime ? formatTime(ctxTime) : '-' }
  ];
}

export function transformContextItems(contexts: ApiContextRecord[]): ContextItem[] {
  const iconMap: [RegExp, ContextItem['icon']][] = [
    [/goal|target|objective/i, 'target'],
    [/audience|user|style/i, 'users'],
    [/formula|math|equation/i, 'formula'],
    [/constraint|limit|rule/i, 'constraint']
  ];

  function pickIcon(key: string): ContextItem['icon'] {
    for (const [re, icon] of iconMap) {
      if (re.test(key)) return icon;
    }
    return 'book';
  }

  return contexts.slice(0, 5).map((c) => ({
    title: c.key.replace(/_/g, ' '),
    summary: c.summary.length > 30 ? c.summary.slice(0, 30) + '...' : c.summary,
    icon: pickIcon(c.key)
  }));
}

export function transformEvents(events: ApiEvent[]): EventItem[] {
  const toneMap: Record<string, EventItem['tone']> = {
    'worker.blocker': 'critical',
    'review.return': 'critical',
    'stage.changed': 'warning',
    'leader.commit': 'warning',
    'worker.result': 'success',
    'review.decision': 'success',
    'plan_snapshot': 'success',
    'dispatch.context_pack': 'info',
    'worker.progress': 'info',
    'review.draft': 'info'
  };

  return events.slice(-6).reverse().map((ev) => {
    let detail = '';
    if (ev.role_id) detail += `[${ev.role_id}] `;
    if (ev.task_id) detail += `task:${ev.task_id} `;
    if (ev.event === 'stage.changed' && ev.from_stage && ev.to_stage) {
      detail += `${ev.from_stage} → ${ev.to_stage}`;
    } else if (ev.payload) {
      const keys = Object.keys(ev.payload).slice(0, 2);
      detail += keys.map((k) => `${k}:${String(ev.payload![k]).slice(0, 20)}`).join(', ');
    }
    return {
      at: formatTime(ev.timestamp),
      type: ev.event,
      detail: detail || ev.event,
      tone: toneMap[ev.event] ?? 'info'
    };
  });
}

export function transformMetrics(tasks: ApiExecutionTask[]): MetricItem[] {
  const total = tasks.length;
  const completed = tasks.filter((t) => t.status === 'completed').length;
  const blocked = tasks.filter((t) => t.blocked_reason).length;
  const active = tasks.filter((t) => t.status === 'in_progress').length;
  const rate = total > 0 ? Math.round((completed / total) * 100) : 0;

  return [
    { title: '任务总数', value: String(total), delta: `活跃 ${active}`, sparkline: '▁▂▃▅▆▅▇' },
    { title: '完成率', value: `${rate}%`, delta: `已完成 ${completed}`, sparkline: '▂▂▃▄▅▅▇' },
    { title: '阻塞数', value: String(blocked), delta: blocked > 0 ? '需关注' : '无阻塞', sparkline: '▃▂▂▃▄▆▇' },
    { title: '待处理', value: String(total - completed - active), delta: `进行中 ${active}`, sparkline: '▃▄▅▄▆▇▆' }
  ];
}

export function transformAgents(
  profiles: ApiAgentProfile[],
  tasks: ApiExecutionTask[]
): AgentItem[] {
  if (profiles.length === 0) return [];

  return profiles.map((p) => {
    const owned = tasks.filter((t) => t.owner_role === p.id);
    const completedCount = owned.filter((t) => t.status === 'completed').length;
    const inProgressCount = owned.filter((t) => t.status === 'in_progress').length;

    let status: AgentItem['status'];
    if (inProgressCount > 0) {
      status = '繁忙';
    } else if (owned.length > 0 && completedCount === owned.length) {
      status = '待命';
    } else {
      status = '在线';
    }

    const successRate = owned.length > 0
      ? `${Math.round((completedCount / owned.length) * 100)}%`
      : '-';

    const name = p.id
      .split('_')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');

    return { name, status, successRate, todayTasks: owned.length };
  });
}

const ARTIFACT_GRADIENTS = [
  'from-sky-100 via-white to-indigo-100',
  'from-orange-100 via-white to-rose-100',
  'from-slate-900 via-slate-950 to-indigo-950',
  'from-emerald-100 via-white to-teal-100'
];

export function transformArtifacts(segments: ApiSegment[]): ArtifactItem[] {
  if (segments.length === 0) return [];
  return segments.slice(0, 4).map((seg, i) => ({
    title: seg.title,
    version: 'v0.1',
    caption: seg.goal.length > 20 ? seg.goal.slice(0, 20) + '...' : seg.goal,
    gradient: ARTIFACT_GRADIENTS[i % ARTIFACT_GRADIENTS.length],
    updatedAt: '-'
  }));
}

export function transformArtifactScores(tasks: ApiExecutionTask[]): ArtifactScore[] {
  const total = tasks.length;
  const completed = tasks.filter((t) => t.status === 'completed').length;
  const score = total > 0 ? Math.round((completed / total) * 100) : 0;
  return [
    { label: '完成度', value: score },
    { label: '总任务', value: total },
    { label: '已完成', value: completed },
    { label: '进行中', value: tasks.filter((t) => t.status === 'in_progress').length },
    { label: '待处理', value: tasks.filter((t) => t.status === 'pending').length },
    { label: '阻塞', value: tasks.filter((t) => t.blocked_reason).length }
  ];
}

export function transformWorkflow(stages: string[]): WorkflowStep[] {
  const detailMap: Record<string, string> = {
    ingest: '导入素材',
    summarize: '内容摘要',
    plan: '生成计划',
    dispatch: '任务分发',
    review: '审核关卡',
    post_produce: '后期制作',
    package: '打包交付',
    done: '完成'
  };

  return stages
    .filter((s) => s !== 'prestart' && s !== 'blocked')
    .map((stage, idx) => ({
      index: idx + 1,
      title: STAGE_LABELS[stage] ?? stage.toUpperCase(),
      detail: detailMap[stage] ?? stage
    }));
}

const CAPABILITIES: string[] = [
  '导入 manifest / PDF / 笔记',
  '查看阶段流',
  '查看任务 DAG',
  '生成上下文包',
  '手动推进任务',
  '预览产物与审核结果'
];

// --- Main Aggregator ---

export type DashboardProps = {
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

export function transformApiToDashboardProps(
  runtime: RuntimeResponse | null,
  eventsResp: EventsResponse | null
): DashboardProps {
  const tasks = runtime?.execution_tasks?.execution_tasks ?? [];
  const contexts = runtime?.context_records?.contexts ?? [];
  const profiles = runtime?.project_plan?.plan?.agent_profiles ?? [];
  const segments = runtime?.project_plan?.plan?.segments ?? [];
  const allEvents = eventsResp?.session_events ?? eventsResp?.project_events ?? [];
  const stateStages = runtime?.state?.stages ?? STAGE_ORDER;

  return {
    stages: transformStages(runtime?.state ?? null, allEvents),
    taskColumns: transformTaskColumns(tasks),
    runtimeAssets: transformRuntimeAssets(runtime),
    contextItems: transformContextItems(contexts),
    events: transformEvents(allEvents),
    metrics: transformMetrics(tasks),
    agents: transformAgents(profiles, tasks),
    artifacts: transformArtifacts(segments),
    artifactScores: transformArtifactScores(tasks),
    capabilities: CAPABILITIES,
    workflow: transformWorkflow(stateStages)
  };
}
