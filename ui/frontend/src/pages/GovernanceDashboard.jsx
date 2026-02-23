import { Typography, Box, CircularProgress, Alert, Accordion, AccordionSummary, AccordionDetails } from '@mui/material';
import { ExpandMore as ExpandMoreIcon } from '@mui/icons-material';
import useApi from '../hooks/useApi';
import GovernanceMatrix from '../components/GovernanceMatrix';
import SqlProfileTable from '../components/SqlProfileTable';

export default function GovernanceDashboard() {
  const { data: matrix, loading: matrixLoading, error: matrixError } = useApi('/governance/matrix');
  const { data: sqlData, loading: sqlLoading } = useApi('/governance/sql-matrix');
  const { data: catsData, loading: catsLoading } = useApi('/categories');
  const { data: envData } = useApi('/config/env-vars');

  if (matrixLoading || sqlLoading || catsLoading) {
    return <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>;
  }
  if (matrixError) {
    return <Alert severity="error">{matrixError}</Alert>;
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Governance Dashboard
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Dual-layer governance: Tool access control (Layer 1) + SQL statement governance (Layer 2).
        Both layers must pass for execution to proceed.
      </Typography>

      <Typography variant="h5" gutterBottom>
        Tool Access Matrix
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Shows which tools are accessible under each governance profile. 31 tools x 4 profiles.
      </Typography>
      <GovernanceMatrix matrix={matrix} categories={catsData?.categories} />

      <Typography variant="h5" sx={{ mt: 4 }} gutterBottom>
        SQL Statement Permissions
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Shows which SQL statement types are allowed per profile. 17 types x 4 profiles.
      </Typography>
      <SqlProfileTable data={sqlData} />

      {envData && (
        <Accordion sx={{ mt: 4 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="h6">Environment Variables Reference</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Box component="table" sx={{ width: '100%', borderCollapse: 'collapse', '& td, & th': { p: 1, borderBottom: '1px solid', borderColor: 'divider', textAlign: 'left' } }}>
              <thead>
                <tr>
                  <th>Variable</th>
                  <th>Description</th>
                  <th>Default</th>
                  <th>Required</th>
                </tr>
              </thead>
              <tbody>
                {envData.variables.map((v) => (
                  <tr key={v.name}>
                    <td><code>{v.name}</code></td>
                    <td>{v.description}</td>
                    <td>{v.default || '—'}</td>
                    <td>{v.required ? 'Yes' : 'No'}</td>
                  </tr>
                ))}
              </tbody>
            </Box>
          </AccordionDetails>
        </Accordion>
      )}
    </Box>
  );
}
