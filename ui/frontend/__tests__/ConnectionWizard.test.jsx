import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import theme from '../src/theme';
import ConnectionWizard from '../src/components/ConnectionWizard';

function renderWithTheme(ui) {
  return render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>);
}

describe('ConnectionWizard', () => {
  it('renders 3 step labels', () => {
    renderWithTheme(<ConnectionWizard />);
    expect(screen.getByText('Choose Profile')).toBeInTheDocument();
    expect(screen.getByText('Choose Client')).toBeInTheDocument();
    expect(screen.getByText('Configure & Connect')).toBeInTheDocument();
  });

  it('starts on step 0 with profile selector', () => {
    renderWithTheme(<ConnectionWizard />);
    expect(screen.getByText('Select a Governance Profile')).toBeInTheDocument();
  });

  it('navigates to step 1 when Next is clicked', () => {
    renderWithTheme(<ConnectionWizard />);
    fireEvent.click(screen.getByText('Next'));
    expect(screen.getByText('Select your MCP Client')).toBeInTheDocument();
  });

  it('navigates back to step 0 when Back is clicked', () => {
    renderWithTheme(<ConnectionWizard />);
    fireEvent.click(screen.getByText('Next'));
    fireEvent.click(screen.getByText('Back'));
    expect(screen.getByText('Select a Governance Profile')).toBeInTheDocument();
  });

  it('reaches step 2 with config output', () => {
    renderWithTheme(<ConnectionWizard />);
    fireEvent.click(screen.getByText('Next'));
    fireEvent.click(screen.getByText('Next'));
    // "Configure & Connect" appears in both stepper label and heading
    expect(screen.getAllByText('Configure & Connect').length).toBeGreaterThanOrEqual(1);
    // MUI TextField renders label text in multiple places
    expect(screen.getAllByText(/MCP Server URL/).length).toBeGreaterThanOrEqual(1);
  });

  it('Back button is disabled on step 0', () => {
    renderWithTheme(<ConnectionWizard />);
    expect(screen.getByText('Back')).toBeDisabled();
  });

  it('does not show Next button on last step', () => {
    renderWithTheme(<ConnectionWizard />);
    fireEvent.click(screen.getByText('Next'));
    fireEvent.click(screen.getByText('Next'));
    expect(screen.queryByText('Next')).toBeNull();
  });
});
