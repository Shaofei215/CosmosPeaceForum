import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from 'react';
import { getMarkRange, getMarkType, type Editor } from '@tiptap/core';
import { EditorContent, useEditor } from '@tiptap/react';
import LinkExtension from '@tiptap/extension-link';
import Placeholder from '@tiptap/extension-placeholder';
import StarterKit from '@tiptap/starter-kit';
import TurndownService from 'turndown';
import { useNavigate } from 'react-router-dom';
import {
  Bold,
  Code2,
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
import { Button, Input } from '@/shared/components/ui';
import { ARTICLE_CONTENT_MAX_LENGTH } from '@/shared/config/contentLimits';
import { hasVisibleContent } from '@/shared/lib/content';
import { normalizeLinkHref } from '@/shared/lib/externalRedirect';
import { cn } from '@/shared/lib/utils';

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

interface LinkDialogState {
  open: boolean;
  text: string;
  href: string;
  top: number;
  left: number;
}

interface PendingLinkSelection {
  from: number;
  to: number;
}

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

const emptyLinkDialogState: LinkDialogState = {
  open: false,
  text: '',
  href: '',
  top: 0,
  left: 0,
};

const text = {
  titlePlaceholder: '\u6587\u7ae0\u6807\u9898',
  editorPlaceholder: '支持 Markdown 输入哦~',
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
  linkTextLabel: '\u94fe\u63a5\u63cf\u8ff0',
  linkTextPlaceholder: '\u663e\u793a\u7ed9\u8bfb\u8005\u7684\u6587\u5b57',
  linkHrefLabel: '\u94fe\u63a5\u5730\u5740',
  linkHrefPlaceholder: 'https://example.com',
  linkAdd: '\u6dfb\u52a0',
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
  const editorRef = useRef<Editor | null>(null);
  const pendingLinkSelectionRef = useRef<PendingLinkSelection | null>(null);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [toolbarState, setToolbarState] = useState<ToolbarState>(emptyToolbarState);
  const [linkDialog, setLinkDialog] = useState<LinkDialogState>(emptyLinkDialogState);
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
      handleDOMEvents: {
        mousedown: (_view, event) => handleRichEditorLinkPointer(event),
        click: (_view, event) => handleRichEditorLinkPointer(event),
        keydown: (_view, event) => handleRichEditorKeyDown(event),
      },
    },
    onUpdate({ editor: currentEditor }) {
      const nextContent = htmlToMarkdown(currentEditor.getHTML());
      if (nextContent.length > ARTICLE_CONTENT_MAX_LENGTH) {
        currentEditor.commands.undo();
        return;
      }
      setContent(nextContent);
    },
  });
  editorRef.current = editor;

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

  const currentMarkdown = editor ? htmlToMarkdown(editor.getHTML()) : content;
  const canPublish = hasVisibleContent(title) && hasVisibleContent(currentMarkdown);

  const submitArticle = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const nextContent = editor ? htmlToMarkdown(editor.getHTML()) : content;
    if (!hasVisibleContent(title) || !hasVisibleContent(nextContent) || isPending) return;

    if (nextContent.length > ARTICLE_CONTENT_MAX_LENGTH) return;
    setContent(nextContent);
    createPost(
      {
        title: title.trim(),
        type: 'article',
        content: nextContent,
      },
      {
        onSuccess: post => {
          navigate(`/post/${post.id}`);
        },
      }
    );
  };

  const applyStyle = (style: ToolbarAction) => {
    if (style === 'link') {
      openLinkDialog();
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
  };

  /**
   * 打开链接编辑弹窗，并记录当前选区用于确认后插入链接。
   */
  const openLinkDialog = (): void => {
    if (!editor) return;

    if (editor.isActive('link')) {
      editor.chain().focus().extendMarkRange('link').run();
    }

    const { from, to } = editor.state.selection;
    const previousHref = editor.getAttributes('link').href as string | undefined;
    const selectedText = editor.state.doc.textBetween(from, to, ' ');
    const position = getRichEditorCaretPosition(editor);
    pendingLinkSelectionRef.current = { from, to };
    setLinkDialog({
      open: true,
      text: selectedText,
      href: previousHref || '',
      ...position,
    });
  };

  /**
   * 点击富文本内已有链接时打开编辑条，而不是跳转。
   *
   * @param event 富文本编辑器 DOM 指针事件。
   * @returns true 表示事件已由链接编辑逻辑处理。
   */
  function handleRichEditorLinkPointer(event: MouseEvent): boolean {
    const currentEditor = editorRef.current;

    if (!currentEditor || !(event.target instanceof Element)) {
      return false;
    }

    const linkElement = event.target.closest<HTMLAnchorElement>('a');

    if (!linkElement || !currentEditor.view.dom.contains(linkElement)) {
      closeLinkDialog();
      return false;
    }

    event.preventDefault();
    event.stopPropagation();

    const position = currentEditor.view.posAtCoords({ left: event.clientX, top: event.clientY });

    if (!position) {
      return true;
    }

    currentEditor.chain().focus().setTextSelection(position.pos).extendMarkRange('link').run();

    const { from, to } = currentEditor.state.selection;

    pendingLinkSelectionRef.current = { from, to };
    setLinkDialog({
      open: true,
      text: currentEditor.state.doc.textBetween(from, to, ' '),
      href: linkElement.getAttribute('href') || '',
      ...normalizeLinkBarPosition({
        top: linkElement.getBoundingClientRect().bottom + 8,
        left: linkElement.getBoundingClientRect().left,
      }),
    });

    return true;
  }

  /**
   * 在富文本链接内按退格时删除整段链接文本。
   *
   * @param event 富文本编辑器键盘事件。
   * @returns true 表示事件已由链接删除逻辑处理。
   */
  function handleRichEditorKeyDown(event: KeyboardEvent): boolean {
    const currentEditor = editorRef.current;

    if (!currentEditor || event.key !== 'Backspace') {
      return false;
    }

    const linkRange = getCurrentLinkRange(currentEditor);

    if (!linkRange) {
      return false;
    }

    event.preventDefault();
    closeLinkDialog();
    currentEditor
      .chain()
      .focus()
      .deleteRange(linkRange)
      .setTextSelection(linkRange.from)
      .unsetMark('link')
      .run();

    return true;
  }

  /**
   * 关闭链接弹窗，并清理暂存选区。
   */
  const closeLinkDialog = (): void => {
    pendingLinkSelectionRef.current = null;
    setLinkDialog(emptyLinkDialogState);
  };

  /**
   * 根据链接编辑条输入在当前编辑模式中插入链接。
   */
  const submitLinkDialog = (): void => {
    const href = linkDialog.href.trim();
    if (!href) return;

    const normalizedHref = normalizeLinkHref(href);
    const linkText = linkDialog.text.trim() || normalizedHref;
    const selection = pendingLinkSelectionRef.current;

    if (!selection) return;

    editor
      ?.chain()
      .focus()
      .setTextSelection({ from: selection.from, to: selection.to })
      .insertContent({
        type: 'text',
        text: linkText,
        marks: [
          {
            type: 'link',
            attrs: { href: normalizedHref },
          },
        ],
      })
      .run();
    editor
      ?.chain()
      .focus()
      .setTextSelection(selection.from + linkText.length)
      .unsetMark('link')
      .run();
    closeLinkDialog();
  };

  /**
   * 处理链接编辑条键盘操作。
   *
   * @param event 链接编辑条键盘事件。
   */
  const handleLinkBarKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>): void => {
    if (event.key === 'Escape') {
      event.preventDefault();
      closeLinkDialog();
      return;
    }

    if (event.key === 'Enter') {
      event.preventDefault();
      submitLinkDialog();
    }
  };

  const linkBarStyle: CSSProperties = {
    top: linkDialog.top,
    left: linkDialog.left,
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
          'article-editor-toolbar flex h-10 max-h-10 flex-nowrap items-center gap-1 overflow-x-auto overflow-y-hidden',
          'border-b border-border/60 bg-white px-2 py-1 sm:px-3'
        )}
      >
        <ToolbarButton label={text.h1} active={toolbarState.h1} onClick={() => applyStyle('h1')}>
          <Heading1 className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton label={text.h2} active={toolbarState.h2} onClick={() => applyStyle('h2')}>
          <Heading2 className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton label={text.h3} active={toolbarState.h3} onClick={() => applyStyle('h3')}>
          <Heading3 className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton
          label={text.bold}
          active={toolbarState.bold}
          onClick={() => applyStyle('bold')}
        >
          <Bold className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton
          label={text.italic}
          active={toolbarState.italic}
          onClick={() => applyStyle('italic')}
        >
          <Italic className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton
          label={text.unorderedList}
          active={toolbarState.ul}
          onClick={() => applyStyle('ul')}
        >
          <List className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton
          label={text.orderedList}
          active={toolbarState.ol}
          onClick={() => applyStyle('ol')}
        >
          <ListOrdered className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton
          label={text.quote}
          active={toolbarState.quote}
          onClick={() => applyStyle('quote')}
        >
          <Quote className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton
          label={text.codeBlock}
          active={toolbarState.code}
          onClick={() => applyStyle('code')}
        >
          <Code2 className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton
          label={text.link}
          active={toolbarState.link}
          onClick={() => applyStyle('link')}
        >
          <LinkIcon className="h-4 w-4" />
        </ToolbarButton>
      </div>

      <EditorContent
        editor={editor}
        className="article-rich-editor min-h-[420px] px-4 py-4 sm:min-h-[560px] sm:px-6 sm:py-6"
      />

      <div className="flex items-center justify-end gap-2 border-t border-border/60 px-3 py-3 sm:px-4">
        <Button type="button" variant="ghost" onClick={() => navigate(-1)}>
          {text.cancel}
        </Button>
        <Button type="submit" disabled={!canPublish || isPending}>
          {isPending ? text.publishing : text.publish}
        </Button>
      </div>

      {linkDialog.open && (
        <div
          className="article-link-bar fixed z-50 flex w-[min(34rem,calc(100vw-1rem))] items-center gap-2 rounded-full border border-border bg-white p-1.5 shadow-xl"
          style={linkBarStyle}
          onKeyDown={handleLinkBarKeyDown}
        >
          <Input
            value={linkDialog.text}
            onChange={event => setLinkDialog(current => ({ ...current, text: event.target.value }))}
            placeholder={text.linkTextPlaceholder}
            aria-label={text.linkTextLabel}
            className="h-8 min-w-0 flex-1 rounded-full text-sm"
            autoFocus
          />
          <Input
            value={linkDialog.href}
            onChange={event => setLinkDialog(current => ({ ...current, href: event.target.value }))}
            placeholder={text.linkHrefPlaceholder}
            aria-label={text.linkHrefLabel}
            className="h-8 min-w-0 flex-[1.2] rounded-full text-sm"
          />
          <Button
            type="button"
            size="sm"
            onClick={submitLinkDialog}
            disabled={!linkDialog.href.trim()}
          >
            {text.linkAdd}
          </Button>
        </div>
      )}
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
        'flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-transparent text-muted-foreground',
        'transition-colors hover:bg-zinc-100/80 hover:text-zinc-950',
        active &&
          'border-zinc-950 bg-zinc-950 text-white shadow-sm hover:bg-zinc-950 hover:text-white hover:opacity-90'
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
    link: isSelectionInsideLinkText(editor),
  };
}

