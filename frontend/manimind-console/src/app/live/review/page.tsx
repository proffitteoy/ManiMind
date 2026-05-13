import { Panel } from '@/components/ui/panel';
import { Badge } from '@/components/ui/badge';

import { ReviewActions } from './review-actions';

export const dynamic = 'force-dynamic';

const API_BASE =
  process.env.NEXT_PUBLIC_MANIMIND_API_BASE_URL ??
  process.env.MANIMIND_API_BASE_URL ??
  'http://127.0.0.1:8000';

const PROJECT_ID = 'max-function-review-demo';
const SESSION_ID = 'manual-session';
const MANIFEST_PATH = 'configs/max-function-review-demo.json';

type ScriptSegment = {
  segment_id: string;
  title: string;
  goal: string;
  narration: string;
  modality: string;
  formulas: string[];
};

type RenderEvidence = {
  task_id: string;
  worker_role: string;
  segment_id: string;
  summary: string;
  artifact_files: string[];
  metadata: { title?: string; worker?: string; scene_class?: string };
};

type Checkpoint = {
  name: string;
  stage: string;
  required_inputs: string[];
};

type ReviewReturnPayload = {
  reason?: string;
  must_fix?: string;
  timestamp?: string;
};

type ContractSchema = {
  type?: string;
  required?: string[];
  properties?: Record<string, unknown>;
};

