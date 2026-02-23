import { Typography, Box, Paper } from '@mui/material';
import ConnectionWizard from '../components/ConnectionWizard';

export default function ConnectionSetup() {
  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Connect to Lakebase MCP
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Follow the steps below to connect your AI tool to the Lakebase MCP Server.
      </Typography>
      <Paper sx={{ p: 3 }}>
        <ConnectionWizard />
      </Paper>
    </Box>
  );
}
