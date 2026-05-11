import { CheckCircle2, Puzzle, XCircle } from 'lucide-react';

const API_BASE = process.env.MANIMIND_API_BASE_URL || 'http://127.0.0.1:8000';

type Capability = {
  name: string;
  path: string;
  roles: string[];
  stages: string[];
  purpose: string;
  summary: string;
  available: boolean;
};

async function fetchCapabilities(): Promise<{ capabilities: Capability[]; total: number; available: number }> {
  try {
    const res = await fetch(`${API_BASE}/api/capabilities`, { cache: 'no-store' });
    if (!res.ok) return { capabilities: [], total: 0, available: 0 };
    return await res.json();
  } catch {
    return { capabilities: [], total: 0, available: 0 };
  }
}

export default async function CapabilitiesPage() {
  const data = await fetchCapabilities();
  const { capabilities, total, available } = data;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">能力注册表</h1>
        <p className="mt-1 text-sm text-slate-400">
          已注册的第三方资源和 skills，按角色/阶段分发给各 Agent
        </p>
      </div>

      <div className="flex gap-4">
        <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-3">
          <span className="text-xs text-slate-400">总计</span>
          <div className="text-lg font-bold text-white">{total}</div>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-3">
          <span className="text-xs text-slate-400">可用</span>
          <div className="text-lg font-bold text-emerald-400">{available}</div>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-3">
          <span className="text-xs text-slate-400">缺失</span>
          <div className="text-lg font-bold text-red-400">{total - available}</div>
        </div>
      </div>

      <div className="space-y-4">
        {capabilities.map((cap) => (
          <div
            key={cap.name}
            className="rounded-2xl border border-white/10 bg-white/5 p-5 backdrop-blur"
          >
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <Puzzle className="h-5 w-5 text-indigo-400" />
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-white">{cap.name}</span>
                    {cap.available ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-400" />
                    )}
                  </div>
                  <div className="mt-0.5 text-xs text-slate-400">{cap.purpose}</div>
                </div>
              </div>
              <span className="rounded-lg bg-white/10 px-2.5 py-1 text-xs font-mono text-slate-300">
                {cap.path}
              </span>
            </div>

            <p className="mt-3 text-sm leading-relaxed text-slate-300">{cap.summary}</p>

            <div className="mt-4 flex flex-wrap gap-4">
              <div>
                <span className="text-xs text-slate-500">适用角色</span>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {cap.roles.map((role) => (
                    <span
                      key={role}
                      className="rounded-md bg-indigo-600/20 px-2 py-0.5 text-xs text-indigo-300"
                    >
                      {role}
                    </span>
                  ))}
                </div>
              </div>
              <div>
                <span className="text-xs text-slate-500">适用阶段</span>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {cap.stages.map((stage) => (
                    <span
                      key={stage}
                      className="rounded-md bg-purple-600/20 px-2 py-0.5 text-xs text-purple-300"
                    >
                      {stage}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {capabilities.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-white/10 py-16 text-slate-400">
          <Puzzle className="h-10 w-10" />
          <p className="mt-3 text-sm">无法连接到 API 或暂无已注册能力</p>
        </div>
      )}
    </div>
  );
}
