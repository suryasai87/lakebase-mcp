import { useState, useMemo } from 'react';
import {
  Typography, Box, Card, CardContent, Grid, CircularProgress, Alert,
  FormControl, InputLabel, Select, MenuItem, TextField, Slider, Stack,
  Chip, Divider, Paper, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow,
} from '@mui/material';
import {
  TipsAndUpdates as TipIcon,
  CheckCircle, Cancel,
} from '@mui/icons-material';
import { motion } from 'framer-motion';
import useApi from '../hooks/useApi';

const containerVariants = {
  animate: { transition: { staggerChildren: 0.08 } },
};

const itemVariants = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

function formatUSD(value) {
  if (value < 0.01) return `$${value.toFixed(4)}`;
  if (value < 1) return `$${value.toFixed(3)}`;
  return `$${value.toFixed(2)}`;
}

export default function PricingCalculator() {
  const { data: modelData, loading: modelLoading, error: modelError } = useApi('/pricing/models');
  const { data: computeData, loading: computeLoading } = useApi('/pricing/compute');
  const { data: comparisonData, loading: comparisonLoading } = useApi('/pricing/comparison');

  // Token calculator state
  const [selectedModel, setSelectedModel] = useState('claude-sonnet-4-6');
  const [toolCalls, setToolCalls] = useState(10);

  // Compute estimator state
  const [selectedCU, setSelectedCU] = useState(1);
  const [selectedRegion, setSelectedRegion] = useState('us-east-1');
  const [usagePattern, setUsagePattern] = useState('scale-to-zero');
  const [hoursPerDay, setHoursPerDay] = useState(8);

  // Storage estimator state
  const [dbSizeGB, setDbSizeGB] = useState(10);
  const [branchCount, setBranchCount] = useState(3);

  // Total estimate state
  const [sessionsPerMonth, setSessionsPerMonth] = useState(100);

  // Token cost calculation
  const tokenCost = useMemo(() => {
    if (!modelData) return null;
    const model = modelData.models.find((m) => m.id === selectedModel);
    if (!model) return null;

    const overheadInput = (modelData.tool_overhead_tokens + modelData.system_prompt_overhead) / 1_000_000;
    const callInput = (modelData.avg_input_per_call * toolCalls) / 1_000_000;
    const callOutput = (modelData.avg_output_per_call * toolCalls) / 1_000_000;

    const totalInput = overheadInput + callInput;
    const totalOutput = callOutput;

    const inputCost = totalInput * model.input_per_mtok;
    const outputCost = totalOutput * model.output_per_mtok;
    const sessionCost = inputCost + outputCost;

    return {
      model,
      overheadTokens: modelData.tool_overhead_tokens + modelData.system_prompt_overhead,
      totalInputTokens: Math.round(totalInput * 1_000_000),
      totalOutputTokens: Math.round(totalOutput * 1_000_000),
      inputCost,
      outputCost,
      sessionCost,
    };
  }, [modelData, selectedModel, toolCalls]);

  // Compute cost calculation
  const computeCost = useMemo(() => {
    if (!computeData) return null;
    const region = computeData.regions.find((r) => r.id === selectedRegion);
    const cu = computeData.compute_units.find((c) => c.cu === selectedCU);
    if (!region || !cu) return null;

    const hours = usagePattern === 'always-on' ? 24 : hoursPerDay;
    const monthlyCost = cu.dbu_per_hour * region.dbu_rate * hours * 30;
    return { monthlyCost, dbuRate: region.dbu_rate, dbuPerHour: cu.dbu_per_hour, hours };
  }, [computeData, selectedCU, selectedRegion, usagePattern, hoursPerDay]);

  // Storage cost calculation
  const storageCost = useMemo(() => {
    if (!computeData) return null;
    return dbSizeGB * computeData.storage_per_gb_month;
  }, [computeData, dbSizeGB]);

  // Total monthly estimate
  const totalMonthly = useMemo(() => {
    if (!tokenCost || !computeCost || storageCost === null) return null;
    const tokenTotal = tokenCost.sessionCost * sessionsPerMonth;
    const compute = computeCost.monthlyCost;
    const storage = storageCost;
    return { tokenTotal, compute, storage, total: tokenTotal + compute + storage };
  }, [tokenCost, computeCost, storageCost, sessionsPerMonth]);

  if (modelLoading || computeLoading || comparisonLoading) {
    return <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>;
  }
  if (modelError) {
    return <Alert severity="error">{modelError}</Alert>;
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>Pricing Calculator</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 4, maxWidth: 700 }}>
        Estimate costs for running the Lakebase MCP Server — including Claude API tokens,
        Lakebase compute, and storage. Compare with Snowflake and Teradata.
      </Typography>

      <motion.div variants={containerVariants} initial="initial" animate="animate">

        {/* Section A: Token Cost Calculator */}
        <motion.div variants={itemVariants}>
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>Token Cost Calculator</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Each MCP tool call consumes Claude API tokens. 31 tools add ~6,000 tokens of overhead per request.
              </Typography>

              <Grid container spacing={3}>
                <Grid item xs={12} sm={4}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Claude Model</InputLabel>
                    <Select
                      value={selectedModel}
                      label="Claude Model"
                      onChange={(e) => setSelectedModel(e.target.value)}
                    >
                      {modelData?.models.map((m) => (
                        <MenuItem key={m.id} value={m.id}>
                          {m.name} (${m.input_per_mtok}/MTok in)
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} sm={4}>
                  <Typography variant="body2" gutterBottom>
                    Tool calls per session: <strong>{toolCalls}</strong>
                  </Typography>
                  <Slider
                    value={toolCalls}
                    onChange={(_, v) => setToolCalls(v)}
                    min={1}
                    max={30}
                    marks={[{ value: 1, label: '1' }, { value: 10, label: '10' }, { value: 30, label: '30' }]}
                    valueLabelDisplay="auto"
                  />
                </Grid>
                <Grid item xs={12} sm={4}>
                  {tokenCost && (
                    <Paper sx={{ p: 2, bgcolor: 'grey.50', textAlign: 'center' }}>
                      <Typography variant="body2" color="text.secondary">Session Cost</Typography>
                      <Typography variant="h4" sx={{ fontWeight: 700, color: 'primary.main' }}>
                        {formatUSD(tokenCost.sessionCost)}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {tokenCost.totalInputTokens.toLocaleString()} in + {tokenCost.totalOutputTokens.toLocaleString()} out tokens
                      </Typography>
                    </Paper>
                  )}
                </Grid>
              </Grid>

              {selectedModel === 'claude-opus-4-6' && (
                <Alert severity="info" sx={{ mt: 2 }}>
                  Switch to <strong>Sonnet 4.6</strong> for 40% savings on token costs — recommended for routine MCP operations.
                </Alert>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Section B: Compute Cost Estimator */}
        <motion.div variants={itemVariants}>
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>Compute Cost Estimator</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Lakebase compute is billed per DBU (Databricks Unit) based on CU size and region.
              </Typography>

              <Grid container spacing={3}>
                <Grid item xs={12} sm={3}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Compute Size (CU)</InputLabel>
                    <Select
                      value={selectedCU}
                      label="Compute Size (CU)"
                      onChange={(e) => setSelectedCU(e.target.value)}
                    >
                      {computeData?.compute_units.map((c) => (
                        <MenuItem key={c.cu} value={c.cu}>
                          {c.cu} CU ({c.ram_gb} GB RAM)
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} sm={3}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Region</InputLabel>
                    <Select
                      value={selectedRegion}
                      label="Region"
                      onChange={(e) => setSelectedRegion(e.target.value)}
                    >
                      {computeData?.regions.map((r) => (
                        <MenuItem key={r.id} value={r.id}>
                          {r.name} (${r.dbu_rate}/DBU)
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} sm={3}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Usage Pattern</InputLabel>
                    <Select
                      value={usagePattern}
                      label="Usage Pattern"
                      onChange={(e) => setUsagePattern(e.target.value)}
                    >
                      <MenuItem value="scale-to-zero">Scale-to-Zero</MenuItem>
                      <MenuItem value="always-on">Always On (24/7)</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} sm={3}>
                  {computeCost && (
                    <Paper sx={{ p: 2, bgcolor: 'grey.50', textAlign: 'center' }}>
                      <Typography variant="body2" color="text.secondary">Monthly Compute</Typography>
                      <Typography variant="h4" sx={{ fontWeight: 700, color: 'secondary.main' }}>
                        {formatUSD(computeCost.monthlyCost)}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {computeCost.dbuPerHour} DBU/hr x ${computeCost.dbuRate}/DBU x {computeCost.hours}h/day
                      </Typography>
                    </Paper>
                  )}
                </Grid>
              </Grid>

              {usagePattern === 'scale-to-zero' && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="body2" gutterBottom>
                    Active hours per day: <strong>{hoursPerDay}</strong>
                  </Typography>
                  <Slider
                    value={hoursPerDay}
                    onChange={(_, v) => setHoursPerDay(v)}
                    min={1}
                    max={24}
                    marks={[{ value: 1, label: '1h' }, { value: 8, label: '8h' }, { value: 24, label: '24h' }]}
                    valueLabelDisplay="auto"
                  />
                </Box>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Section C: Storage Cost Estimator */}
        <motion.div variants={itemVariants}>
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>Storage Cost Estimator</Typography>
              <Grid container spacing={3} alignItems="center">
                <Grid item xs={12} sm={3}>
                  <TextField
                    label="Database Size (GB)"
                    type="number"
                    size="small"
                    fullWidth
                    value={dbSizeGB}
                    onChange={(e) => setDbSizeGB(Math.max(0, Number(e.target.value)))}
                    inputProps={{ min: 0 }}
                  />
                </Grid>
                <Grid item xs={12} sm={3}>
                  <TextField
                    label="Branch Count"
                    type="number"
                    size="small"
                    fullWidth
                    value={branchCount}
                    onChange={(e) => setBranchCount(Math.max(0, Number(e.target.value)))}
                    inputProps={{ min: 0 }}
                  />
                </Grid>
                <Grid item xs={12} sm={3}>
                  {storageCost !== null && (
                    <Paper sx={{ p: 2, bgcolor: 'grey.50', textAlign: 'center' }}>
                      <Typography variant="body2" color="text.secondary">Monthly Storage</Typography>
                      <Typography variant="h4" sx={{ fontWeight: 700, color: 'success.main' }}>
                        {formatUSD(storageCost)}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {dbSizeGB} GB x ${computeData?.storage_per_gb_month}/GB/mo
                      </Typography>
                    </Paper>
                  )}
                </Grid>
                <Grid item xs={12} sm={3}>
                  <Alert severity="success" variant="outlined" sx={{ fontSize: '0.8rem' }}>
                    Branches are free! Copy-on-write storage means {branchCount} branches add no extra cost.
                  </Alert>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </motion.div>

        {/* Section D: Total Monthly Estimate */}
        <motion.div variants={itemVariants}>
          <Paper sx={{ p: 3, mb: 3, bgcolor: 'secondary.main', color: 'white' }}>
            <Grid container spacing={3} alignItems="center">
              <Grid item xs={12} sm={3}>
                <Typography variant="h6">Total Monthly Estimate</Typography>
                <TextField
                  label="Sessions / month"
                  type="number"
                  size="small"
                  value={sessionsPerMonth}
                  onChange={(e) => setSessionsPerMonth(Math.max(1, Number(e.target.value)))}
                  inputProps={{ min: 1 }}
                  sx={{
                    mt: 1,
                    '& .MuiInputBase-root': { bgcolor: 'white' },
                    '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
                  }}
                />
              </Grid>
              {totalMonthly && (
                <>
                  <Grid item xs={6} sm={2}>
                    <Typography variant="body2" sx={{ opacity: 0.7 }}>Tokens</Typography>
                    <Typography variant="h5" sx={{ fontWeight: 700 }}>
                      {formatUSD(totalMonthly.tokenTotal)}
                    </Typography>
                  </Grid>
                  <Grid item xs={6} sm={2}>
                    <Typography variant="body2" sx={{ opacity: 0.7 }}>Compute</Typography>
                    <Typography variant="h5" sx={{ fontWeight: 700 }}>
                      {formatUSD(totalMonthly.compute)}
                    </Typography>
                  </Grid>
                  <Grid item xs={6} sm={2}>
                    <Typography variant="body2" sx={{ opacity: 0.7 }}>Storage</Typography>
                    <Typography variant="h5" sx={{ fontWeight: 700 }}>
                      {formatUSD(totalMonthly.storage)}
                    </Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" sx={{ opacity: 0.7 }}>Total</Typography>
                    <Typography variant="h3" sx={{ fontWeight: 700 }}>
                      {formatUSD(totalMonthly.total)}
                    </Typography>
                    <Typography variant="caption" sx={{ opacity: 0.7 }}>/month</Typography>
                  </Grid>
                </>
              )}
            </Grid>
          </Paper>
        </motion.div>

        {/* Section E: Competitive Comparison */}
        <motion.div variants={itemVariants}>
          <Typography variant="h6" gutterBottom>Competitive Comparison</Typography>
          <Grid container spacing={3} sx={{ mb: 3 }}>
            {comparisonData?.platforms.map((platform) => (
              <Grid item xs={12} md={4} key={platform.name}>
                <Card
                  variant="outlined"
                  sx={{
                    height: '100%',
                    ...(platform.name === 'Lakebase' && {
                      borderColor: 'primary.main',
                      borderWidth: 2,
                    }),
                  }}
                >
                  <CardContent>
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                      <Typography variant="h6" sx={{ fontWeight: 700 }}>
                        {platform.name}
                      </Typography>
                      {platform.name === 'Lakebase' && (
                        <Chip label="Recommended" color="primary" size="small" />
                      )}
                    </Stack>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      {platform.provider}
                    </Typography>

                    <Divider sx={{ my: 1.5 }} />

                    <TableContainer>
                      <Table size="small">
                        <TableBody>
                          <TableRow>
                            <TableCell sx={{ pl: 0, border: 0 }}>Min compute/hr</TableCell>
                            <TableCell align="right" sx={{ border: 0, fontWeight: 600 }}>
                              {formatUSD(platform.min_compute_hr)}
                            </TableCell>
                          </TableRow>
                          <TableRow>
                            <TableCell sx={{ pl: 0, border: 0 }}>8-call session</TableCell>
                            <TableCell align="right" sx={{ border: 0, fontWeight: 600 }}>
                              {formatUSD(platform.session_cost_8_calls)}
                            </TableCell>
                          </TableRow>
                          <TableRow>
                            <TableCell sx={{ pl: 0, border: 0 }}>Monthly (prod)</TableCell>
                            <TableCell align="right" sx={{ border: 0, fontWeight: 600 }}>
                              {formatUSD(platform.monthly_prod)}
                            </TableCell>
                          </TableRow>
                          <TableRow>
                            <TableCell sx={{ pl: 0, border: 0 }}>MCP Tools</TableCell>
                            <TableCell align="right" sx={{ border: 0, fontWeight: 600 }}>
                              {platform.mcp_tools}
                            </TableCell>
                          </TableRow>
                          <TableRow>
                            <TableCell sx={{ pl: 0, border: 0 }}>Governance</TableCell>
                            <TableCell align="right" sx={{ border: 0, fontWeight: 600 }}>
                              {platform.governance_layers} layer{platform.governance_layers > 1 ? 's' : ''}
                            </TableCell>
                          </TableRow>
                          <TableRow>
                            <TableCell sx={{ pl: 0, border: 0 }}>Branching</TableCell>
                            <TableCell align="right" sx={{ border: 0, fontWeight: 600, fontSize: '0.75rem' }}>
                              {platform.branching}
                            </TableCell>
                          </TableRow>
                          <TableRow>
                            <TableCell sx={{ pl: 0, border: 0 }}>Scale-to-Zero</TableCell>
                            <TableCell align="right" sx={{ border: 0 }}>
                              {platform.scale_to_zero ? (
                                <CheckCircle sx={{ color: 'success.main', fontSize: 18 }} />
                              ) : (
                                <Cancel sx={{ color: 'error.main', fontSize: 18 }} />
                              )}
                            </TableCell>
                          </TableRow>
                        </TableBody>
                      </Table>
                    </TableContainer>

                    <Divider sx={{ my: 1.5 }} />

                    <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                      {platform.highlights.map((h) => (
                        <Chip
                          key={h}
                          label={h}
                          size="small"
                          variant="outlined"
                          sx={{ fontSize: '0.7rem', mb: 0.5 }}
                        />
                      ))}
                    </Stack>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </motion.div>

        {/* Section F: Cost Optimization Tips */}
        <motion.div variants={itemVariants}>
          <Alert severity="info" icon={<TipIcon />} sx={{ mb: 3 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
              Cost Optimization Tips
            </Typography>
            <Stack spacing={0.5}>
              <Typography variant="body2">
                Use <strong>Sonnet 4.6</strong> instead of Opus for routine operations — 40% savings on token costs
              </Typography>
              <Typography variant="body2">
                Enable <strong>prompt caching</strong> — 90% savings on tool definition tokens (cache hits: $0.30/MTok vs $3.00/MTok)
              </Typography>
              <Typography variant="body2">
                Use <strong>scale-to-zero</strong> for dev/test branches — pay only for active hours
              </Typography>
              <Typography variant="body2">
                Use <strong>Batch API</strong> for non-interactive operations — 50% discount on token costs
              </Typography>
            </Stack>
          </Alert>
        </motion.div>

      </motion.div>
    </Box>
  );
}
