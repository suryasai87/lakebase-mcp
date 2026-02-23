import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import theme from '../src/theme';
import ProfileSelector from '../src/components/ProfileSelector';

function renderWithTheme(ui) {
  return render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>);
}

describe('ProfileSelector', () => {
  it('renders a combobox', () => {
    renderWithTheme(<ProfileSelector value="read_only" onChange={() => {}} />);
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('renders the label text', () => {
    renderWithTheme(<ProfileSelector value="read_only" onChange={() => {}} />);
    // MUI renders label in both <label> and <legend><span>
    expect(screen.getAllByText('Governance Profile').length).toBeGreaterThanOrEqual(1);
  });

  it('renders custom label text', () => {
    renderWithTheme(<ProfileSelector value="read_only" onChange={() => {}} label="SQL Profile" />);
    expect(screen.getAllByText('SQL Profile').length).toBeGreaterThanOrEqual(1);
  });

  it('calls onChange when selection changes', () => {
    const onChange = vi.fn();
    renderWithTheme(<ProfileSelector value="read_only" onChange={onChange} />);
    const select = screen.getByRole('combobox');
    fireEvent.mouseDown(select);
    const option = screen.getByText('developer');
    fireEvent.click(option);
    expect(onChange).toHaveBeenCalledWith('developer');
  });

  it('shows all 4 profile options when opened', () => {
    renderWithTheme(<ProfileSelector value="read_only" onChange={() => {}} />);
    const select = screen.getByRole('combobox');
    fireEvent.mouseDown(select);
    expect(screen.getAllByText('read_only').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('analyst')).toBeInTheDocument();
    expect(screen.getByText('developer')).toBeInTheDocument();
    expect(screen.getByText('admin')).toBeInTheDocument();
  });
});