type ContractResponse = {
  contracts?: Record<string, ContractSchema | null>;
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

export default async function ReviewPage() {
  const [evidenceResp, scriptResp, returnResp, runtimeResp, contractResp] = await Promise.all([
    fetchJson<{ evidence: { render_evidence: RenderEvidence[]; checkpoints: Checkpoint[] } | null }>(
      `${API_BASE}/api/projects/${PROJECT_ID}/review-evidence`
    ),
    fetchJson<{ script: { script_outline: ScriptSegment[] } | null }>(
      `${API_BASE}/api/projects/${PROJECT_ID}/narration-script`
    ),
    fetchJson<{ payload: ReviewReturnPayload | null }>(
      `${API_BASE}/api/projects/${PROJECT_ID}/review-return?session_id=${SESSION_ID}`
    ),
    fetchJson<{ state?: { current_stage?: string } | null }>(
      `${API_BASE}/api/projects/${PROJECT_ID}/runtime`
    ),
    fetchJson<ContractResponse>(
      `${API_BASE}/api/projects/contracts?roles=planner,coordinator,reviewer`
    ),
  ]);

  const evidence = evidenceResp?.evidence;
  const segments = scriptResp?.script?.script_outline ?? [];
  const checkpoints = evidence?.checkpoints ?? [];
  const renderItems = evidence?.render_evidence ?? [];
  const latestReturn = returnResp?.payload;
  const currentStage = runtimeResp?.state?.current_stage ?? 'unknown';
  const isReviewStage = currentStage === 'review';
  const contracts = contractResp?.contracts ?? {};
  const reviewerRequired = contracts.reviewer?.required ?? [];
  const plannerRequired = contracts.planner?.required ?? [];
  const coordinatorRequired = contracts.coordinator?.required ?? [];

  return (
    <>
      <header className='rounded-[24px] border border-white/75 bg-white/90 px-5 py-4 backdrop-blur-xl sm:px-7'>
        <div className='flex items-center justify-between'>
          <div>
            <h1 className='text-2xl font-semibold text-slate-950'>审核</h1>
            <p className='mt-1 text-sm text-slate-500'>审查各段落的脚本、公式与渲染产物</p>
          </div>
          <Badge tone={isReviewStage ? 'active' : 'neutral'}>
            {isReviewStage ? '等待审核' : currentStage.toUpperCase()}
          </Badge>
        </div>
      </header>

      {checkpoints.length > 0 && (
        <Panel className='p-5'>
          <h2 className='mb-3 text-base font-semibold text-slate-900'>审核检查点</h2>
          <div className='flex flex-wrap gap-2'>
            {checkpoints.map((cp) => (
              <div key={cp.name} className='rounded-xl border border-indigo-200 bg-indigo-50 px-3 py-2'>
                <span className='text-sm font-medium text-indigo-700'>{cp.name}</span>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {(reviewerRequired.length > 0 || plannerRequired.length > 0 || coordinatorRequired.length > 0) && (
        <Panel className='p-5'>
          <h2 className='mb-3 text-base font-semibold text-slate-900'>Schema 字段约束</h2>
          <div className='grid gap-3 md:grid-cols-3'>
            <SchemaFieldCard title='planner' fields={plannerRequired} />
            <SchemaFieldCard title='coordinator' fields={coordinatorRequired} />
            <SchemaFieldCard title='reviewer' fields={reviewerRequired} />
          </div>
        </Panel>
      )}

      {segments.length === 0 && renderItems.length === 0 ? (
        <Panel className='p-8 text-center'>
          <p className='text-slate-500'>暂无审核内容。请先执行流水线到审核阶段。</p>
        </Panel>
      ) : (
        <div className='space-y-5'>
          {segments.map((seg) => {
            const renders = renderItems.filter((r) => r.segment_id === seg.segment_id);
            return (
              <SegmentCard key={seg.segment_id} segment={seg} renders={renders} projectId={PROJECT_ID} />
            );
          })}
        </div>
      )}

      {latestReturn && (
        <Panel className='border-amber-200 bg-amber-50/50 p-5'>
          <h2 className='mb-2 text-base font-semibold text-amber-800'>上次退回记录</h2>
          {latestReturn.reason && <p className='text-sm text-amber-700'>原因：{latestReturn.reason}</p>}
          {latestReturn.must_fix && <p className='mt-1 text-sm text-amber-700'>必须修复：{latestReturn.must_fix}</p>}
        </Panel>
      )}

      <ReviewActions apiBaseUrl={API_BASE} manifestPath={MANIFEST_PATH} sessionId={SESSION_ID} />
    </>
  );
}

function SchemaFieldCard({ title, fields }: { title: string; fields: string[] }) {
  if (fields.length === 0) {
    return (
      <div className='rounded-xl border border-slate-200 bg-slate-50 p-4'>
        <div className='text-sm font-medium text-slate-700'>{title}</div>
        <p className='mt-1 text-xs text-slate-500'>无 required 字段</p>
      </div>
    );
  }
  return (
    <div className='rounded-xl border border-slate-200 bg-slate-50 p-4'>
      <div className='text-sm font-medium text-slate-700'>{title}</div>
      <div className='mt-2 flex flex-wrap gap-1.5'>
        {fields.map((field) => (
          <span key={field} className='rounded-md border border-indigo-200 bg-white px-2 py-0.5 text-xs text-indigo-700'>
            {field}
          </span>
        ))}
      </div>
    </div>
  );
}

function SegmentCard({ segment, renders, projectId }: { segment: ScriptSegment; renders: RenderEvidence[]; projectId: string }) {
  return (
    <Panel className='p-5'>
      <div className='flex items-start justify-between'>
        <div>
          <h3 className='text-lg font-semibold text-slate-900'>{segment.title}</h3>
          <p className='mt-1 text-sm text-slate-600'>{segment.goal}</p>
        </div>
        <Badge tone='neutral'>{segment.modality}</Badge>
      </div>

      <div className='mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4'>
        <div className='text-xs font-semibold text-slate-500'>旁白脚本</div>
        <p className='mt-1 text-sm text-slate-800'>{segment.narration}</p>
      </div>

      {segment.formulas.length > 0 && (
        <div className='mt-3 rounded-xl border border-slate-200 bg-slate-50 p-4'>
          <div className='text-xs font-semibold text-slate-500'>公式</div>
          <div className='mt-2 space-y-1'>
            {segment.formulas.map((f, i) => (
              <code key={i} className='block rounded bg-white px-2 py-1 text-xs text-slate-700'>
                {f}
              </code>
            ))}
          </div>
        </div>
      )}

      {renders.length > 0 && (
        <div className='mt-4 space-y-3'>
          <div className='text-xs font-semibold text-slate-500'>渲染产物</div>
          {renders.map((r) => (
            <RenderPreview key={r.task_id} render={r} projectId={projectId} />
          ))}
        </div>
      )}
    </Panel>
  );
}

function RenderPreview({ render, projectId }: { render: RenderEvidence; projectId: string }) {
  const worker = render.metadata.worker ?? render.worker_role;

  const htmlFile = render.artifact_files.find((f) => f.endsWith('.html'));
  const mp4File = render.artifact_files.find((f) => f.endsWith('.mp4'));
  const svgFile = render.artifact_files.find((f) => f.endsWith('.svg'));

  function toOutputUrl(absPath: string): string {
    const marker = `outputs/${projectId}/`;
    const idx = absPath.replace(/\\/g, '/').indexOf(marker);
    if (idx === -1) return '';
    return '/outputs/' + absPath.replace(/\\/g, '/').slice(idx + 'outputs/'.length);
  }

  return (
    <div className='rounded-xl border border-slate-200 bg-white p-4'>
      <div className='mb-2 flex items-center justify-between'>
        <span className='text-sm font-medium text-slate-700'>{render.summary}</span>
        <Badge tone='neutral'>{worker}</Badge>
      </div>

      {worker === 'html' && htmlFile && (
        <iframe
          src={toOutputUrl(htmlFile)}
          className='h-64 w-full rounded-lg border border-slate-200'
          sandbox='allow-scripts'
          title={render.metadata.title ?? render.segment_id}
        />
      )}

      {worker === 'manim' && mp4File && (
        <video
          src={toOutputUrl(mp4File)}
          controls
          className='h-64 w-full rounded-lg bg-black'
        />
      )}

      {worker === 'svg' && svgFile && (
        <iframe
          src={toOutputUrl(svgFile)}
          className='h-48 w-full rounded-lg border border-slate-200 bg-white'
          title={render.metadata.title ?? render.segment_id}
        />
      )}
    </div>
  );
}
