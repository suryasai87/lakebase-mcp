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

const mockModelPricing = {
  models: [
    { id: 'claude-opus-4-6', name: 'Claude Opus 4.6', input_per_mtok: 5.0, output_per_mtok: 25.0, cache_write: 6.25, cache_hit: 0.50 },
    { id: 'claude-sonnet-4-6', name: 'Claude Sonnet 4.6', input_per_mtok: 3.0, output_per_mtok: 15.0, cache_write: 3.75, cache_hit: 0.30 },
    { id: 'claude-haiku-4-5', name: 'Claude Haiku 4.5', input_per_mtok: 1.0, output_per_mtok: 5.0, cache_write: 1.25, cache_hit: 0.10 },
  ],
  tool_overhead_tokens: 6000,
  system_prompt_overhead: 346,
  avg_input_per_call: 5000,
  avg_output_per_call: 1000,
};

const mockComputePricing = {
  regions: [
    { id: 'us-east-1', name: 'US East (N. Virginia)', dbu_rate: 0.70 },
    { id: 'us-west-2', name: 'US West (Oregon)', dbu_rate: 0.70 },
  ],
  compute_units: [
    { cu: 0.5, ram_gb: 1, dbu_per_hour: 0.5 },
    { cu: 1, ram_gb: 2, dbu_per_hour: 1.0 },
  ],
  storage_per_gb_month: 0.023,
};

const mockComparisonPricing = {
  platforms: [
    {
      name: 'Lakebase', provider: 'Databricks', min_compute_hr: 0.35,
      session_cost_8_calls: 0.42, monthly_prod: 365, branching: 'Free (copy-on-write)',
      scale_to_zero: true, mcp_tools: 31, governance_layers: 2,
      highlights: ['10-15x cheaper compute', 'Free instant branching'],
    },
    {
      name: 'Snowflake', provider: 'Snowflake', min_compute_hr: 3.00,
      session_cost_8_calls: 1.05, monthly_prod: 8640, branching: 'N/A (clone = full cost)',
      scale_to_zero: true, mcp_tools: 15, governance_layers: 1,
      highlights: ['Managed MCP server'],
    },
    {
      name: 'Teradata', provider: 'Teradata', min_compute_hr: 4.80,
      session_cost_8_calls: 1.05, monthly_prod: 5184, branching: 'N/A',
      scale_to_zero: false, mcp_tools: 100, governance_layers: 1,
      highlights: ['100+ tools'],
    },
  ],
};

beforeEach(() => {
  global.fetch = vi.fn((url) => {
    let data = {};
    if (url.includes('/pricing/models')) data = mockModelPricing;
    else if (url.includes('/pricing/compute')) data = mockComputePricing;
    else if (url.includes('/pricing/comparison')) data = mockComparisonPricing;
    else data = { tools: [], categories: [], count: 0, types: [], profiles: {}, variables: [], prompts: [], resources: [] };
    return Promise.resolve({ ok: true, json: () => Promise.resolve(data) });
  });
});

describe('PricingCalculator', () => {
  it('renders pricing page title on /pricing route', async () => {
    renderApp('/pricing');
    await waitFor(() => {
      expect(screen.getByText('Pricing Calculator')).toBeInTheDocument();
    });
  });

  it('renders Token Cost Calculator section heading', async () => {
    renderApp('/pricing');
    await waitFor(() => {
      expect(screen.getByText('Token Cost Calculator')).toBeInTheDocument();
    });
  });

  it('renders Compute Cost Estimator section heading', async () => {
    renderApp('/pricing');
    await waitFor(() => {
      expect(screen.getByText('Compute Cost Estimator')).toBeInTheDocument();
    });
  });

  it('renders Storage Cost Estimator section heading', async () => {
    renderApp('/pricing');
    await waitFor(() => {
      expect(screen.getByText('Storage Cost Estimator')).toBeInTheDocument();
    });
  });

  it('renders 3 competitive comparison platform names', async () => {
    renderApp('/pricing');
    await waitFor(() => {
      expect(screen.getAllByText('Lakebase').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Snowflake').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Teradata').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('renders cost optimization tips', async () => {
    renderApp('/pricing');
    await waitFor(() => {
      expect(screen.getByText(/prompt caching/i)).toBeInTheDocument();
    });
  });

  it('renders Pricing nav item in sidebar', async () => {
    renderApp('/pricing');
    expect(screen.getAllByText('Pricing').length).toBeGreaterThanOrEqual(1);
  });

  it('shows branches-are-free note in storage section', async () => {
    renderApp('/pricing');
    await waitFor(() => {
      expect(screen.getByText(/branches are free/i)).toBeInTheDocument();
    });
  });

  it('renders model selector with at least one combobox', async () => {
    renderApp('/pricing');
    await waitFor(() => {
      expect(screen.getByText('Pricing Calculator')).toBeInTheDocument();
    });
    const selects = document.querySelectorAll('[role="combobox"]');
    expect(selects.length).toBeGreaterThanOrEqual(1);
  });

  it('renders Total Monthly Estimate section', async () => {
    renderApp('/pricing');
    await waitFor(() => {
      expect(screen.getByText('Total Monthly Estimate')).toBeInTheDocument();
    });
  });
});
