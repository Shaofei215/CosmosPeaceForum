import { useEffect, useState } from 'react';
import { ImagePlus, Palette, RotateCcw, Save } from 'lucide-react';
import { Button, Card, CardContent, CardHeader, CardTitle, Input } from '@/shared/components/ui';
import { useAdminTheme, useUpdateAdminTheme } from '@/features/theme';
import type { ThemeSettingsUpdate, TopbarBackgroundMode } from '@/features/theme';

const defaultTheme: ThemeSettingsUpdate = {
  accent_color: '#111827',
  accent_foreground_color: '#ffffff',
  subtle_color: 'rgba(243, 244, 246, 0.82)',
  subtle_foreground_color: '#4b5563',
  topbar_background_mode: 'solid',
  topbar_solid_color: '#ffffff',
  topbar_gradient_from: '#ffffff',
  topbar_gradient_to: '#f3f4f6',
  topbar_gradient_direction: '90deg',
  topbar_scrolled_background: 'rgba(255, 255, 255, 0.45)',
  topbar_decoration_top: null,
  topbar_decoration_bottom: null,
  topbar_decoration_left: null,
  topbar_decoration_right: null,
};

type ThemeField = keyof ThemeSettingsUpdate;

export default function AdminThemePage() {
  const { data, isLoading } = useAdminTheme();
  const updateTheme = useUpdateAdminTheme();
  const [form, setForm] = useState<ThemeSettingsUpdate>(defaultTheme);
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (data) {
      const editable = Object.fromEntries(
        Object.entries(data).filter(([key]) => key !== 'id' && key !== 'updated_at')
      ) as ThemeSettingsUpdate;
      setForm(editable);
    }
  }, [data]);

  const setField = <K extends ThemeField>(field: K, value: ThemeSettingsUpdate[K]) => {
    setForm(current => ({ ...current, [field]: value }));
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setMessage('');
    updateTheme.mutate(form, {
      onSuccess: () => setMessage('主题已保存'),
      onError: error => {
        const message = error instanceof Error ? error.message : '保存失败';
        setMessage(message);
      },
    });
  };

  if (isLoading) {
    return <div className="text-sm text-muted-foreground">正在加载主题配置...</div>;
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">主题管理</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            这些配置只作用于公开前台的用户侧界面，不影响管理后台。
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            className="rounded-md gap-2"
            onClick={() => setForm(defaultTheme)}
          >
            <RotateCcw size={14} />
            恢复默认
          </Button>
          <Button type="submit" className="rounded-md gap-2" disabled={updateTheme.isPending}>
            <Save size={14} />
            {updateTheme.isPending ? '保存中...' : '保存'}
          </Button>
        </div>
      </div>

      {message && (
        <div className="rounded-lg border border-border bg-card px-3 py-2 text-sm">{message}</div>
      )}

      <div className="grid gap-4 xl:grid-cols-[1fr_22rem]">
        <div className="space-y-4">
          <Card className="rounded-lg">
            <CardHeader className="flex flex-row items-center gap-2 space-y-0">
              <Palette size={18} className="text-muted-foreground" />
              <CardTitle>颜色系统</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
              <ColorField
                label="强调色"
                description="登录、注册、发布、关注，以及被选中状态。"
                value={form.accent_color}
                onChange={value => setField('accent_color', value)}
              />
              <ColorField
                label="强调色文字"
                description="强调按钮上的文字颜色。"
                value={form.accent_foreground_color}
                onChange={value => setField('accent_foreground_color', value)}
              />
              <ColorField
                label="非强调色"
                description="验证码、未选中状态、次级按钮背景，可填 transparent。"
                value={form.subtle_color}
                onChange={value => setField('subtle_color', value)}
              />
              <ColorField
                label="非强调色文字"
                description="次级按钮和未选中状态文字。"
                value={form.subtle_foreground_color}
                onChange={value => setField('subtle_foreground_color', value)}
              />
            </CardContent>
          </Card>

          <Card className="rounded-lg">
            <CardHeader>
              <CardTitle>顶栏系统</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <label className="space-y-2">
                <span className="text-sm font-medium">背景模式</span>
                <select
                  value={form.topbar_background_mode}
                  onChange={event =>
                    setField('topbar_background_mode', event.target.value as TopbarBackgroundMode)
                  }
                  className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                >
                  <option value="solid">纯色</option>
                  <option value="gradient">渐变</option>
                </select>
              </label>

              {form.topbar_background_mode === 'gradient' ? (
                <div className="grid gap-4 md:grid-cols-3">
                  <ColorField
                    label="渐变起点"
                    description="顶部不透明，滚动后自动半透明毛玻璃。"
                    value={form.topbar_gradient_from}
                    onChange={value => setField('topbar_gradient_from', value)}
                  />
                  <ColorField
                    label="渐变终点"
                    value={form.topbar_gradient_to}
                    onChange={value => setField('topbar_gradient_to', value)}
                  />
                  <label className="space-y-2">
                    <span className="text-sm font-medium">渐变方向</span>
                    <Input
                      value={form.topbar_gradient_direction}
                      onChange={event => setField('topbar_gradient_direction', event.target.value)}
                      placeholder="90deg"
                    />
                  </label>
                </div>
              ) : (
                <ColorField
                  label="顶栏背景色"
                  description="顶部不透明，滚动后自动半透明毛玻璃。"
                  value={form.topbar_solid_color}
                  onChange={value => setField('topbar_solid_color', value)}
                />
              )}
            </CardContent>
          </Card>

          <Card className="rounded-lg">
            <CardHeader className="flex flex-row items-center gap-2 space-y-0">
              <ImagePlus size={18} className="text-muted-foreground" />
              <CardTitle>顶栏图片装饰</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
              <ImageField
                label="上方装饰"
                value={form.topbar_decoration_top}
                onChange={value => setField('topbar_decoration_top', value)}
              />
              <ImageField
                label="下方装饰"
                value={form.topbar_decoration_bottom}
                onChange={value => setField('topbar_decoration_bottom', value)}
              />
              <ImageField
                label="左侧装饰"
                value={form.topbar_decoration_left}
                onChange={value => setField('topbar_decoration_left', value)}
              />
              <ImageField
                label="右侧装饰"
                value={form.topbar_decoration_right}
                onChange={value => setField('topbar_decoration_right', value)}
              />
            </CardContent>
          </Card>
        </div>

        <ThemePreview form={form} />
      </div>
    </form>
  );
}

