import { useMutation } from '@tanstack/react-query';
import { reportApi } from './api';

export const useCreateReport = () => {
  return useMutation({
    mutationFn: reportApi.createReport,
  });
};
