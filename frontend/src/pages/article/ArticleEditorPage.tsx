import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import type { Editor } from '@tiptap/core';
import { EditorContent, useEditor } from '@tiptap/react';
import LinkExtension from '@tiptap/extension-link';
import Placeholder from '@tiptap/extension-placeholder';
import StarterKit from '@tiptap/starter-kit';
import { marked } from 'marked';
import TurndownService from 'turndown';
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
import { cn } from '@/shared/lib/utils';

type EditorMode = 'rich' | 'markdown';

type ToolbarAction =
  | 'h1'
  | 'h2'
  | 'h3'
  | 'bold'
  | 'italic'
  | 'ul'
  | 'ol'
  | 'quote'
  | 'code'
  | 'link';

type ToolbarState = Record<ToolbarAction, boolean>;

const emptyToolbarState: ToolbarState = {
  h1: false,
  h2: false,
  h3: false,
  bold: false,
  italic: false,
  ul: false,
  ol: false,
  quote: false,
  code: false,
  link: false,
};

const text = {
  titlePlaceholder: '\u6587\u7ae0\u6807\u9898',
  editorPlaceholder: '\u5f00\u59cb\u5199\u4f5c...',
  markdownPlaceholder: '\u7528 Markdown \u5199\u4e0b\u6587\u7ae0\u6b63\u6587...',
  h1: '\u4e00\u7ea7\u6807\u9898',
  h2: '\u4e8c\u7ea7\u6807\u9898',
  h3: '\u4e09\u7ea7\u6807\u9898',
  bold: '\u52a0\u7c97',
  italic: '\u659c\u4f53',
  unorderedList: '\u65e0\u5e8f\u5217\u8868',
  orderedList: '\u6709\u5e8f\u5217\u8868',
  quote: '\u5f15\u7528',
  codeBlock: '\u4ee3\u7801\u5757',
  link: '\u94fe\u63a5',
  linkPrompt: '\u94fe\u63a5\u5730\u5740',
  richMode: '\u5bcc\u6587\u672c\u6a21\u5f0f',
  markdownMode: 'Markdown \u6a21\u5f0f',
  cancel: '\u53d6\u6d88',
  publishing: '\u53d1\u5e03\u4e2d...',
  publish: '\u53d1\u5e03\u6587\u7ae0',
};

const markdownConverter = new TurndownService({
  bulletListMarker: '-',
  codeBlockStyle: 'fenced',
  emDelimiter: '*',
  headingStyle: 'atx',
});