function htmlToMarkdown(html: string): string {
  return markdownConverter
    .turndown(html)
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

/**
 * 计算富文本编辑器当前选区附近的链接编辑条位置。
 *
 * @param editor TipTap 编辑器实例。
 * @returns 固定定位坐标。
 */
function getRichEditorCaretPosition(editor: Editor): Pick<LinkDialogState, 'top' | 'left'> {
  const { from } = editor.state.selection;
  const rect = editor.view.coordsAtPos(from);

  return normalizeLinkBarPosition({
    top: rect.bottom + 8,
    left: rect.left,
  });
}

/**
 * 将链接编辑条坐标限制在视口内。
 *
 * @param position 原始定位坐标。
 * @returns 不会明显溢出视口的定位坐标。
 */
function normalizeLinkBarPosition(
  position: Pick<LinkDialogState, 'top' | 'left'>
): Pick<LinkDialogState, 'top' | 'left'> {
  const barWidth = 544;
  const padding = 8;

  if (typeof window === 'undefined') {
    return position;
  }

  return {
    top: Math.max(padding, Math.min(position.top, window.innerHeight - 64)),
    left: Math.max(padding, Math.min(position.left, window.innerWidth - barWidth - padding)),
  };
}

/**
 * 获取当前选区所在的链接范围，用于整段编辑或删除链接。
 *
 * @param editor TipTap 编辑器实例。
 * @returns 链接范围；当前不在链接中时返回 null。
 */
function getCurrentLinkRange(editor: Editor): { from: number; to: number } | null {
  const linkType = getMarkType('link', editor.state.schema);
  const { selection } = editor.state;

  if (!selection.empty) {
    return editor.isActive('link') ? { from: selection.from, to: selection.to } : null;
  }

  const currentRange = getMarkRange(selection.$from, linkType);

  if (currentRange) {
    return currentRange;
  }

  if (selection.from <= 0) {
    return null;
  }

  const beforeCursor = editor.state.doc.resolve(selection.from - 1);

  return getMarkRange(beforeCursor, linkType) ?? null;
}

/**
 * 判断选区是否实际位于链接文本内部。
 *
 * @param editor TipTap 编辑器实例。
 * @returns 选中链接或光标在链接文本内部时返回 true。
 */
function isSelectionInsideLinkText(editor: Editor): boolean {
  const linkType = getMarkType('link', editor.state.schema);
  const { selection } = editor.state;

  if (!selection.empty) {
    return editor.isActive('link');
  }

  const range = getMarkRange(selection.$from, linkType);

  if (!range) {
    return false;
  }

  return selection.from > range.from && selection.from < range.to;
}
