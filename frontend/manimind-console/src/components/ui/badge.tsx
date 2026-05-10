import { cn } from '@/lib/utils';
import type { ReactNode } from 'react';

type BadgeProps = {
  children: ReactNode;
  className?: string;
  tone?: 'neutral' | 'success' | 'active';
};

const toneMap: Record<NonNullable<BadgeProps['tone']>, string> = {
  neutral: 'bg-slate-100 text-slate-700',
  success: 'bg-emerald-100 text-emerald-700',
  active: 'bg-indigo-100 text-indigo-700'
};

export function Badge({ children, className, tone = 'neutral' }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold tracking-[0.18em] uppercase',
        toneMap[tone],
        className
      )}
    >
      {children}
    </span>
  );
}
