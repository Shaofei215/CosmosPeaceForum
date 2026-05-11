import ReactMarkdown, { type Components } from 'react-markdown';
import { Link } from 'react-router-dom';
import remarkGfm from 'remark-gfm';
import { cn } from '@/shared/lib/utils';

interface MarkdownRendererProps {
  content: string;
  compact?: boolean;
  className?: string;
}

export function MarkdownRenderer({ content, compact = false, className }: MarkdownRendererProps) {
  return (
    <div
      className={cn(
        'markdown-body min-w-0 break-words text-foreground/90',
        compact && 'markdown-body-compact text-sm',
        className
      )}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={markdownComponents}>
        {content}
      </ReactMarkdown>
    </div>
  );
}

export function stripMarkdown(content: string): string {
  return content
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/^\s{0,3}#{1,6}\s+/gm, '')
    .replace(/^\s{0,3}>\s?/gm, '')
    .replace(/^\s*[-*+]\s+/gm, '')
    .replace(/^\s*\d+\.\s+/gm, '')
    .replace(/[*_~|`>#-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

const markdownComponents: Components = {
  a({ href, children }) {
    if (href?.startsWith('/')) {
      return (
        <Link to={href} className="font-medium text-primary hover:text-primary/80">
          {children}
        </Link>
      );
    }

    return (
      <a
        href={href}
        target="_blank"
        rel="noreferrer"
        className="font-medium text-primary hover:text-primary/80"
      >
        {children}
      </a>
    );
  },
  h1({ children }) {
    return <h1 className="text-2xl font-semibold leading-9 text-foreground">{children}</h1>;
  },
  h2({ children }) {
    return <h2 className="text-xl font-semibold leading-8 text-foreground">{children}</h2>;
  },
  h3({ children }) {
    return <h3 className="text-lg font-semibold leading-7 text-foreground">{children}</h3>;
  },
  h4({ children }) {
    return <h4 className="text-base font-semibold leading-7 text-foreground">{children}</h4>;
  },
  h5({ children }) {
    return <h5 className="text-sm font-semibold leading-6 text-foreground">{children}</h5>;
  },
  h6({ children }) {
    return <h6 className="text-sm font-semibold leading-6 text-muted-foreground">{children}</h6>;
  },
  p({ children }) {
    return <p className="whitespace-pre-wrap">{children}</p>;
  },
  blockquote({ children }) {
    return (
      <blockquote className="border-l-2 border-primary/40 pl-3 text-muted-foreground">
        {children}
      </blockquote>
    );
  },
  ul({ children }) {
    return <ul className="ml-5 list-disc space-y-1">{children}</ul>;
  },
  ol({ children }) {
    return <ol className="ml-5 list-decimal space-y-1">{children}</ol>;
  },
  code({ children, className }) {
    return <code className={cn('font-mono text-[0.92em]', className)}>{children}</code>;
  },
  pre({ children }) {
    return (
      <pre className="overflow-x-auto rounded-md bg-muted px-3 py-2 text-sm leading-6">
        {children}
      </pre>
    );
  },
  table({ children }) {
    return (
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">{children}</table>
      </div>
    );
  },
  th({ children }) {
    return (
      <th className="border border-border bg-muted px-2 py-1 text-left font-semibold">
        {children}
      </th>
    );
  },
  td({ children }) {
    return <td className="border border-border px-2 py-1 align-top">{children}</td>;
  },
};
