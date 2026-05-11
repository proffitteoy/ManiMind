import { ArtifactCard } from './artifact-card';

export const dynamic = 'force-dynamic';

const API_BASE =
  process.env.NEXT_PUBLIC_MANIMIND_API_BASE_URL ??
  process.env.MANIMIND_API_BASE_URL ??
  'http://127.0.0.1:8000';

const PROJECT_ID = 'cauchy-backward-induction-real';

type EvidenceItem = {
  task_id: string;
  worker_role: string;
  segment_id: string;
  summary: string;
  artifact_files: string[];
  metadata: { title?: string; worker?: string };
};

type EvidenceResponse = {
  evidence: {
    render_evidence: EvidenceItem[];
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
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">产物浏览</h1>
        <p className="mt-1 text-sm text-slate-400">所有渲染产物，共 {items.length} 项</p>
      </div>

      {items.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-white/10 py-16 text-slate-400">
          <p className="text-sm">暂无渲染产物。请先执行流水线。</p>
        </div>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {items.map((item) => (
            <ArtifactCard key={item.task_id} item={item} projectId={PROJECT_ID} />
          ))}
        </div>
      )}
    </div>
  );
}
