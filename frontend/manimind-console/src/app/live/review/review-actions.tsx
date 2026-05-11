'use client';

import { useState } from 'react';

type ReviewActionsProps = {
  apiBaseUrl: string;
  manifestPath: string;
  sessionId: string;
};

type ActionState = {
  loading: boolean;
  message: string;
};

const defaultReturnRoles = 'coordinator,reviewer,html_worker,manim_worker,svg_worker';

export function ReviewActions({ apiBaseUrl, manifestPath, sessionId }: ReviewActionsProps) {
  const [reason, setReason] = useState('请补齐数学定义一致性并收敛镜头节奏。');
  const [mustFix, setMustFix] = useState('修复术语不一致；补全关键公式解释。');
  const [promptPatch, setPromptPatch] = useState(
    '下一轮生成请先统一术语，再按”问题-直觉-公式-结论”的结构输出。'
  );
  const [targetRoles, setTargetRoles] = useState(defaultReturnRoles);
  const [state, setState] = useState<ActionState>({ loading: false, message: '' });

  async function postJson(path: string, payload: unknown) {
    const response = await fetch(`${apiBaseUrl}${path}`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body?.detail ?? `请求失败：${response.status}`);
    }
    return body;
  }

  async function execute(
    actionName: string,
    path: string,
    payload: Record<string, unknown>
  ) {
    setState({ loading: true, message: `${actionName} 请求中...` });
    try {
      await postJson(path, payload);
      setState({ loading: false, message: `${actionName} 成功，页面即将刷新。` });
      setTimeout(() => window.location.reload(), 500);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setState({ loading: false, message: `${actionName} 失败：${message}` });
    }
  }

  return (
    <section className='rounded-[24px] border border-white/70 bg-white/88 p-5 shadow-[0_25px_60px_rgba(99,102,241,0.08)] backdrop-blur-xl'>
      <h2 className='text-lg font-semibold text-slate-900'>执行与人工审核</h2>
      <p className='mt-2 text-sm text-slate-500'>
        先执行流水线到审核关卡，再做人工通过或退回。
      </p>

      <div className='mt-4 grid gap-3 sm:grid-cols-4'>
        <button
          type='button'
          disabled={state.loading}
          className='rounded-xl border border-indigo-500 bg-indigo-500 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60'
          onClick={() =>
            execute('执行到审核', '/api/projects/run-to-review', {
              manifest_path: manifestPath,
              session_id: sessionId
            })
          }
        >
          执行到审核
        </button>
        <button
          type='button'
          disabled={state.loading}
          className='rounded-xl border border-emerald-500 bg-emerald-500 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60'
          onClick={() =>
            execute('通过', '/api/projects/review/decision', {
              manifest_path: manifestPath,
              session_id: sessionId,
              decision: 'approve',
              reason
            })
          }
        >
          通过
        </button>
        <button
          type='button'
          disabled={state.loading}
          className='rounded-xl border border-amber-500 bg-amber-500 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60'
          onClick={() =>
            execute('退回', '/api/projects/review/decision', {
              manifest_path: manifestPath,
              session_id: sessionId,
              decision: 'return',
              reason,
              must_fix: mustFix,
              prompt_patch: promptPatch,
              target_roles: targetRoles
                .split(',')
                .map((item) => item.trim())
                .filter(Boolean)
            })
          }
        >
          退回
        </button>
        <button
          type='button'
          disabled={state.loading}
          className='rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:opacity-60'
          onClick={() =>
            execute('终稿打包', '/api/projects/finalize', {
              manifest_path: manifestPath,
              session_id: sessionId,
              tts_provider: 'powershell_sapi'
            })
          }
        >
          终稿打包
        </button>
      </div>

      <div className='mt-4 grid gap-3'>
        <label className='grid gap-1 text-sm text-slate-600'>
          审核原因
          <input
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            className='rounded-xl border border-slate-300 px-3 py-2 text-sm'
          />
        </label>
        <label className='grid gap-1 text-sm text-slate-600'>
          必须修复项
          <input
            value={mustFix}
            onChange={(event) => setMustFix(event.target.value)}
            className='rounded-xl border border-slate-300 px-3 py-2 text-sm'
          />
        </label>
        <label className='grid gap-1 text-sm text-slate-600'>
          提示词补丁
          <textarea
            value={promptPatch}
            onChange={(event) => setPromptPatch(event.target.value)}
            rows={3}
            className='rounded-xl border border-slate-300 px-3 py-2 text-sm'
          />
        </label>
        <label className='grid gap-1 text-sm text-slate-600'>
          目标角色（逗号分隔）
          <input
            value={targetRoles}
            onChange={(event) => setTargetRoles(event.target.value)}
            className='rounded-xl border border-slate-300 px-3 py-2 text-sm'
          />
        </label>
      </div>

      {state.message ? <div className='mt-4 text-sm text-slate-700'>{state.message}</div> : null}
    </section>
  );
}