function ColorField({
  label,
  description,
  value,
  onChange,
}: {
  label: string;
  description?: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const colorValue = /^#[0-9a-fA-F]{6}$/.test(value) ? value : '#ffffff';

  return (
    <label className="space-y-2">
      <span className="text-sm font-medium">{label}</span>
      <div className="flex gap-2">
        <input
          type="color"
          value={colorValue}
          onChange={event => onChange(event.target.value)}
          className="h-9 w-10 shrink-0 rounded-md border border-input bg-background"
        />
        <Input value={value} onChange={event => onChange(event.target.value)} />
      </div>
      {description && <p className="text-xs text-muted-foreground">{description}</p>}
    </label>
  );
}

function ImageField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string | null;
  onChange: (value: string | null) => void;
}) {
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        onChange(reader.result);
      }
    };
    reader.readAsDataURL(file);
  };

  return (
    <div className="space-y-2">
      <span className="text-sm font-medium">{label}</span>
      <Input
        value={value ?? ''}
        onChange={event => onChange(event.target.value || null)}
        placeholder="图片 URL 或 data URL"
      />
      <div className="flex items-center gap-2">
        <input type="file" accept="image/*" onChange={handleFileChange} className="text-xs" />
        <Button type="button" variant="ghost" size="sm" onClick={() => onChange(null)}>
          清除
        </Button>
      </div>
      {value && (
        <div className="flex h-12 items-center rounded-md border border-border bg-muted/30 p-2">
          <img src={value} alt="" className="max-h-full max-w-full object-contain" />
        </div>
      )}
    </div>
  );
}

