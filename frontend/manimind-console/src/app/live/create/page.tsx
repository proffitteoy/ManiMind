'use client';

import { useState } from 'react';
import { FileText, PlusCircle, Upload, X } from 'lucide-react';

const DOC_ROLES = [
  { value: 'raw_material', label: '原始资料' },
  { value: 'focus_points', label: '重点侧重' },
  { value: 'arrangement_guide', label: '编排建议' },
  { value: 'reference', label: '参考资料' },
  { value: 'style_example', label: '风格示例' },
];

const STYLE_PRESETS = ['3b1b', 'veritasium', 'numberphile', 'mathologer'];

type DocEntry = {
  file: File | null;
  role: string;
  title: string;
  consumer_roles: string;
};

const API_BASE = process.env.NEXT_PUBLIC_MANIMIND_API_BASE_URL || 'http://127.0.0.1:8000';

export default function CreateProjectPage() {
  const [projectId, setProjectId] = useState('');
  const [title, setTitle] = useState('');
  const [audience, setAudience] = useState('数学本科生');
  const [styleRefs, setStyleRefs] = useState<string[]>([]);
  const [documents, setDocuments] = useState<DocEntry[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<any>(null);

  function addDocument() {
    setDocuments([...documents, { file: null, role: 'raw_material', title: '', consumer_roles: '' }]);
  }

  function removeDocument(idx: number) {
    setDocuments(documents.filter((_, i) => i !== idx));
  }

  function updateDocument(idx: number, patch: Partial<DocEntry>) {
    setDocuments(documents.map((d, i) => (i === idx ? { ...d, ...patch } : d)));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!projectId.trim()) return;
    setSubmitting(true);
    setResult(null);

    try {
      for (const doc of documents) {
        if (!doc.file) continue;
        const formData = new FormData();
        formData.append('file', doc.file);
        formData.append('role', doc.role);
        formData.append('title', doc.title || doc.file.name);
        formData.append('consumer_roles', doc.consumer_roles);
        await fetch(`${API_BASE}/api/projects/${projectId}/inputs/upload`, {
          method: 'POST',
          body: formData,
        });
      }

      const res = await fetch(`${API_BASE}/api/projects/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId,
          title,
          audience,
          style_refs: styleRefs,
          segments: [],
        }),
      });
      const data = await res.json();
      setResult(data);
    } catch (err: any) {
      setResult({ error: err.message });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">新建项目</h1>
        <p className="mt-1 text-sm text-slate-400">创建新的数学科普动画项目，上传输入文档</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur">
          <h2 className="text-lg font-semibold text-white">基本信息</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm text-slate-300">项目 ID</label>
              <input
                type="text"
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
                placeholder="cauchy-backward-induction"
                className="mt-1 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-white placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-slate-300">项目标题</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="柯西的反向归纳法"
                className="mt-1 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-white placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-300">目标受众</label>
              <input
                type="text"
                value={audience}
                onChange={(e) => setAudience(e.target.value)}
                className="mt-1 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-white placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-300">风格参考</label>
              <div className="mt-1 flex flex-wrap gap-2">
                {STYLE_PRESETS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() =>
                      setStyleRefs((prev) =>
                        prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]
                      )
                    }
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                      styleRefs.includes(s)
                        ? 'bg-indigo-600 text-white'
                        : 'border border-white/10 bg-white/5 text-slate-300 hover:bg-white/10'
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">输入文档</h2>
            <button
              type="button"
              onClick={addDocument}
              className="flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500"
            >
              <PlusCircle className="h-4 w-4" />
              添加文档
            </button>
          </div>

          {documents.length === 0 && (
            <div className="mt-4 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-white/10 py-12 text-slate-400">
              <Upload className="h-8 w-8" />
              <p className="mt-2 text-sm">点击"添加文档"上传原始资料、重点侧重或编排建议</p>
            </div>
          )}

          <div className="mt-4 space-y-3">
            {documents.map((doc, idx) => (
              <div key={idx} className="flex items-start gap-3 rounded-xl border border-white/10 bg-white/3 p-4">
                <FileText className="mt-1 h-5 w-5 shrink-0 text-slate-400" />
                <div className="flex-1 space-y-2">
                  <input
                    type="file"
                    accept=".pdf,.md,.txt,.markdown,.text"
                    onChange={(e) => updateDocument(idx, { file: e.target.files?.[0] || null })}
                    className="text-sm text-slate-300 file:mr-3 file:rounded-lg file:border-0 file:bg-indigo-600 file:px-3 file:py-1 file:text-sm file:text-white"
                  />
                  <div className="flex gap-2">
                    <select
                      value={doc.role}
                      onChange={(e) => updateDocument(idx, { role: e.target.value })}
                      className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white"
                    >
                      {DOC_ROLES.map((r) => (
                        <option key={r.value} value={r.value} className="bg-slate-800">
                          {r.label}
                        </option>
                      ))}
                    </select>
                    <input
                      type="text"
                      placeholder="标题（可选）"
                      value={doc.title}
                      onChange={(e) => updateDocument(idx, { title: e.target.value })}
                      className="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white placeholder:text-slate-500"
                    />
                  </div>
                  <input
                    type="text"
                    placeholder="消费角色（逗号分隔，如 planner,coordinator）"
                    value={doc.consumer_roles}
                    onChange={(e) => updateDocument(idx, { consumer_roles: e.target.value })}
                    className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white placeholder:text-slate-500"
                  />
                </div>
                <button type="button" onClick={() => removeDocument(idx)} className="text-slate-400 hover:text-red-400">
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting || !projectId.trim()}
          className="w-full rounded-2xl bg-gradient-to-r from-indigo-600 to-purple-600 px-6 py-3 text-base font-semibold text-white shadow-lg transition hover:from-indigo-500 hover:to-purple-500 disabled:opacity-50"
        >
          {submitting ? '创建中...' : '创建项目'}
        </button>
      </form>

      {result && (
        <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
          <h3 className="text-sm font-semibold text-slate-300">创建结果</h3>
          <pre className="mt-2 overflow-auto rounded-xl bg-black/30 p-4 text-xs text-slate-300">
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
