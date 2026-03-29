/**
 * 头像上传组件
 * 支持图片预览、上传、删除功能
 */

import { useState, useRef, useEffect } from 'react';
import { Camera, X } from 'lucide-react';
import { Avatar } from '@/shared/components/ui';
import { cn } from '@/shared/lib/utils';

interface AvatarUploadProps {
  /** 当前头像URL */
  avatarUrl?: string | null;
  /** 用户名（用于显示首字母） */
  username?: string;
  /** 头像尺寸 */
  size?: 'sm' | 'md' | 'lg' | 'xl' | '2xl';
  /** 是否禁用 */
  disabled?: boolean;
  /** 上传中状态 */
  isUploading?: boolean;
  /** 上传回调 */
  onUpload?: (file: File) => void;
  /** 删除回调 */
  onDelete?: () => void;
  /** 错误信息 */
  error?: string;
}

/**
 * 头像上传组件
 */
export function AvatarUpload({
  avatarUrl,
  username = '用户',
  size = 'lg',
  disabled = false,
  isUploading = false,
  onUpload,
  onDelete,
  error,
}: AvatarUploadProps) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (avatarUrl) {
      setPreviewUrl(null);
    }
  }, [avatarUrl]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFile(file);
    }
  };

  const handleFile = (file: File) => {
    if (!file.type.startsWith('image/')) {
      return;
    }

    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    onUpload?.(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    if (disabled) return;

    const file = e.dataTransfer.files?.[0];
    if (file && file.type.startsWith('image/')) {
      handleFile(file);
    }
  };

  const handleClick = () => {
    if (!disabled && !isUploading) {
      fileInputRef.current?.click();
    }
  };

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    setPreviewUrl(null);
    onDelete?.();
  };

  const displayUrl = previewUrl || avatarUrl;

  return (
    <div className="flex flex-col items-center gap-2">
      <div
        className={cn(
          'relative cursor-pointer group',
          disabled && 'cursor-not-allowed opacity-60',
          isDragging && 'ring-2 ring-primary rounded-full'
        )}
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <Avatar
          src={displayUrl}
          alt={username}
          size={size}
          className={cn(
            'transition-all duration-200',
            !disabled && 'group-hover:opacity-70'
          )}
        />

        {!disabled && !isUploading && (
          <>
            <div className="absolute inset-0 flex items-center justify-center bg-black/40 rounded-full opacity-0 group-hover:opacity-100 transition-opacity">
              <Camera className="w-6 h-6 text-white" />
            </div>
            {displayUrl && (
              <button
                type="button"
                onClick={handleDelete}
                className="absolute -top-1 -right-1 w-6 h-6 bg-destructive text-destructive-foreground rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity shadow-md hover:bg-destructive/90"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </>
        )}

        {isUploading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/40 rounded-full">
            <div className="w-6 h-6 border-2 border-white border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleFileChange}
          className="hidden"
          disabled={disabled || isUploading}
        />
      </div>

      {error && (
        <p className="text-xs text-destructive">{error}</p>
      )}

      <p className="text-xs text-muted-foreground">
        点击上传或拖拽图片（最大5MB）
      </p>
    </div>
  );
}