export default function ArticleEditorPage() {
  const navigate = useNavigate();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [mode, setMode] = useState<EditorMode>('rich');
  const [toolbarState, setToolbarState] = useState<ToolbarState>(emptyToolbarState);
  const { mutate: createPost, isPending } = useCreatePost();

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [1, 2, 3],
        },
      }),
      LinkExtension.configure({
        autolink: true,
        defaultProtocol: 'https',
        HTMLAttributes: {
          class: 'font-medium text-primary',
          rel: 'noreferrer',
          target: '_blank',
        },
        linkOnPaste: true,
        openOnClick: false,
      }),
      Placeholder.configure({
        placeholder: text.editorPlaceholder,
      }),
    ],
    content: '',
    editorProps: {
      attributes: {
        class: 'article-rich-editor-content',
      },
    },
    onUpdate({ editor: currentEditor }) {
      setContent(htmlToMarkdown(currentEditor.getHTML()));
    },
  });

  useEffect(() => {
    if (!editor) {
      setToolbarState(emptyToolbarState);
      return;
    }

    const refreshToolbarState = () => {
      setToolbarState(getToolbarState(editor));
    };

    refreshToolbarState();
    editor.on('selectionUpdate', refreshToolbarState);
    editor.on('transaction', refreshToolbarState);
    editor.on('focus', refreshToolbarState);
    editor.on('blur', refreshToolbarState);

    return () => {
      editor.off('selectionUpdate', refreshToolbarState);
      editor.off('transaction', refreshToolbarState);
      editor.off('focus', refreshToolbarState);
      editor.off('blur', refreshToolbarState);
    };
  }, [editor]);

  const currentMarkdown = mode === 'rich' && editor ? htmlToMarkdown(editor.getHTML()) : content;
  const canPublish = title.trim().length > 0 && currentMarkdown.trim().length > 0;

  const setEditorMode = (nextMode: EditorMode) => {
    if (nextMode === mode) return;

    if (nextMode === 'markdown') {
      const nextContent = editor ? htmlToMarkdown(editor.getHTML()) : content;
      setContent(nextContent);
      setMode('markdown');
      return;
    }

    editor?.commands.setContent(markdownToHtml(content));
    setMode('rich');
    window.requestAnimationFrame(() => editor?.commands.focus('end'));
  };

  const submitArticle = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const nextContent = mode === 'rich' && editor ? htmlToMarkdown(editor.getHTML()) : content;
    if (!title.trim() || !nextContent.trim() || isPending) return;

    setContent(nextContent);
    createPost(
      {
        title: title.trim(),
        type: 'article',
        content: nextContent.trim(),
      },
      {
        onSuccess: post => {
          navigate(`/post/${post.id}`);
        },
      }
    );
  };

  const applyStyle = (style: ToolbarAction) => {
    if (mode === 'markdown') {
      applyMarkdownStyle(style);
      return;
    }

    if (!editor) return;

    if (style === 'h1') editor.chain().focus().toggleHeading({ level: 1 }).run();
    if (style === 'h2') editor.chain().focus().toggleHeading({ level: 2 }).run();
    if (style === 'h3') editor.chain().focus().toggleHeading({ level: 3 }).run();
    if (style === 'bold') editor.chain().focus().toggleBold().run();
    if (style === 'italic') editor.chain().focus().toggleItalic().run();
    if (style === 'ul') editor.chain().focus().toggleBulletList().run();
    if (style === 'ol') editor.chain().focus().toggleOrderedList().run();
    if (style === 'quote') editor.chain().focus().toggleBlockquote().run();
    if (style === 'code') editor.chain().focus().toggleCodeBlock().run();
    if (style === 'link') setRichLink();
  };

  const setRichLink = () => {
    if (!editor) return;

    const previousHref = editor.getAttributes('link').href as string | undefined;
    const href = window.prompt(text.linkPrompt, previousHref || 'https://');
    if (href === null) return;

    if (!href.trim()) {
      editor.chain().focus().extendMarkRange('link').unsetLink().run();
      return;
    }

    editor.chain().focus().extendMarkRange('link').setLink({ href: href.trim() }).run();
  };

  const insertMarkdown = (before: string, after = '', placeholder = 'text') => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selected = content.slice(start, end) || placeholder;
    const nextContent = [content.slice(0, start), before, selected, after, content.slice(end)].join(
      ''
    );
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

  const insertCodeBlock = () => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selected = content.slice(start, end) || 'code';
    const block = `\n\`\`\`\n${selected}\n\`\`\`\n`;
    const nextContent = `${content.slice(0, start)}${block}${content.slice(end)}`;
    const nextCursor = start + block.length;

    setContent(nextContent);
    window.requestAnimationFrame(() => {
      textarea.focus();
      textarea.setSelectionRange(nextCursor, nextCursor);
    });
  };

  const applyMarkdownStyle = (style: ToolbarAction) => {
    if (style === 'h1') insertLinePrefix('# ');
    if (style === 'h2') insertLinePrefix('## ');
    if (style === 'h3') insertLinePrefix('### ');
    if (style === 'bold') insertMarkdown('**', '**');
    if (style === 'italic') insertMarkdown('*', '*');
    if (style === 'ul') insertLinePrefix('- ');
    if (style === 'ol') insertLinePrefix('1. ');
    if (style === 'quote') insertLinePrefix('> ');
    if (style === 'code') insertCodeBlock();
    if (style === 'link') insertMarkdown('[', '](https://)', 'link');
  };

  return (
    <form onSubmit={submitArticle} className="overflow-hidden rounded-lg bg-white shadow-sm">
      <div className="border-b border-border/60 px-3 py-3 sm:px-4">
        <Input
          value={title}
          onChange={event => setTitle(event.target.value)}
          placeholder={text.titlePlaceholder}
          className="h-10 border-0 px-0 text-xl font-semibold shadow-none focus-visible:ring-0 sm:h-11 sm:text-2xl"
        />
      </div>

      <div
        className={cn(
          'sticky top-[4.5rem] z-10 flex flex-wrap items-center gap-1 sm:top-[5.75rem]',
          'border-b border-border/60 bg-white px-2 py-2 sm:px-3'
        )}
      >
        <ToolbarButton
          label={text.h1}
          active={mode === 'rich' && toolbarState.h1}
          onClick={() => applyStyle('h1')}
        >
          <Heading1 className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton
          label={text.h2}
          active={mode === 'rich' && toolbarState.h2}
          onClick={() => applyStyle('h2')}
        >
          <Heading2 className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton
          label={text.h3}
          active={mode === 'rich' && toolbarState.h3}
          onClick={() => applyStyle('h3')}
        >
          <Heading3 className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton
          label={text.bold}
          active={mode === 'rich' && toolbarState.bold}
          onClick={() => applyStyle('bold')}
        >
          <Bold className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton
          label={text.italic}
          active={mode === 'rich' && toolbarState.italic}
          onClick={() => applyStyle('italic')}
        >
          <Italic className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton
          label={text.unorderedList}
          active={mode === 'rich' && toolbarState.ul}
          onClick={() => applyStyle('ul')}
        >
          <List className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton
          label={text.orderedList}
          active={mode === 'rich' && toolbarState.ol}
          onClick={() => applyStyle('ol')}
        >
          <ListOrdered className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton
          label={text.quote}
          active={mode === 'rich' && toolbarState.quote}
          onClick={() => applyStyle('quote')}
        >
          <Quote className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton
          label={text.codeBlock}
          active={mode === 'rich' && toolbarState.code}
          onClick={() => applyStyle('code')}
        >
          <Code2 className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton
          label={text.link}
          active={mode === 'rich' && toolbarState.link}
          onClick={() => applyStyle('link')}
        >
          <LinkIcon className="h-4 w-4" />
        </ToolbarButton>

        <div className="ml-auto flex rounded-full bg-muted p-1">
          <button
            type="button"
            onClick={() => setEditorMode('rich')}
            className={cn(
              'flex h-8 w-8 items-center justify-center rounded-full',
              mode === 'rich' ? 'bg-white text-foreground shadow-sm' : 'text-muted-foreground'
            )}
            title={text.richMode}
          >
            <Eye className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => setEditorMode('markdown')}
            className={cn(
              'flex h-8 w-8 items-center justify-center rounded-full',
              mode === 'markdown' ? 'bg-white text-foreground shadow-sm' : 'text-muted-foreground'
            )}
            title={text.markdownMode}
          >
            <FileText className="h-4 w-4" />
          </button>
        </div>
      </div>

      {mode === 'rich' ? (
        <EditorContent
          editor={editor}
          className="article-rich-editor min-h-[420px] px-4 py-4 sm:min-h-[560px] sm:px-6 sm:py-6"
        />
      ) : (
        <div className="grid gap-0 lg:grid-cols-2">
          <Textarea
            ref={textareaRef}
            value={content}
            onChange={event => setContent(event.target.value)}
            className={cn(
              'min-h-[420px] resize-none rounded-none border-0 px-4 py-4 sm:min-h-[560px] sm:px-5 sm:py-5',
              'font-mono text-sm leading-6 shadow-none focus-visible:ring-0'
            )}
            placeholder={text.markdownPlaceholder}
          />
          <div
            className={cn(
              'min-h-[320px] border-t border-border/60 px-4 py-4 sm:min-h-[560px] sm:px-5 sm:py-5',
              'lg:border-l lg:border-t-0'
            )}
          >
            <MarkdownRenderer content={content} />
          </div>
        </div>
      )}

      <div className="flex items-center justify-end gap-2 border-t border-border/60 px-3 py-3 sm:px-4">
        <Button type="button" variant="ghost" onClick={() => navigate(-1)}>
          {text.cancel}
        </Button>
        <Button type="submit" disabled={!canPublish || isPending}>
          {isPending ? text.publishing : text.publish}
        </Button>
      </div>
    </form>
  );
}

