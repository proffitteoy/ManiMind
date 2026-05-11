import { Panel } from '@/components/ui/panel';
import { Badge } from '@/components/ui/badge';

export const dynamic = 'force-dynamic';

const API_BASE =
  process.env.NEXT_PUBLIC_MANIMIND_API_BASE_URL ??
  process.env.MANIMIND_API_BASE_URL ??
  'http://127.0.0.1:8000';

const PROJECT_ID = 'max-function-review-demo';

type EvidenceResponse = {
  evidence: {
    render_evidence: {
      task_id: string;
      worker_role: string;
      segment_id: string;
      summary: string;
      artifact_files: string[];
      metadata: { title?: string; worker?: string };
    }[];
  } | null;
};

export default async function ArtifactsPage() {
  let evidence: EvidenceResponse['evidence'] = null;
  try {
    const res = await fetch(`${API_BASE}/api/projects/${PROJECT_ID}/review-evidence`, { cache: 'no-store' });
    if (res.ok) {
      const data: EvidenceResponse = await res.json();
      evidence = data.evidence;
    }
  } catch {}

  const items = evidence?.render_evidence ?? [];

  return (
    <>
      <header className='rounded-[24px] border border-white/75 bg-white/90 px-5 py-4 backdrop-blur-xl sm:px-7'>
        <h1 className='text-2xl font-semibold text-slate-950'>产物浏览</h1>
        <p className='mt-1 text-sm text-slate-500'>所有渲染产物，共 {items.length} 项</p>
      </header>

      {items.length === 0 ? (
        <Panel className='p-8 text-center'>
          <p className='text-slate-500'>暂无渲染产物。请先执行流水线。</p>
        </Panel>
      ) : (
        <div className='grid gap-5 md:grid-cols-2 xl:grid-cols-3'>
          {items.map((item) => (
            <Panel key={item.task_id} className='p-5'>
              <div className='flex items-start justify-between'>
                <div>
                  <h3 className='text-sm font-semibold text-slate-900'>
                    {item.metadata.title ?? item.segment_id}
                  </h3>
                  <p className='mt-1 text-xs text-slate-500'>{item.summary}</p>
                </div>
                <Badge tone={item.worker_role === 'html_worker' ? 'active' : 'neutral'}>
                  {item.metadata.worker ?? item.worker_role}
                </Badge>
              </div>
              <div className='mt-3 space-y-1'>
                {item.artifact_files.map((f) => {
                  const filename = f.split(/[/\\]/).pop() ?? f;
                  return (
                    <div key={f} className='truncate rounded-lg bg-slate-50 px-2 py-1 text-xs text-slate-600'>
                      {filename}
                    </div>
                  );
                })}
              </div>
            </Panel>
          ))}
        </div>
      )}
    </>
  );
}
