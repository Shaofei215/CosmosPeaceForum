import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Braces, RotateCcw, Save, ScrollText } from 'lucide-react';
import { promptApi } from '@/shared/api/modules';
import {
  Badge, Button, Card, CardContent, Textarea,
} from '@/shared/components/ui';

interface PlaceholderHint {
  token: string;
  description: string;
}

const PLACEHOLDER_LABELS: Record<string, PlaceholderHint[]> = {
  agent_system_prompt: [
    { token: '{platform_user_id}', description: '当前登录的平台用户 ID。' },
    { token: '{following_count}', description: '当前账号关注数。' },
    { token: '{followers_count}', description: '当前账号粉丝数。' },
    { token: '{unread_count}', description: '当前未读消息数。' },
    { token: '{hot_topic_titles}', description: '当前热榜前 8 个标题。' },
    { token: '{topic_titles}', description: '当前热门话题前 8 个名称。' },
    { token: '{#if login_stats}', description: '条件段：仅存在登录统计时拼入。' },
    { token: '{total_login_count}', description: '累计登录次数。' },
    { token: '{last_login_time}', description: '上次登录时间描述。' },
    { token: '{name}', description: '角色昵称。' },
    { token: '{username}', description: '角色用户名。' },
    { token: '{personality_prompt}', description: '角色性格提示词。' },
    { token: '{personal_signature}', description: '角色个人签名。' },
    {
      token: '{#if session_prompt_injection}',
      description: '条件段：仅本次会话存在临时注入时拼入。',
    },
    { token: '{session_prompt_injection}', description: '下一次登录会话的一次性临时提示词。' },
  ],
  summarize_memory_prompt: [
    { token: '{username}', description: '角色用户名。' },
    { token: '{history_text}', description: '本次会话操作历史。' },
  ],
  memory_chunk_system_prompt: [
    { token: '{personality_prompt}', description: '角色性格提示词。' },
    { token: '{text}', description: '待智能分块的原始文本。' },
    {
      token: '{#if static_memories_context}',
      description: '条件段：仅召回到相关记忆时拼入。',
    },
    { token: '{static_memories_context}', description: '分块时召回到的已有相关记忆。' },
    { token: '{owner_id}', description: '记忆所有者平台用户 ID。' },
    { token: '{semantic_timestamp}', description: '本次写入使用的语义时间戳。' },
  ],
};

export default function PromptConfigPage() {
  const queryClient = useQueryClient();
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const { data: prompts, isLoading } = useQuery({
    queryKey: ['prompts'],
    queryFn: promptApi.list,
  });

  useEffect(() => {
    if (!prompts) return;
    setDrafts((current) => {
      const next = { ...current };
      prompts.forEach((prompt) => {
        if (next[prompt.key] === undefined) {
          next[prompt.key] = prompt.value;
        }
      });
      return next;
    });
  }, [prompts]);

  const dirtyKeys = useMemo(() => {
    const keys = new Set<string>();
    prompts?.forEach((prompt) => {
      if ((drafts[prompt.key] ?? prompt.value) !== prompt.value) {
        keys.add(prompt.key);
      }
    });
    return keys;
  }, [drafts, prompts]);

  const updateMutation = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) =>
      promptApi.update(key, value),
    onSuccess: (updated) => {
      setDrafts((current) => ({ ...current, [updated.key]: updated.value }));
      queryClient.invalidateQueries({ queryKey: ['prompts'] });
    },
  });

  const resetMutation = useMutation({
    mutationFn: (key: string) => promptApi.reset(key),
    onSuccess: (updated) => {
      setDrafts((current) => ({ ...current, [updated.key]: updated.value }));
      queryClient.invalidateQueries({ queryKey: ['prompts'] });
    },
  });

  if (isLoading) {
    return (
      <div>
        <h1 className="mb-6 text-2xl font-bold">提示词管理</h1>
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Card key={index}>
              <CardContent className="space-y-3 p-4">
                <div className="h-4 w-1/4 animate-pulse rounded bg-muted" />
                <div className="h-36 animate-pulse rounded bg-muted" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">提示词管理</h1>
      </div>

      <div className="space-y-5">
        {prompts?.map((prompt) => {
          const draft = drafts[prompt.key] ?? prompt.value;
          const isDirty = dirtyKeys.has(prompt.key);
          const placeholders = PLACEHOLDER_LABELS[prompt.key] ?? [];

          return (
            <Card key={prompt.key}>
              <CardContent className="space-y-4 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <ScrollText size={18} className="text-muted-foreground" />
                      <h2 className="text-lg font-semibold">{prompt.name}</h2>
                      {isDirty && <Badge variant="secondary">未保存</Badge>}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Button
                      variant="outline"
                      onClick={() => setDrafts((current) => ({
                        ...current,
                        [prompt.key]: prompt.value,
                      }))}
                      disabled={!isDirty || updateMutation.isPending || resetMutation.isPending}
                    >
                      取消
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => resetMutation.mutate(prompt.key)}
                      disabled={updateMutation.isPending || resetMutation.isPending}
                    >
                      <RotateCcw size={15} className="mr-1.5" />
                      恢复默认
                    </Button>
                    <Button
                      onClick={() => updateMutation.mutate({ key: prompt.key, value: draft })}
                      disabled={!draft.trim() || !isDirty || updateMutation.isPending}
                    >
                      <Save size={15} className="mr-1.5" />
                      保存
                    </Button>
                  </div>
                </div>

                {placeholders.length > 0 && (
                  <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <Braces size={14} />
                    {placeholders.map((placeholder) => (
                      <Badge
                        key={placeholder.token}
                        variant="outline"
                        className="font-mono"
                        title={placeholder.description}
                      >
                        {placeholder.token}
                      </Badge>
                    ))}
                  </div>
                )}

                <Textarea
                  value={draft}
                  onChange={(event) => setDrafts((current) => ({
                    ...current,
                    [prompt.key]: event.target.value,
                  }))}
                  className="min-h-[340px] font-mono leading-relaxed"
                  spellCheck={false}
                />
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
