export type NavItem = {
  title: string;
  icon:
    | 'overview'
    | 'projects'
    | 'tasks'
    | 'contexts'
    | 'runtime'
    | 'artifacts'
    | 'review'
    | 'settings';
  active?: boolean;
};

export type ActionItem = {
  title: string;
  icon: 'plan' | 'context' | 'refresh' | 'more';
  tone?: 'primary' | 'secondary';
};

export type StageItem = {
  key: string;
  title: string;
  at: string;
  status: 'done' | 'active' | 'waiting';
  summary: string;
};

export type TaskCard = {
  title: string;
  stage: string;
  owner?: string;
};

export type TaskColumn = {
  title: string;
  status: 'pending' | 'in_progress' | 'completed';
  count: number;
  tasks: TaskCard[];
  footer: string;
};

export type RuntimeAsset = {
  title: string;
  state: string;
  updatedAt: string;
};

export type ContextItem = {
  title: string;
  summary: string;
};

export type EventItem = {
  at: string;
  type: string;
  detail: string;
  tone: 'success' | 'warning' | 'info' | 'critical';
};

export type MetricItem = {
  title: string;
  value: string;
  delta: string;
  sparkline: string;
};

export type AgentItem = {
  name: string;
  status: '在线' | '繁忙' | '待命';
  successRate: string;
  todayTasks: number;
};

export type ArtifactItem = {
  title: string;
  version: string;
  caption: string;
  gradient: string;
};

export type WorkflowStep = {
  index: number;
  title: string;
  detail: string;
};

