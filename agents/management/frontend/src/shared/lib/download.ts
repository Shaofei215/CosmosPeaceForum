/**
 * 触发浏览器下载 Blob，并在点击后释放临时对象 URL。
 *
 * @param blob 服务端返回的文件内容。
 * @param filename 浏览器保存时使用的文件名。
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = filename;
  link.style.display = 'none';
  document.body.appendChild(link);

  try {
    link.click();
  } finally {
    link.remove();
    URL.revokeObjectURL(objectUrl);
  }
}

/** 生成带本地时间的角色配置导出文件名。 */
export function buildAgentExportFilename(now = new Date()): string {
  const pad = (value: number) => String(value).padStart(2, '0');
  const timestamp = [
    now.getFullYear(),
    pad(now.getMonth() + 1),
    pad(now.getDate()),
    '_',
    pad(now.getHours()),
    pad(now.getMinutes()),
    pad(now.getSeconds()),
  ].join('');
  return `agents_config_${timestamp}.zip`;
}
