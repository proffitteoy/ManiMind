'use client';

import { useState } from 'react';
import { Expand, FileCode, Film, Image, X } from 'lucide-react';

type ArtifactItem = {
  task_id: string;
  worker_role: string;
  segment_id: string;
  summary: string;
  artifact_files: string[];
  metadata: { title?: string; worker?: string };
};

const WORKER_COLORS: Record<string, string> = {
  html_worker: 'bg-blue-600/20 text-blue-300',
  manim_worker: 'bg-purple-600/20 text-purple-300',
  svg_worker: 'bg-emerald-600/20 text-emerald-300',
};

function getFileType(filename: string): 'html' | 'video' | 'svg' | 'audio' | 'other' {
  const lower = filename.toLowerCase();
  if (lower.endsWith('.html') || lower.endsWith('.htm')) return 'html';
  if (lower.endsWith('.mp4') || lower.endsWith('.webm') || lower.endsWith('.mov')) return 'video';
  if (lower.endsWith('.svg')) return 'svg';
  if (lower.endsWith('.wav') || lower.endsWith('.mp3') || lower.endsWith('.m4a')) return 'audio';
  return 'other';
}

function getPreviewUrl(file: string, projectId: string): string {
  const match = file.match(new RegExp(`outputs[/\\\\]${projectId}[/\\\\](.+)`));
  if (match) return `/outputs/${projectId}/${match[1].replace(/\\/g, '/')}`;
  return `/outputs/${file.replace(/\\/g, '/')}`;
}

export function ArtifactCard({ item, projectId }: { item: ArtifactItem; projectId: string }) {
  const [preview, setPreview] = useState<string | null>(null);
  const [previewType, setPreviewType] = useState<'html' | 'video' | 'svg' | 'audio' | 'other'>('other');

  function openPreview(file: string) {
    setPreviewType(getFileType(file));
    setPreview(getPreviewUrl(file, projectId));
  }

  return (
    <>
      <div className="rounded-2xl border border-white/10 bg-white/5 p-5 backdrop-blur">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white">
              {item.metadata.title ?? item.segment_id}
            </h3>
            <p className="mt-1 text-xs text-slate-400">{item.summary}</p>
          </div>
          <span className={`rounded-lg px-2.5 py-1 text-xs font-medium ${WORKER_COLORS[item.worker_role] || 'bg-white/10 text-slate-300'}`}>
            {item.metadata.worker ?? item.worker_role}
          </span>
        </div>

        <div className="mt-3 space-y-1.5">
          {item.artifact_files.map((f) => {
            const filename = f.split(/[/\\]/).pop() ?? f;
            const type = getFileType(filename);
            const Icon = type === 'html' ? FileCode : type === 'video' ? Film : type === 'svg' ? Image : FileCode;

            return (
              <button
                key={f}
                onClick={() => openPreview(f)}
                className="flex w-full items-center gap-2 rounded-xl bg-white/5 px-3 py-2 text-left transition hover:bg-white/10"
              >
                <Icon className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                <span className="flex-1 truncate text-xs text-slate-300">{filename}</span>
                <Expand className="h-3 w-3 text-slate-500" />
              </button>
            );
          })}
        </div>
      </div>

      {preview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
          <div className="relative h-[85vh] w-[90vw] max-w-6xl overflow-hidden rounded-2xl border border-white/10 bg-slate-900">
            <div className="flex items-center justify-between border-b border-white/10 px-5 py-3">
              <span className="text-sm font-medium text-white">预览</span>
              <button onClick={() => setPreview(null)} className="text-slate-400 hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="h-[calc(100%-52px)] w-full">
              {previewType === 'html' && (
                <iframe src={preview} className="h-full w-full border-0 bg-white" sandbox="allow-scripts" />
              )}
              {previewType === 'video' && (
                <div className="flex h-full items-center justify-center bg-black p-4">
                  <video src={preview} controls className="max-h-full max-w-full rounded-lg" />
                </div>
              )}
              {previewType === 'svg' && (
                <iframe src={preview} className="h-full w-full border-0 bg-white" />
              )}
              {previewType === 'audio' && (
                <div className="flex h-full items-center justify-center">
                  <audio src={preview} controls className="w-96" />
                </div>
              )}
              {previewType === 'other' && (
                <div className="flex h-full items-center justify-center text-slate-400">
                  <p>不支持预览此文件类型</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
