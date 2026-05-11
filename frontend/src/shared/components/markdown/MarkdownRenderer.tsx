import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { cn } from '@/shared/lib/utils';

interface MarkdownRendererProps {
  content: string;
  compact?: boolean;
  className?: string;
}

type Block =
  | { type: 'heading'; level: number; text: string }
  | { type: 'quote'; text: string }
  | { type: 'ul'; items: string[] }
  | { type: 'ol'; items: string[] }
  | { type: 'code'; text: string }
  | { type: 'paragraph'; text: string };

export function MarkdownRenderer({ content, compact = false, className }: MarkdownRendererProps) {
  const blocks = parseBlocks(content);

  return (
    <div
      className={cn(
        'markdown-body min-w-0 break-words text-foreground/90',
        compact ? 'space-y-1.5 text-sm' : 'space-y-4 text-[15px] leading-7',
        className,
      )}
    >
      {blocks.map((block, index) => renderBlock(block, index, compact))}
    </div>
  );
}

export function stripMarkdown(content: string): string {
  return content
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/!\[[^\]]*\]\([^)]+\)/g, ' ')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/^[#>\-\*\+\d.\s]+/gm, '')
    .replace(/[*_~]+/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function parseBlocks(content: string): Block[] {
  const lines = content.replace(/\r\n/g, '\n').split('\n');
  const blocks: Block[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }

    if (line.trim().startsWith('```')) {
      const codeLines: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith('```')) {
        codeLines.push(lines[index]);
        index += 1;
      }
      blocks.push({ type: 'code', text: codeLines.join('\n') });
      index += 1;
      continue;
    }

    const heading = /^(#{1,6})\s+(.+)$/.exec(line);
    if (heading) {
      blocks.push({ type: 'heading', level: heading[1].length, text: heading[2] });
      index += 1;
      continue;
    }

    if (/^\s*>\s?/.test(line)) {
      const quoteLines: string[] = [];
      while (index < lines.length && /^\s*>\s?/.test(lines[index])) {
        quoteLines.push(lines[index].replace(/^\s*>\s?/, ''));
        index += 1;
      }
      blocks.push({ type: 'quote', text: quoteLines.join('\n') });
      continue;
    }

    if (/^\s*[-*+]\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^\s*[-*+]\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*[-*+]\s+/, ''));
        index += 1;
      }
      blocks.push({ type: 'ul', items });
      continue;
    }

    if (/^\s*\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^\s*\d+\.\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*\d+\.\s+/, ''));
        index += 1;
      }
      blocks.push({ type: 'ol', items });
      continue;
    }

    const paragraphLines = [line];
    index += 1;
    while (
      index < lines.length &&
      lines[index].trim() &&
      !/^(#{1,6})\s+/.test(lines[index]) &&
      !/^\s*>\s?/.test(lines[index]) &&
      !/^\s*[-*+]\s+/.test(lines[index]) &&
      !/^\s*\d+\.\s+/.test(lines[index]) &&
      !lines[index].trim().startsWith('```')
    ) {
      paragraphLines.push(lines[index]);
      index += 1;
    }
    blocks.push({ type: 'paragraph', text: paragraphLines.join('\n') });
  }

  return blocks;
}

function renderBlock(block: Block, index: number, compact: boolean) {
  if (block.type === 'heading') {
    const Tag = `h${Math.min(block.level, 3)}` as 'h1' | 'h2' | 'h3';
    return (
      <Tag
        key={index}
        className={cn(
          'font-semibold text-foreground',
          compact && 'line-clamp-2',
          !compact && block.level === 1 && 'text-2xl leading-9',
          !compact && block.level === 2 && 'text-xl leading-8',
          !compact && block.level >= 3 && 'text-lg leading-7',
        )}
      >
        {renderInline(block.text)}
      </Tag>
    );
  }

  if (block.type === 'quote') {
    return (
      <blockquote
        key={index}
        className="border-l-2 border-primary/40 pl-3 text-muted-foreground"
      >
        {renderInline(block.text)}
      </blockquote>
    );
  }

  if (block.type === 'ul' || block.type === 'ol') {
    const Tag = block.type;
    return (
      <Tag key={index} className={cn('ml-5 space-y-1', block.type === 'ul' ? 'list-disc' : 'list-decimal')}>
        {block.items.map((item, itemIndex) => (
          <li key={`${item}-${itemIndex}`}>{renderInline(item)}</li>
        ))}
      </Tag>
    );
  }

  if (block.type === 'code') {
    return (
      <pre key={index} className="overflow-x-auto rounded-md bg-muted px-3 py-2 text-sm leading-6">
        <code>{block.text}</code>
      </pre>
    );
  }

  return (
    <p key={index} className={cn('whitespace-pre-wrap', compact && 'line-clamp-3')}>
      {renderInline(block.text)}
    </p>
  );
}

function renderInline(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_|\[[^\]]+\]\([^)]+\))/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > cursor) {
      nodes.push(text.slice(cursor, match.index));
    }

    const token = match[0];
    const key = `${token}-${match.index}`;
    if (token.startsWith('`')) {
      nodes.push(
        <code key={key} className="rounded bg-muted px-1 py-0.5 text-[0.92em]">
          {token.slice(1, -1)}
        </code>,
      );
    } else if (token.startsWith('**') || token.startsWith('__')) {
      nodes.push(<strong key={key}>{token.slice(2, -2)}</strong>);
    } else if (token.startsWith('*') || token.startsWith('_')) {
      nodes.push(<em key={key}>{token.slice(1, -1)}</em>);
    } else {
      const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(token);
      if (link) {
        nodes.push(renderLink(link[1], link[2], key));
      }
    }

    cursor = match.index + token.length;
  }

  if (cursor < text.length) {
    nodes.push(text.slice(cursor));
  }

  return nodes;
}

function renderLink(label: string, href: string, key: string) {
  if (href.startsWith('/')) {
    return (
      <Link key={key} to={href} className="font-medium text-primary hover:text-primary/80">
        {label}
      </Link>
    );
  }

  return (
    <a
      key={key}
      href={href}
      target="_blank"
      rel="noreferrer"
      className="font-medium text-primary hover:text-primary/80"
    >
      {label}
    </a>
  );
}
