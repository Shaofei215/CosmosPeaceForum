import { apiClient } from '@/shared/api/client';
import type { ContentReportRequest, ContentReportResponse } from './types';

export const reportApi = {
  createReport: (request: ContentReportRequest) =>
    apiClient.post<ContentReportResponse>('/reports', request),
};