function colorToRgb(color: string): [number, number, number] | null {
  const value = color.trim();
  if (value.toLowerCase() === 'transparent') {
    return [255, 255, 255];
  }

  const hex = value.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (hex) {
    const raw = hex[1].length === 3 ? hex[1].replace(/./g, char => char + char) : hex[1];
    return [
      Number.parseInt(raw.slice(0, 2), 16),
      Number.parseInt(raw.slice(2, 4), 16),
      Number.parseInt(raw.slice(4, 6), 16),
    ];
  }

  const rgba = value.match(/^rgba?\(\s*(\d{1,3})[,\s]+(\d{1,3})[,\s]+(\d{1,3})/i);
  if (!rgba) return null;
  return [
    Math.min(255, Number(rgba[1])),
    Math.min(255, Number(rgba[2])),
    Math.min(255, Number(rgba[3])),
  ];
}

function colorWithAlpha(color: string, alpha: number, fallback: string) {
  const rgb = colorToRgb(color);
  return rgb ? `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${alpha})` : fallback;
}

function getPreviewTopbarBackground(form: ThemeSettingsUpdate, alpha: number) {
  if (form.topbar_background_mode === 'gradient') {
    return `linear-gradient(${form.topbar_gradient_direction}, ${colorWithAlpha(
      form.topbar_gradient_from,
      alpha,
      form.topbar_gradient_from
    )}, ${colorWithAlpha(form.topbar_gradient_to, alpha, form.topbar_gradient_to)})`;
  }

  return colorWithAlpha(form.topbar_solid_color, alpha, form.topbar_solid_color);
}

function ThemePreview({ form }: { form: ThemeSettingsUpdate }) {
  const topbarBackground = getPreviewTopbarBackground(form, 1);
  const topbarGlassBackground = getPreviewTopbarBackground(form, 0.45);

  return (
    <Card className="h-fit rounded-lg xl:sticky xl:top-5">
      <CardHeader>
        <CardTitle>预览</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div
          className="rounded-[2rem] border border-border p-3"
          style={{ background: topbarBackground }}
        >
          <div className="flex items-center gap-2">
            <div className="h-8 w-16 rounded-full bg-white/70" />
            <div className="h-8 flex-1 rounded-full bg-muted/50" />
            <div
              className="rounded-full px-3 py-1.5 text-sm"
              style={{ background: form.accent_color, color: form.accent_foreground_color }}
            >
              推荐
            </div>
          </div>
        </div>
        <div
          className="rounded-[2rem] border border-white/40 p-3 shadow-md backdrop-blur-xl"
          style={{ background: topbarGlassBackground }}
        >
          <div className="flex items-center gap-2">
            <div className="h-8 w-16 rounded-full bg-white/60" />
            <div className="h-8 flex-1 rounded-full bg-muted/50" />
            <div
              className="rounded-full px-3 py-1.5 text-sm"
              style={{ background: form.accent_color, color: form.accent_foreground_color }}
            >
              最新
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-full px-4 py-2 text-sm"
            style={{ background: form.accent_color, color: form.accent_foreground_color }}
          >
            发布
          </button>
          <button
            type="button"
            className="rounded-lg px-4 py-2 text-sm"
            style={{ background: form.accent_color, color: form.accent_foreground_color }}
          >
            获取验证码
          </button>
          <button
            type="button"
            className="rounded-md px-3 py-2 text-sm"
            style={{ background: form.accent_color, color: form.accent_foreground_color }}
          >
            H1
          </button>
          <button
            type="button"
            className="rounded-md px-3 py-2 text-sm"
            style={{ background: form.subtle_color, color: form.subtle_foreground_color }}
          >
            H2
          </button>
        </div>
      </CardContent>
    </Card>
  );
}
