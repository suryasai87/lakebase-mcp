import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { MemoryRouter } from 'react-router-dom';
import theme from '../src/theme';
import App from '../src/App';

function renderApp(initialRoute = '/') {
  return render(
    <ThemeProvider theme={theme}>
      <MemoryRouter initialEntries={[initialRoute]}>
        <App />
      </MemoryRouter>
    </ThemeProvider>
  );
}

beforeEach(() => {
  global.fetch = vi.fn((url) => {
    let data = {};
    if (url.includes('/pricing/models')) {
      data = { models: [{ id: 'claude-sonnet-4-6', name: 'Claude Sonnet 4.6', input_per_mtok: 3, output_per_mtok: 15, cache_write: 3.75, cache_hit: 0.30 }], tool_overhead_tokens: 6000, system_prompt_overhead: 346, avg_input_per_call: 5000, avg_output_per_call: 1000 };
    } else if (url.includes('/pricing/compute')) {
      data = { regions: [{ id: 'us-east-1', name: 'US East', dbu_rate: 0.70 }], compute_units: [{ cu: 1, ram_gb: 2, dbu_per_hour: 1.0 }], storage_per_gb_month: 0.023 };
    } else if (url.includes('/pricing/comparison')) {
      data = { platforms: [{ name: 'Lakebase', provider: 'Databricks', min_compute_hr: 0.35, session_cost_8_calls: 0.42, monthly_prod: 365, branching: 'Free', scale_to_zero: true, mcp_tools: 31, governance_layers: 2, highlights: [] }] };
    } else {
      data = { tools: [], categories: [], count: 0, types: [], profiles: {}, variables: [], prompts: [], resources: [] };
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(data) });
  });
});

describe('App', () => {
  it('renders the app bar title', () => {
    renderApp();
    expect(screen.getAllByText('Lakebase MCP Server').length).toBeGreaterThanOrEqual(1);
  });

  it('renders navigation items', () => {
    renderApp();
    expect(screen.getAllByText('Home').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Tools').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Connect').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Governance').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Pricing').length).toBeGreaterThanOrEqual(1);
  });

  it('renders Home page content on / route', () => {
    renderApp('/');
    expect(screen.getByText('Quick Links')).toBeInTheDocument();
  });

  it('renders Tool Explorer on /tools route', async () => {
    renderApp('/tools');
    await waitFor(() => {
      expect(screen.getByText('Tool Explorer')).toBeInTheDocument();
    });
  });

  it('renders Connection Setup on /connect route', () => {
    renderApp('/connect');
    expect(screen.getByText('Connect to Lakebase MCP')).toBeInTheDocument();
  });

  it('renders Governance Dashboard on /governance route', async () => {
    renderApp('/governance');
    await waitFor(() => {
      expect(screen.getByText('Governance Dashboard')).toBeInTheDocument();
    });
  });

  it('renders Pricing Calculator on /pricing route', async () => {
    renderApp('/pricing');
    await waitFor(() => {
      expect(screen.getByText('Pricing Calculator')).toBeInTheDocument();
    });
  });
});
