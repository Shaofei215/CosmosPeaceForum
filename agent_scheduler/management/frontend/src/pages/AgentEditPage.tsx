import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { agentApi } from '@/shared/api/modules';
import AgentFormPage from '@/features/agents/components/AgentForm';
import { Skeleton } from '@/shared/components/ui';

export default function AgentEditPage() {
  const { id } = useParams<{ id: string }>();
  const agentId = Number(id);

  const { data: agent, isLoading } = useQuery({
    queryKey: ['agent', agentId],
    queryFn: () => agentApi.getOne(agentId),
    enabled: !!agentId,
  });

  if (isLoading || !agent) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return <AgentFormPage mode="edit" agent={agent} />;
}
