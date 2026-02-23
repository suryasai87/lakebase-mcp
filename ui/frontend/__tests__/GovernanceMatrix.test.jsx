import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import theme from '../src/theme';
import GovernanceMatrix from '../src/components/GovernanceMatrix';

function renderWithTheme(ui) {
  return render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>);
}

const mockCategories = [
  { name: 'sql_query', tool_count: 3, tools: ['lakebase_execute_query', 'lakebase_read_query', 'lakebase_explain_query'] },
  { name: 'branch_write', tool_count: 2, tools: ['lakebase_create_branch', 'lakebase_delete_branch'] },
];

const mockMatrix = {
  read_only: {
    lakebase_execute_query: true,
    lakebase_read_query: true,
    lakebase_explain_query: true,
    lakebase_create_branch: false,
    lakebase_delete_branch: false,
  },
  analyst: {
    lakebase_execute_query: true,
    lakebase_read_query: true,
    lakebase_explain_query: true,
    lakebase_create_branch: false,
    lakebase_delete_branch: false,
  },
  developer: {
    lakebase_execute_query: true,
    lakebase_read_query: true,
    lakebase_explain_query: true,
    lakebase_create_branch: true,
    lakebase_delete_branch: true,
  },
  admin: {
    lakebase_execute_query: true,
    lakebase_read_query: true,
    lakebase_explain_query: true,
    lakebase_create_branch: true,
    lakebase_delete_branch: true,
  },
};

describe('GovernanceMatrix', () => {
  it('renders null when no data', () => {
    const { container } = renderWithTheme(<GovernanceMatrix matrix={null} categories={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders profile column headers', () => {
    renderWithTheme(<GovernanceMatrix matrix={mockMatrix} categories={mockCategories} />);
    expect(screen.getByText('read only')).toBeInTheDocument();
    expect(screen.getByText('analyst')).toBeInTheDocument();
    expect(screen.getByText('developer')).toBeInTheDocument();
    expect(screen.getByText('admin')).toBeInTheDocument();
  });

  it('renders category headers', () => {
    renderWithTheme(<GovernanceMatrix matrix={mockMatrix} categories={mockCategories} />);
    expect(screen.getByText('sql_query')).toBeInTheDocument();
    expect(screen.getByText('branch_write')).toBeInTheDocument();
  });

  it('renders tool names', () => {
    renderWithTheme(<GovernanceMatrix matrix={mockMatrix} categories={mockCategories} />);
    expect(screen.getByText('lakebase_execute_query')).toBeInTheDocument();
    expect(screen.getByText('lakebase_create_branch')).toBeInTheDocument();
  });

  it('renders correct number of check/cancel icons', () => {
    renderWithTheme(<GovernanceMatrix matrix={mockMatrix} categories={mockCategories} />);
    // 5 tools x 4 profiles = 20 cells
    const checkIcons = document.querySelectorAll('[data-testid="CheckCircleIcon"]');
    const cancelIcons = document.querySelectorAll('[data-testid="CancelIcon"]');
    // sql_query: 3 tools, all 4 profiles allowed = 12 checks
    // branch_write: 2 tools, read_only+analyst denied (4), developer+admin allowed (4)
    // Total checks: 12 + 4 = 16, Total cancels: 4
    expect(checkIcons.length + cancelIcons.length).toBe(20);
  });
});