export const consoleDemo = {
  project: {
    title: '项目：数学科普自动化项目',
    subtitle: '从输入到交付的闭环控制，Runtime 驱动的单一事实源',
    status: '运行中',
    statusDetail: '当前阶段：DISPATCH'
  },
  navigation: [
    { title: '总览', icon: 'overview', active: true },
    { title: '项目', icon: 'projects' },
    { title: '任务', icon: 'tasks' },
    { title: '上下文', icon: 'contexts' },
    { title: 'Runtime', icon: 'runtime' },
    { title: '产物', icon: 'artifacts' },
    { title: '审核', icon: 'review' },
    { title: '设置', icon: 'settings' }
  ] satisfies NavItem[],
  quickActions: [
    { title: '生成 Project Plan', icon: 'plan', tone: 'secondary' },
    { title: '生成 Context Packet', icon: 'context', tone: 'secondary' },
    { title: '更新任务状态', icon: 'refresh', tone: 'primary' },
    { title: '更多', icon: 'more', tone: 'secondary' }
  ] satisfies ActionItem[],
  stages: [
    { key: 'INGEST', title: 'INGEST', at: '05-19 10:02', status: 'done', summary: '已完成' },
    {
      key: 'SUMMARIZE',
      title: 'SUMMARIZE',
      at: '05-19 10:07',
      status: 'done',
      summary: '已完成'
    },
    { key: 'PLAN', title: 'PLAN', at: '05-19 10:12', status: 'done', summary: '已完成' },
    {
      key: 'DISPATCH',
      title: 'DISPATCH',
      at: '05-19 10:16',
      status: 'active',
      summary: '进行中'
    },
    { key: 'REVIEW', title: 'REVIEW', at: '待触发', status: 'waiting', summary: '等待中' },
    {
      key: 'POST_PRODUCE',
      title: 'POST_PRODUCE',
      at: '待触发',
      status: 'waiting',
      summary: '等待中'
    },
    {
      key: 'PACKAGE',
      title: 'PACKAGE',
      at: '待触发',
      status: 'waiting',
      summary: '等待中'
    },
    { key: 'DONE', title: 'DONE', at: '待触发', status: 'waiting', summary: '等待中' }
  ] satisfies StageItem[],
  taskColumns: [
    {
      title: 'pending',
      status: 'pending',
      count: 3,
      footer: '新建任务',
      tasks: [
        { title: '解析论文 PDF', stage: 'INGEST' },
        { title: '提取公式与定理', stage: 'SUMMARIZE' },
        { title: '生成研究总结', stage: 'SUMMARIZE' }
      ]
    },
    {
      title: 'in_progress',
      status: 'in_progress',
      count: 3,
      footer: '新建任务',
      tasks: [
        { title: '撰写讲解脚本', stage: 'DISPATCH', owner: 'MW' },
        { title: '生成分镜草稿', stage: 'DISPATCH', owner: 'HW' },
        { title: '审核输出结果', stage: 'REVIEW', owner: 'RV' }
      ]
    },
    {
      title: 'completed',
      status: 'completed',
      count: 2,
      footer: '查看全部',
      tasks: [
        { title: '生成研究问题清单', stage: 'PLAN' },
        { title: '构建 Content Packet', stage: 'PLAN' }
      ]
    }
  ] satisfies TaskColumn[],
  runtimeAssets: [
    { title: 'state.json', state: '已同步', updatedAt: '10:18:32' },
    { title: 'project-plan.json', state: '最新', updatedAt: '10:18:12' },
    { title: 'execution-tasks.json', state: '已同步', updatedAt: '10:18:32' },
    { title: 'context-records.json', state: '已落盘', updatedAt: '10:17:58' }
  ] satisfies RuntimeAsset[],
  contextItems: [
    { title: '项目目标', summary: '生成高质量数学科普动画' },
    { title: '受众与风格', summary: '中学生，严谨易懂，视觉统一' },
    { title: '关键公式', summary: 'Euler 公式、泰勒展开、级数收敛' },
    { title: '参考资料', summary: '8 篇论文，5 本教材，12 个网页片段' }
  ] satisfies ContextItem[],
  events: [
    {
      at: '10:18:32',
      type: 'artifact.saved',
      detail: '分镜草稿 v0.2 已保存',
      tone: 'info'
    },
    {
      at: '10:17:55',
      type: 'review.blocked',
      detail: '脚本存在术语未定义问题',
      tone: 'critical'
    },
    {
      at: '10:17:20',
      type: 'task.updated',
      detail: '任务状态更新为 in_progress',
      tone: 'warning'
    },
    {
      at: '10:16:45',
      type: 'context_packet.generated',
      detail: 'Context Packet v1.3 已生成',
      tone: 'success'
    },
    {
      at: '10:16:12',
      type: 'plan.created',
      detail: 'Project Plan v1.0 已创建',
      tone: 'success'
    }
  ] satisfies EventItem[],
  metrics: [
    { title: '任务总数', value: '18', delta: '环比 +12%', sparkline: '▁▂▃▅▆▅▇' },
    { title: '完成率', value: '61%', delta: '较昨日 +8%', sparkline: '▂▂▃▄▅▅▇' },
    { title: '平均耗时', value: '12m 43s', delta: '较昨日 -9%', sparkline: '▃▂▂▃▄▆▇' },
    { title: '成功率', value: '96.3%', delta: '较昨日 +2.1%', sparkline: '▃▄▅▄▆▇▆' }
  ] satisfies MetricItem[],
  agents: [
    { name: 'Lead', status: '在线', successRate: '98%', todayTasks: 2 },
    { name: 'Explorer', status: '在线', successRate: '97%', todayTasks: 3 },
    { name: 'Planner', status: '在线', successRate: '99%', todayTasks: 2 },
    { name: 'Coordinator', status: '在线', successRate: '97%', todayTasks: 4 },
    { name: 'HTML Worker', status: '繁忙', successRate: '96%', todayTasks: 3 },
    { name: 'Manim Worker', status: '在线', successRate: '95%', todayTasks: 4 },
    { name: 'SVG Worker', status: '待命', successRate: '98%', todayTasks: 2 },
    { name: 'Reviewer', status: '在线', successRate: '96%', todayTasks: 3 }
  ] satisfies AgentItem[],
  artifacts: [
    {
      title: '讲解脚本',
      version: 'v0.3',
      caption: '用于串联公式、叙事与口播节奏',
      gradient: 'from-sky-100 via-white to-indigo-100'
    },
    {
      title: '分镜',
      version: 'v0.2',
      caption: '镜头节奏、字幕节拍、说明层级',
      gradient: 'from-orange-100 via-white to-rose-100'
    },
    {
      title: 'Manim 动画',
      version: 'v0.1',
      caption: '基础图元与公式演化预览',
      gradient: 'from-slate-900 via-slate-950 to-indigo-950'
    },
    {
      title: '审核报告',
      version: 'v0.1',
      caption: '术语一致性与事实核查',
      gradient: 'from-emerald-100 via-white to-teal-100'
    }
  ] satisfies ArtifactItem[],
  capabilities: [
    '导入 manifest / PDF / 笔记',
    '查看阶段流',
    '查看任务 DAG',
    '生成 context packet',
    '手动推进任务',
    '预览产物与审核结果'
  ],
  workflow: [
    { index: 1, title: '导入素材', detail: 'manifest / PDF / 笔记' },
    { index: 2, title: '生成计划', detail: 'Project Plan' },
    { index: 3, title: '组装上下文', detail: 'Context Packet' },
    { index: 4, title: '任务分发', detail: 'Agent Dispatch' },
    { index: 5, title: '状态更新', detail: 'Runtime 唯一事实源' },
    { index: 6, title: '审核关卡', detail: 'Review Gate' },
    { index: 7, title: '产物预览', detail: 'Artifact Preview' },
    { index: 8, title: '打包交付', detail: 'Package Delivery' }
  ] satisfies WorkflowStep[]
};
