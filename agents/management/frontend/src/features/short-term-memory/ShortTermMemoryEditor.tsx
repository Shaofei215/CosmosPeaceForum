import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';

import { shortTermMemoryApi } from '@/shared/api/modules';
import { Button, Textarea } from '@/shared/components/ui';

interface ShortTermMemoryEditorProps {
  agentId: number;
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'object' && error !== null && 'message' in error) {
    return String((error as { message?: unknown }).message ?? '短期记忆保存失败');
  }
  return '短期记忆保存失败';
}

/** 独立展示并完整覆盖角色当前短期记忆 Markdown 快照。 */
export function ShortTermMemoryEditor({ agentId }: ShortTermMemoryEditorProps) {
  const queryClient = useQueryClient();
  const [content, setContent] = useState('');
  const [isDirty, setIsDirty] = useState(false);
  const [error, setError] = useState('');

  const memoryQuery = useQuery({
    queryKey: ['short-term-memory', agentId],
    queryFn: () => shortTermMemoryApi.get(agentId),
  });

  useEffect(() => {
    if (memoryQuery.data && !isDirty) {
      setContent(memoryQuery.data.content);
    }
  }, [isDirty, memoryQuery.data]);

  const updateMutation = useMutation({
    mutationFn: (nextContent: string) =>
      shortTermMemoryApi.update(agentId, { content: nextContent }),
    onSuccess: (memory) => {
      queryClient.setQueryData(['short-term-memory', agentId], memory);
      setContent(memory.content);
      setIsDirty(false);
      setError('');
    },
    onError: (mutationError: unknown) => setError(getErrorMessage(mutationError)),
  });

  const save = () => {
    setError('');
    updateMutation.mutate(content);
  };

  return (
    <section className="mb-6">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">短期记忆</h2>
        <Button
          type="button"
          onClick={save}
          disabled={memoryQuery.isLoading || updateMutation.isPending || !isDirty}
        >
          {updateMutation.isPending && (
            <Loader2 size={16} className="mr-1 animate-spin" />
          )}
          保存
        </Button>
      </div>

      {(error || memoryQuery.error) && (
        <div className="mb-3 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error || getErrorMessage(memoryQuery.error)}
        </div>
      )}

      <Textarea
        value={content}
        onChange={(event) => {
          setContent(event.target.value);
          setIsDirty(true);
        }}
        className="min-h-64 resize-y font-mono text-sm leading-6"
        aria-label="短期记忆 Markdown"
        disabled={memoryQuery.isLoading}
      />
    </section>
  );
}
