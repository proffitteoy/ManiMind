import { cn } from '@/lib/utils';
import type { HTMLAttributes } from 'react';

export function Panel({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return (
    <section
      className={cn(
        'rounded-[24px] border border-white/70 bg-white/88 p-5 shadow-[0_25px_60px_rgba(99,102,241,0.08)] backdrop-blur-xl',
        className
      )}
      {...props}
    />
  );
}
