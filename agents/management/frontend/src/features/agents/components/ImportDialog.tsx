/**
 * Agent 导入对话框。
 *
 * 流式导入请求从 tokenStorage 读取最新 access token，避免 refresh 后沿用旧 token。
 */

import { useState, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription, DialogFooter, Button,
} from '@/shared/components/ui';
import { Upload, FileUp, Check, AlertTriangle, Loader2, XCircle } from 'lucide-react';
import { API_CONFIG } from '@/shared/config/api';
import { getAccessToken } from '@/features/auth/tokenStorage';

interface ImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type ImportEvent =
  | { event: 'start'; total: number }
  | { event: 'success'; username: string; id: number; social_platform_user_id: number | null }
  | { event: 'exists'; username: string; id: number; social_platform_user_id: number | null }
  | { event: 'error'; username: string; message: string }
  | { event: 'done'; total: number; success: number; exists: number; failed: number };

type ImportResult = {
  type: 'success' | 'exists' | 'error';
  username: string;
  id?: number;
  social_platform_user_id?: number | null;
  message?: string;
};

export function ImportDialog({ open, onOpenChange }: ImportDialogProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragDepthRef = useRef(0);
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState('');
  const [importing, setImporting] = useState(false);
  const [results, setResults] = useState<ImportResult[]>([]);
  const [summary, setSummary] = useState<{ total: number; success: number; exists: number; failed: number } | null>(null);
  const queryClient = useQueryClient();

  const selectFile = (selectedFile: File | undefined) => {
    if (!selectedFile) return;

    setResults([]);
    setSummary(null);

    if (!selectedFile.name.endsWith('.zip')) {
      setFile(null);
      setError('仅支持 .zip 格式文件');
      return;
    }

    setFile(selectedFile);
    setError('');
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    selectFile(event.target.files?.[0]);
    event.target.value = '';
  };

  const handleDragEnter = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    if (!event.dataTransfer.types.includes('Files')) return;

    dragDepthRef.current += 1;
    setIsDragging(true);
  };

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    if (event.dataTransfer.types.includes('Files')) {
      event.dataTransfer.dropEffect = 'copy';
    }
  };

  const handleDragLeave = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
    if (dragDepthRef.current === 0) {
      setIsDragging(false);
    }
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    dragDepthRef.current = 0;
    setIsDragging(false);
    selectFile(event.dataTransfer.files[0]);
  };

  const parseSSE = (text: string): ImportEvent | null => {
    const lines = text.trim().split('\n');
    let eventType = '';
    let data = '';

    for (const line of lines) {
      if (line.startsWith('event:')) {
        eventType = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        data = line.slice(5).trim();
      }
    }

    if (!eventType || !data) return null;

    try {
      const parsed = JSON.parse(data);
      return { event: eventType, ...parsed } as ImportEvent;
    } catch {
      return null;
    }
  };

  const getErrorMessage = (err: unknown) =>
    err instanceof Error ? err.message : '导入失败，请重试';

  const handleImport = async () => {
    if (!file) return;

    setImporting(true);
    setError('');
    setResults([]);
    setSummary(null);

    const formData = new FormData();
    formData.append('file', file);

    const token = getAccessToken();
    const apiUrl = API_CONFIG.BASE_URL;

    try {
      const response = await fetch(`${apiUrl}/agents/import-stream`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => null);
        throw new Error(errData?.detail || `HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('无法读取响应流');

      const decoder = new TextDecoder();
      let buffer = '';

      let isReading = true;
      while (isReading) {
        const { done, value } = await reader.read();
        if (done) {
          isReading = false;
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const part of parts) {
          if (!part.trim()) continue;
          const event = parseSSE(part);
          if (!event) continue;

          if (event.event === 'start') {
            // Import started
          } else if (event.event === 'success' || event.event === 'exists' || event.event === 'error') {
            const result: ImportResult = {
              type: event.event,
              username: event.username,
              id: 'id' in event ? event.id : undefined,
              social_platform_user_id: 'social_platform_user_id' in event ? event.social_platform_user_id : undefined,
              message: 'message' in event ? event.message : undefined,
            };
            setResults((prev) => [...prev, result]);
          } else if (event.event === 'done') {
            setSummary({
              total: event.total,
              success: event.success,
              exists: event.exists,
              failed: event.failed,
            });
            queryClient.invalidateQueries({ queryKey: ['agents'] });
          }
        }
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setImporting(false);
    }
  };

  const handleClose = () => {
    if (!importing) {
      dragDepthRef.current = 0;
      setFile(null);
      setIsDragging(false);
      setResults([]);
      setSummary(null);
      setError('');
      onOpenChange(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>批量导入角色</DialogTitle>
          <DialogDescription>
            上传包含 ai_users_config.json 和 avatar 目录的 zip 压缩包
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {!importing && !summary && (
            <>
              <div
                className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                  isDragging
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:border-primary/50'
                }`}
                onClick={() => fileInputRef.current?.click()}
                onDragEnter={handleDragEnter}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".zip"
                  className="hidden"
                  onChange={handleFileChange}
                />
                {isDragging ? (
                  <div className="text-primary">
                    <Upload size={32} className="mx-auto mb-2" />
                    <p className="text-sm">松开以上传 zip 文件</p>
                  </div>
                ) : file ? (
                  <div className="flex items-center justify-center gap-2 text-green-600 dark:text-green-400">
                    <Check size={20} />
                    <span className="font-medium">{file.name}</span>
                  </div>
                ) : (
                  <div className="text-muted-foreground">
                    <Upload size={32} className="mx-auto mb-2" />
                    <p className="text-sm">点击选择或拖拽 zip 文件到此处</p>
                  </div>
                )}
              </div>
            </>
          )}

          {importing && results.length > 0 && (
            <div className="space-y-2 max-h-[300px] overflow-y-auto">
              {results.map((r, i) => (
                <div key={i} className="flex items-center gap-2 text-sm py-1">
                  {r.type === 'success' && (
                    <>
                      <Check size={14} className="text-green-500 shrink-0" />
                      <span className="font-medium text-green-600 dark:text-green-400">
                        {r.username}
                      </span>
                      <span className="text-muted-foreground">注册成功</span>
                    </>
                  )}
                  {r.type === 'exists' && (
                    <>
                      <AlertTriangle size={14} className="text-yellow-500 shrink-0" />
                      <span className="font-medium text-yellow-600 dark:text-yellow-400">
                        {r.username}
                      </span>
                      <span className="text-muted-foreground">已存在</span>
                    </>
                  )}
                  {r.type === 'error' && (
                    <>
                      <XCircle size={14} className="text-red-500 shrink-0" />
                      <span className="font-medium text-red-600 dark:text-red-400">
                        {r.username}
                      </span>
                      <span className="text-muted-foreground">{r.message}</span>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}

          {summary && (
            <div className="space-y-3">
              <div className="bg-muted rounded-lg p-4 space-y-2">
                <div className="flex justify-between text-sm">
                  <span>总计</span>
                  <span className="font-medium">{summary.total}</span>
                </div>
                <div className="flex justify-between text-sm text-green-600 dark:text-green-400">
                  <span>注册成功</span>
                  <span className="font-medium">{summary.success}</span>
                </div>
                <div className="flex justify-between text-sm text-yellow-600 dark:text-yellow-400">
                  <span>已存在</span>
                  <span className="font-medium">{summary.exists}</span>
                </div>
                {summary.failed > 0 && (
                  <div className="flex justify-between text-sm text-destructive">
                    <span>失败</span>
                    <span className="font-medium">{summary.failed}</span>
                  </div>
                )}
              </div>

              {results.length > 0 && (
                <div className="space-y-2 max-h-[200px] overflow-y-auto">
                  {results.map((r, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm py-1">
                      {r.type === 'success' && (
                        <>
                          <Check size={14} className="text-green-500 shrink-0" />
                          <span className="font-medium text-green-600 dark:text-green-400">
                            {r.username}
                          </span>
                          <span className="text-muted-foreground">注册成功</span>
                        </>
                      )}
                      {r.type === 'exists' && (
                        <>
                          <AlertTriangle size={14} className="text-yellow-500 shrink-0" />
                          <span className="font-medium text-yellow-600 dark:text-yellow-400">
                            {r.username}
                          </span>
                          <span className="text-muted-foreground">已存在</span>
                        </>
                      )}
                      {r.type === 'error' && (
                        <>
                          <XCircle size={14} className="text-red-500 shrink-0" />
                          <span className="font-medium text-red-600 dark:text-red-400">
                            {r.username}
                          </span>
                          <span className="text-muted-foreground">{r.message}</span>
                        </>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 text-sm text-destructive">
              <AlertTriangle size={14} />
              {error}
            </div>
          )}
        </div>

        <DialogFooter>
          {!importing && (
            <Button variant="outline" onClick={handleClose}>
              关闭
            </Button>
          )}
          {!importing && !summary && (
            <Button onClick={handleImport} disabled={!file}>
              <FileUp size={16} className="mr-1" /> 导入
            </Button>
          )}
          {importing && (
            <Button disabled>
              <Loader2 size={16} className="mr-1 animate-spin" /> 导入中...
            </Button>
          )}
          {summary && (
            <Button onClick={handleClose}>
              完成
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
