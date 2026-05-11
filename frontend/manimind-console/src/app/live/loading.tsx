import { Panel } from '@/components/ui/panel';

export default function LiveLoading() {
  return (
    <div className='min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(99,102,241,0.16),transparent_22%),radial-gradient(circle_at_top_right,rgba(56,189,248,0.12),transparent_24%),linear-gradient(180deg,#eef4ff_0%,#f7f9fc_42%,#f4f7fb_100%)] px-4 py-6 text-slate-900 sm:px-6 lg:px-8'>
      <div className='mx-auto flex w-full max-w-[1400px] flex-col gap-5'>
        <Panel className='p-6'>
          <div className='h-8 w-64 animate-pulse rounded-lg bg-slate-200' />
          <div className='mt-3 h-4 w-48 animate-pulse rounded bg-slate-100' />
        </Panel>
        <div className='grid gap-5 xl:grid-cols-3'>
          <Panel className='h-48 xl:col-span-2'>
            <div className='h-full animate-pulse rounded-xl bg-slate-100' />
          </Panel>
          <Panel className='h-48'>
            <div className='h-full animate-pulse rounded-xl bg-slate-100' />
          </Panel>
        </div>
        <div className='grid gap-5 xl:grid-cols-2'>
          <Panel className='h-40'>
            <div className='h-full animate-pulse rounded-xl bg-slate-100' />
          </Panel>
          <Panel className='h-40'>
            <div className='h-full animate-pulse rounded-xl bg-slate-100' />
          </Panel>
        </div>
      </div>
    </div>
  );
}
