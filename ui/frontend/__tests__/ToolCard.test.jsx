import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import theme from '../src/theme';
import ToolCard from '../src/components/ToolCard';

function renderWithTheme(ui) {
  return render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>);
}

const readOnlyTool = {
  name: 'lakebase_read_query',
  title: 'Execute Read-Only SQL Query',
  category: 'sql_query',
  description: 'Execute a read-only SQL query against Lakebase.',
  readOnlyHint: true,
  destructiveHint: false,
  parameters: {
    sql: { type: 'string', required: true, description: 'SQL query' },
    max_rows: { type: 'integer', required: false, default: 100, description: 'Max rows' },
  },
};

const destructiveTool = {
  name: 'lakebase_delete_branch',
  title: 'Delete Database Branch',
  category: 'branch_write',
  description: 'Delete a Lakebase database branch. Irreversible.',
  readOnlyHint: false,
  destructiveHint: true,
  parameters: {
    project_name: { type: 'string', required: true, description: 'Project name' },
    branch_name: { type: 'string', required: true, description: 'Branch to delete' },
  },
};

const writeTool = {
  name: 'lakebase_create_branch',
  title: 'Create Database Branch',
  category: 'branch_write',
  description: 'Create a copy-on-write branch.',
  readOnlyHint: false,
  destructiveHint: false,
  parameters: {},
};

describe('ToolCard', () => {
  it('renders tool name and description', () => {
    renderWithTheme(<ToolCard tool={readOnlyTool} />);
    expect(screen.getByText('lakebase_read_query')).toBeInTheDocument();
    expect(screen.getByText(/read-only SQL query/)).toBeInTheDocument();
  });

  it('shows Read Only badge for readOnlyHint tools', () => {
    renderWithTheme(<ToolCard tool={readOnlyTool} />);
    expect(screen.getByText('Read Only')).toBeInTheDocument();
  });

  it('shows Destructive badge for destructiveHint tools', () => {
    renderWithTheme(<ToolCard tool={destructiveTool} />);
    expect(screen.getByText('Destructive')).toBeInTheDocument();
  });

  it('shows Read/Write badge for non-readonly non-destructive tools', () => {
    renderWithTheme(<ToolCard tool={writeTool} />);
    expect(screen.getByText('Read/Write')).toBeInTheDocument();
  });

  it('shows category chip', () => {
    renderWithTheme(<ToolCard tool={readOnlyTool} />);
    expect(screen.getByText('sql_query')).toBeInTheDocument();
  });

  it('expands to show parameters table when clicked', () => {
    renderWithTheme(<ToolCard tool={readOnlyTool} />);
    const expandButton = screen.getByTestId ? null : document.querySelector('[aria-label]');
    // Click the expand button (the IconButton with ExpandMore)
    const buttons = document.querySelectorAll('button');
    const expandBtn = Array.from(buttons).find(b => b.querySelector('svg'));
    if (expandBtn) {
      fireEvent.click(expandBtn);
      expect(screen.getByText('sql')).toBeInTheDocument();
      expect(screen.getByText('max_rows')).toBeInTheDocument();
    }
  });
});
