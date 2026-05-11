import { useRef, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bold,
  Code2,
  Eye,
  FileText,
  Heading1,
  Heading2,
  Heading3,
  Italic,
  Link as LinkIcon,
  List,
  ListOrdered,
  Quote,
} from 'lucide-react';
import { useCreatePost } from '@/features/post';
import { Button, Input, Textarea } from '@/shared/components/ui';
import { MarkdownRenderer } from '@/shared/components/markdown/MarkdownRenderer';

type EditorMode = 'rich' | 'markdown';

const initialContent = '# \n\n';

export default function ArticleEditorPage() {
  const navigate = useNavigate();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState(initialContent);
  const [mode, setMode] = useState<EditorMode>('rich');
  const { mutate: createPost, isPending } = useCreatePost();

  const canPublish = title.trim().length > 0 && content.trim().length > 0;

  const submitArticle = (event: React.FormEvent) => {
    event.preventDefault();
    if (!canPublish || isPending) return;

    createPost(
      {
        title: title.trim(),
        type: 'article',
        content: content.trim(),
      },
      {
        onSuccess: (post) => {
          navigate(`/post/${post.id}`);
        },
      },
    );
  };

  const insertMarkdown = (before: string, after = '', placeholder = 'text') => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selected = content.slice(start, end) || placeholder;
    const nextContent = `${content.slice(0, start)}${before}${selected}${after}${content.slice(end)}`;
    const nextCursor = start + before.length + selected.length + after.length;

    setContent(nextContent);
    window.requestAnimationFrame(() => {
      textarea.focus();
      textarea.setSelectionRange(nextCursor, nextCursor);
    });
  };

  const insertLinePrefix = (prefix: string) => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const lineStart = content.lastIndexOf('\n', start - 1) + 1;
    const nextContent = `${content.slice(0, lineStart)}${prefix}${content.slice(lineStart)}`;
    setContent(nextContent);
    window.requestAnimationFrame(() => {
      textarea.focus();
      textarea.setSelectionRange(start + prefix.length, start + prefix.length);
    });
  };

  return (
    <form onSubmit={submitArticle} className="rounded-lg bg-white shadow-sm">
      <div className="border-b border-border/60 px-4 py-3">
        <Input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="文章标题"
          className="h-11 border-0 px-0 text-2xl font-semibold shadow-none focus-visible:ring-0"
        />
      </div>

      <div className="sticky top-[5.75rem] z-10 flex flex-wrap items-center gap-1 border-b border-border/60 bg-white px-3 py-2">
        <ToolbarButton label="一级标题" onClick={() => insertLinePrefix('# ')}>
          <Heading1 className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton label="二级标题" onClick={() => insertLinePrefix('## ')}>
          <Heading2 className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton label="三级标题" onClick={() => insertLinePrefix('### ')}>
          <Heading3 className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton label="加粗" onClick={() => insertMarkdown('**', '**')}>
          <Bold className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton label="斜体" onClick={() => insertMarkdown('*', '*')}>
          <Italic className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton label="无序列表" onClick={() => insertLinePrefix('- ')}>
          <List className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton label="有序列表" onClick={() => insertLinePrefix('1. ')}>
          <ListOrdered className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton label="引用" onClick={() => insertLinePrefix('> ')}>
          <Quote className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton label="代码" onClick={() => insertMarkdown('`', '`', 'code')}>
          <Code2 className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton label="链接" onClick={() => insertMarkdown('[', '](https://)', 'link')}>
          <LinkIcon className="h-4 w-4" />
        </ToolbarButton>

        <div className="ml-auto flex rounded-full bg-muted p-1">
          <button
            type="button"
            onClick={() => setMode('rich')}
            className={`flex h-8 w-8 items-center justify-center rounded-full ${
              mode === 'rich' ? 'bg-white text-foreground shadow-sm' : 'text-muted-foreground'
            }`}
            title="预览编辑"
          >
            <Eye className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => setMode('markdown')}
            className={`flex h-8 w-8 items-center justify-center rounded-full ${
              mode === 'markdown' ? 'bg-white text-foreground shadow-sm' : 'text-muted-foreground'
            }`}
            title="纯 Markdown"
          >
            <FileText className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className={mode === 'rich' ? 'grid gap-0 lg:grid-cols-2' : ''}>
        <Textarea
          ref={textareaRef}
          value={content}
          onChange={(event) => setContent(event.target.value)}
          className="min-h-[560px] resize-none rounded-none border-0 px-5 py-5 font-mono text-sm leading-6 shadow-none focus-visible:ring-0"
          placeholder="用 Markdown 写下文章正文..."
        />
        {mode === 'rich' && (
          <div className="min-h-[560px] border-t border-border/60 px-5 py-5 lg:border-l lg:border-t-0">
            <MarkdownRenderer content={content} />
          </div>
        )}
      </div>

      <div className="flex items-center justify-end gap-2 border-t border-border/60 px-4 py-3">
        <Button type="button" variant="ghost" onClick={() => navigate(-1)}>
          取消
        </Button>
        <Button type="submit" disabled={!canPublish || isPending}>
          {isPending ? '发布中...' : '发布文章'}
        </Button>
      </div>
    </form>
  );
}

function ToolbarButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex h-8 w-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      title={label}
    >
      {children}
    </button>
  );
}
