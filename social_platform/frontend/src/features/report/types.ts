export type ReportTargetType = 'post' | 'comment';

export interface ContentReportRequest {
  target_type: ReportTargetType;
  target_id: number;
  reason: string;
}

export interface ContentReportResponse {
  id: number;
  status: string;
  message: string;
}