function ToolbarButton({
  label,
  active,
  onClick,
  children,
}: {
  label: string;
  active?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onMouseDown={event => event.preventDefault()}
      onClick={onClick}
      className={cn(
        'flex h-8 w-8 items-center justify-center rounded-full text-muted-foreground',
        'transition-colors hover:bg-muted hover:text-foreground',
        active &&
          'bg-primary text-primary-foreground shadow-sm hover:bg-primary/90 hover:text-primary-foreground'
      )}
      aria-pressed={Boolean(active)}
      title={label}
    >
      {children}
    </button>
  );
}

function getToolbarState(editor: Editor): ToolbarState {
  return {
    h1: editor.isActive('heading', { level: 1 }),
    h2: editor.isActive('heading', { level: 2 }),
    h3: editor.isActive('heading', { level: 3 }),
    bold: editor.isActive('bold'),
    italic: editor.isActive('italic'),
    ul: editor.isActive('bulletList'),
    ol: editor.isActive('orderedList'),
    quote: editor.isActive('blockquote'),
    code: editor.isActive('codeBlock'),
    link: editor.isActive('link'),
  };
}

function markdownToHtml(markdown: string): string {
  return marked.parse(markdown, { async: false, gfm: true }) as string;
}

function htmlToMarkdown(html: string): string {
  return markdownConverter
    .turndown(html)
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}
