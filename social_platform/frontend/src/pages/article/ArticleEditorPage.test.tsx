// @vitest-environment jsdom

/**
 * 文章编辑页表格交互的组件测试。
 *
 * 覆盖工具栏创建 2×2 表格、表格处于 contenteditable 编辑区，以及
 * 右边缘和下边缘按钮真实调用 TipTap 命令增减行列。
 */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import ArticleEditorPage from './ArticleEditorPage';

vi.mock('@/features/post', () => ({
  useCreatePost: () => ({ mutate: vi.fn(), isPending: false }),
}));

describe('ArticleEditorPage table controls', () => {
  it('创建可编辑 2×2 表格并通过边缘按钮增减行列', async () => {
    const { container } = render(
      <MemoryRouter>
        <ArticleEditorPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(container.querySelector('.ProseMirror')).not.toBeNull();
    });

    const insertTableButton = screen.getByTitle('插入表格');

    fireEvent.mouseDown(insertTableButton);
    fireEvent.click(insertTableButton);

    const table = await waitFor(() => {
      const currentTable = container.querySelector<HTMLTableElement>('table');

      expect(currentTable).not.toBeNull();
      return currentTable as HTMLTableElement;
    });

    expect(table.rows).toHaveLength(2);
    expect(Array.from(table.rows, row => row.cells.length)).toEqual([2, 2]);
    expect(table.closest('[contenteditable="true"]')).not.toBeNull();

    fireEvent.mouseMove(table);
    fireEvent.mouseDown(screen.getByLabelText('增加一列'));
    fireEvent.click(screen.getByLabelText('增加一列'));

    await waitFor(() => {
      expect(Array.from(table.rows, row => row.cells.length)).toEqual([3, 3]);
    });

    fireEvent.mouseDown(screen.getByLabelText('减少一列'));
    fireEvent.click(screen.getByLabelText('减少一列'));

    await waitFor(() => {
      expect(Array.from(table.rows, row => row.cells.length)).toEqual([2, 2]);
    });

    fireEvent.mouseDown(screen.getByLabelText('增加一行'));
    fireEvent.click(screen.getByLabelText('增加一行'));

    await waitFor(() => {
      expect(table.rows).toHaveLength(3);
    });

    fireEvent.mouseDown(screen.getByLabelText('减少一行'));
    fireEvent.click(screen.getByLabelText('减少一行'));

    await waitFor(() => {
      expect(table.rows).toHaveLength(2);
    });

    fireEvent.mouseDown(screen.getByLabelText('减少一行'));
    fireEvent.click(screen.getByLabelText('减少一行'));

    await waitFor(() => {
      expect(table.rows).toHaveLength(1);
      expect(screen.getByLabelText('减少一行')).not.toBeNull();
    });

    fireEvent.mouseDown(screen.getByLabelText('减少一行'));
    fireEvent.click(screen.getByLabelText('减少一行'));

    await waitFor(() => {
      expect(container.querySelector('table')).toBeNull();
    });

    const insertTableButtonAgain = screen.getByTitle('插入表格');

    fireEvent.mouseDown(insertTableButtonAgain);
    fireEvent.click(insertTableButtonAgain);

    const secondTable = await waitFor(() => {
      const currentTable = container.querySelector<HTMLTableElement>('table');

      expect(currentTable).not.toBeNull();
      return currentTable as HTMLTableElement;
    });

    fireEvent.mouseMove(secondTable);
    fireEvent.mouseDown(screen.getByLabelText('减少一列'));
    fireEvent.click(screen.getByLabelText('减少一列'));

    await waitFor(() => {
      expect(Array.from(secondTable.rows, row => row.cells.length)).toEqual([1, 1]);
      expect(screen.getByLabelText('减少一列')).not.toBeNull();
    });

    fireEvent.mouseDown(screen.getByLabelText('减少一列'));
    fireEvent.click(screen.getByLabelText('减少一列'));

    await waitFor(() => {
      expect(container.querySelector('table')).toBeNull();
    });
  });
});
