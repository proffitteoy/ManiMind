'use client';

import { Panel } from '@/components/ui/panel';

export default function LiveError({
  error,
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className='flex min-h-screen items-center justify-center bg-[linear-gradient(180deg,#eef4ff_0%,#f7f9fc_42%,#f4f7fb_100%)] px-4'>
      <Panel className='max-w-md p-8 text-center'>
        <h2 className='text-xl font-semibold text-slate-900'>加载失败</h2>
        <p className='mt-3 text-sm text-slate-600'>
          {error.message || '无法连接到后端 API，请确认服务已启动。'}
        </p>
        <button
          type='button'
          onClick={reset}
          className='mt-5 rounded-xl border border-indigo-500 bg-indigo-500 px-5 py-2 text-sm font-medium text-white'
        >
          重试
        </button>
      </Panel>
    </div>
  );
}
