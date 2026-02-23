import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import theme from '../src/theme';
import CategoryAccordion from '../src/components/CategoryAccordion';

function renderWithTheme(ui) {
  return render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>);
}

const mockCategory = {
  name: 'sql_query',
  description: 'SQL query execution with governance controls',
  tool_count: 3,
  tools: ['lakebase_execute_query', 'lakebase_read_query', 'lakebase_explain_query'],
};

const mockTools = [
  {
    name: 'lakebase_execute_query',
    title: 'Execute SQL Query',
    category: 'sql_query',
    description: 'Execute a SQL query',
    readOnlyHint: false,
    destructiveHint: false,
    parameters: {},
  },
  {
    name: 'lakebase_read_query',
    title: 'Read Query',
    category: 'sql_query',
    description: 'Execute a read-only query',
    readOnlyHint: true,
    destructiveHint: false,
    parameters: {},
  },
  {
    name: 'lakebase_explain_query',
    title: 'Explain Query',
    category: 'sql_query',
    description: 'Get query plan',
    readOnlyHint: true,
    destructiveHint: false,
    parameters: {},
  },
];

describe('CategoryAccordion', () => {
  it('renders category name in the summary', () => {
    renderWithTheme(<CategoryAccordion category={mockCategory} tools={mockTools} />);
    // Category name appears in the AccordionSummary as a subtitle1
    const heading = screen.getByRole('button');
    expect(heading).toHaveTextContent('sql_query');
  });

  it('shows tool count badge', () => {
    renderWithTheme(<CategoryAccordion category={mockCategory} tools={mockTools} />);
    expect(screen.getByText('3 tools')).toBeInTheDocument();
  });

  it('shows category description', () => {
    renderWithTheme(<CategoryAccordion category={mockCategory} tools={mockTools} />);
    expect(screen.getByText('SQL query execution with governance controls')).toBeInTheDocument();
  });

  it('renders all tool names', () => {
    renderWithTheme(<CategoryAccordion category={mockCategory} tools={mockTools} />);
    expect(screen.getByText('lakebase_execute_query')).toBeInTheDocument();
    expect(screen.getByText('lakebase_read_query')).toBeInTheDocument();
    expect(screen.getByText('lakebase_explain_query')).toBeInTheDocument();
  });
});
