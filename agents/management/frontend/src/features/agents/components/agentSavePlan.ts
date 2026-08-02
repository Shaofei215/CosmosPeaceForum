import type {
  AgentConfig,
  AgentRelationUpdate,
  AgentUpdate,
} from '@/shared/types/api';

export interface AgentFormValues {
  name: string;
  username: string;
  monthlyLogins: number;
  signature: string;
  personalityPrompt: string;
  isActive: boolean;
  knowsIds: Iterable<number>;
  bidirectional: boolean;
}

export interface AgentSavePlan {
  agentUpdate: AgentUpdate | null;
  relationUpdate: AgentRelationUpdate | null;
}

const haveSameIds = (left: Iterable<number>, right: Iterable<number>): boolean => {
  const leftSet = new Set(left);
  const rightSet = new Set(right);
  return leftSet.size === rightSet.size && [...leftSet].every((id) => rightSet.has(id));
};

/** 根据编辑前后的值生成最小保存请求集合。 */
export const buildAgentSavePlan = (
  agent: AgentConfig,
  values: AgentFormValues,
): AgentSavePlan => {
  const agentUpdate: AgentUpdate = {
    username: values.username.trim(),
    name: values.name.trim(),
    monthly_logins: values.monthlyLogins,
    personal_signature: values.signature.trim(),
    personality_prompt: values.personalityPrompt.trim(),
    is_active: values.isActive,
  };
  const hasAgentChanges =
    agentUpdate.username !== agent.username
    || agentUpdate.name !== agent.name
    || agentUpdate.monthly_logins !== agent.monthly_logins
    || agentUpdate.personal_signature !== agent.personal_signature
    || agentUpdate.personality_prompt !== agent.personality_prompt
    || agentUpdate.is_active !== agent.is_active;

  const knowsIds = [...new Set(values.knowsIds)];
  const hasRelationChanges = !haveSameIds(knowsIds, agent.knows_ids);

  return {
    agentUpdate: hasAgentChanges ? agentUpdate : null,
    relationUpdate: hasRelationChanges || values.bidirectional
      ? { knows_ids: knowsIds, bidirectional: values.bidirectional }
      : null,
  };
};
