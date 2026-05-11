import { FileText, Tag, Users } from 'lucide-react';

const API_BASE = process.env.MANIMIND_API_BASE_URL || 'http://127.0.0.1:8000';
const PROJECT_ID = 'cauchy-backward-induction-real';

const DOC_ROLE_LABELS: Record<string, string> = {
  raw_material: '原始资料',
  focus_points: '重点侧重',
  arrangement_guide: '编排建议',
  reference: '参考资料',
  style_example: '风格示例',
};

async function fetchInputs() {
  try {
    const res = await fetch(`${API_BASE}/api/projects/${PROJECT_ID}/inputs`, {
      cache: 'no-store',
    });
    if (!res.ok) return { documents: [], files_on_disk: [] };
    return await res.json();
  } catch {
    return { documents: [], files_on_disk: [] };
  }
}

export default async function InputsPage() {
  const data = await fetchInputs();
  const documents = data.documents || [];
  const filesOnDisk = data.files_on_disk || [];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">输入文档</h1>
        <p className="mt-1 text-sm text-slate-400">
          管理项目的输入文档，由 leader 决定各角色的文档分发
        </p>
      </div>

      {documents.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-white/10 py-16 text-slate-400">
          <FileText className="h-10 w-10" />
          <p className="mt-3 text-sm">暂无输入文档</p>
          <p className="mt-1 text-xs text-slate-500">
            前往"新建"页面上传文档，或通过 manifest 配置 documents 字段
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {documents.map((doc: any, idx: number) => (
            <div
              key={idx}
              className="rounded-2xl border border-white/10 bg-white/5 p-5 backdrop-blur"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <FileText className="h-5 w-5 text-indigo-400" />
                  <div>
                    <div className="font-medium text-white">
                      {doc.title || doc.path.split('/').pop()}
                    </div>
                    <div className="mt-0.5 text-xs text-slate-400">{doc.path}</div>
                  </div>
                </div>
                <span className="rounded-lg bg-indigo-600/20 px-2.5 py-1 text-xs font-medium text-indigo-300">
                  {DOC_ROLE_LABELS[doc.role] || doc.role}
                </span>
              </div>

              {doc.consumer_roles && doc.consumer_roles.length > 0 && (
                <div className="mt-3 flex items-center gap-2">
                  <Users className="h-3.5 w-3.5 text-slate-400" />
                  <span className="text-xs text-slate-400">消费角色：</span>
                  <div className="flex gap-1.5">
                    {doc.consumer_roles.map((role: string) => (
                      <span
                        key={role}
                        className="rounded-md bg-white/10 px-2 py-0.5 text-xs text-slate-300"
                      >
                        {role}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {doc.notes && (
                <div className="mt-2 flex items-start gap-2">
                  <Tag className="mt-0.5 h-3.5 w-3.5 text-slate-400" />
                  <span className="text-xs text-slate-400">{doc.notes}</span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {filesOnDisk.length > 0 && (
        <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
          <h3 className="text-sm font-semibold text-slate-300">磁盘文件</h3>
          <div className="mt-3 flex flex-wrap gap-2">
            {filesOnDisk.map((f: string) => (
              <span key={f} className="rounded-lg bg-white/10 px-3 py-1.5 text-xs text-slate-300">
                {f}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
