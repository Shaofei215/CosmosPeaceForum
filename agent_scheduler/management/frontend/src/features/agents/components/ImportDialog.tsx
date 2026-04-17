import { useState, useRef } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { agentApi } from '@/shared/api/modules';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription, DialogFooter, Button,
} from '@/shared/components/ui';
import { Upload, FileUp, Check, AlertTriangle } from 'lucide-react';

interface ImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ImportDialog({ open, onOpenChange }: ImportDialogProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState('');
  const queryClient = useQueryClient();

  const importMutation = useMutation({
    mutationFn: (f: File) => agentApi.importAgents(f),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      setFile(null);
      setError('');
      onOpenChange(false);
    },
    onError: (err: { message?: string }) => {
      setError(err.message || '导入失败，请检查文件格式');
    },
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) {
      if (!f.name.endsWith('.zip')) {
        setError('仅支持 .zip 格式文件');
        return;
      }
      setFile(f);
      setError('');
    }
  };

  const handleImport = () => {
    if (file) {
      importMutation.mutate(file);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>批量导入 Agent</DialogTitle>
          <DialogDescription>
            上传包含 ai_users_config.json 和 avatar 目录的 zip 压缩包
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div
            className="border-2 border-dashed border-border rounded-lg p-8 text-center cursor-pointer hover:border-primary/50 transition-colors"
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".zip"
              className="hidden"
              onChange={handleFileChange}
            />
            {file ? (
              <div className="flex items-center justify-center gap-2 text-green-600">
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

          {error && (
            <div className="flex items-center gap-2 text-sm text-destructive">
              <AlertTriangle size={14} />
              {error}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button onClick={handleImport} disabled={!file || importMutation.isPending}>
            {importMutation.isPending ? '导入中...' : (
              <>
                <FileUp size={16} className="mr-1" /> 导入
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
