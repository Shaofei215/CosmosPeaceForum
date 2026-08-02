import { describe, expect, it } from 'vitest';

import type { AgentConfig } from '@/shared/types/api';
import { buildAgentSavePlan, type AgentFormValues } from './agentSavePlan';

const agent: AgentConfig = {
  id: 1,
  name: '角色一',
  username: 'agent_one',
  monthly_logins: 30,
  personal_signature: '签名',
  personality_prompt: '提示词',
  knows_ids: [2, 3],
  is_active: true,
  model_config_id: 4,
  social_platform_user_id: 10,
  last_login_at: null,
  last_login_timestamp: null,
  total_login_count: 0,
  created_at: '2026-01-01T00:00:00',
  updated_at: '2026-01-01T00:00:00',
};

const values = (overrides: Partial<AgentFormValues> = {}): AgentFormValues => ({
  name: agent.name,
  username: agent.username,
  monthlyLogins: agent.monthly_logins,
  signature: agent.personal_signature,
  personalityPrompt: agent.personality_prompt,
  isActive: agent.is_active,
  knowsIds: agent.knows_ids,
  bidirectional: false,
  ...overrides,
});

describe('buildAgentSavePlan', () => {
  it('没有变化时不生成请求', () => {
    expect(buildAgentSavePlan(agent, values())).toEqual({
      agentUpdate: null,
      relationUpdate: null,
    });
  });

  it('只修改基础配置时仅生成角色更新', () => {
    const plan = buildAgentSavePlan(agent, values({ monthlyLogins: 60 }));
    expect(plan.agentUpdate?.monthly_logins).toBe(60);
    expect(plan.relationUpdate).toBeNull();
  });

  it('只修改关系时仅生成关系更新', () => {
    const plan = buildAgentSavePlan(agent, values({ knowsIds: [2, 5] }));
    expect(plan.agentUpdate).toBeNull();
    expect(plan.relationUpdate).toEqual({ knows_ids: [2, 5], bidirectional: false });
  });

  it('关系顺序变化不算修改', () => {
    expect(buildAgentSavePlan(agent, values({ knowsIds: [3, 2] })).relationUpdate).toBeNull();
  });

  it('双向操作会强制生成关系同步请求', () => {
    expect(buildAgentSavePlan(agent, values({ bidirectional: true })).relationUpdate).toEqual({
      knows_ids: [2, 3],
      bidirectional: true,
    });
  });

  it('字符串仅有首尾空白变化时不生成角色更新', () => {
    const plan = buildAgentSavePlan(agent, values({
      username: ` ${agent.username} `,
      signature: ` ${agent.personal_signature} `,
      personalityPrompt: ` ${agent.personality_prompt} `,
    }));
    expect(plan.agentUpdate).toBeNull();
  });
});
