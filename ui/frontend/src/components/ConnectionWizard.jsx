import { useState } from 'react';
import {
  Stepper, Step, StepLabel, Button, Box, Typography, TextField, List,
  ListItem, ListItemIcon, ListItemText, Stack, Alert,
} from '@mui/material';
import { LooksOne, LooksTwo, Looks3 } from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';
import ProfileSelector from './ProfileSelector';
import ClientSelector from './ClientSelector';
import ConfigSnippet from './ConfigSnippet';
import CLIENT_CONFIGS from '../data/clientConfigs';

const STEPS = ['Choose Profile', 'Choose Client', 'Configure & Connect'];

const stepVariants = {
  initial: { opacity: 0, x: 40 },
  animate: { opacity: 1, x: 0, transition: { duration: 0.3 } },
  exit: { opacity: 0, x: -40, transition: { duration: 0.15 } },
};

export default function ConnectionWizard() {
  const [activeStep, setActiveStep] = useState(0);
  const [profile, setProfile] = useState('read_only');
  const [client, setClient] = useState('claude_code');
  const [serverUrl, setServerUrl] = useState('http://localhost:8000/mcp');

  const clientConfig = CLIENT_CONFIGS[client];
  const configCode = clientConfig?.template(serverUrl) || '';

  const envSnippet = `# Required
export LAKEBASE_COMPUTE_ENDPOINT="your-lakebase-host:5432"

# Governance (optional)
export LAKEBASE_SQL_PROFILE="${profile}"
export LAKEBASE_TOOL_PROFILE="${profile}"`;

  return (
    <Box>
      <Stepper activeStep={activeStep} alternativeLabel sx={{ mb: 4 }}>
        {STEPS.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      <AnimatePresence mode="wait">
        {activeStep === 0 && (
          <motion.div key="step-0" variants={stepVariants} initial="initial" animate="animate" exit="exit">
            <Typography variant="h6" gutterBottom>
              Select a Governance Profile
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Choose the access level for the MCP connection. This determines which
              tools and SQL statement types are available.
            </Typography>
            <ProfileSelector value={profile} onChange={setProfile} />
          </motion.div>
        )}

        {activeStep === 1 && (
          <motion.div key="step-1" variants={stepVariants} initial="initial" animate="animate" exit="exit">
            <Typography variant="h6" gutterBottom>
              Select your MCP Client
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Choose the AI tool you want to connect to the Lakebase MCP Server.
            </Typography>
            <ClientSelector value={client} onChange={setClient} />
            {clientConfig && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Setup Instructions:
                </Typography>
                <List dense>
                  {clientConfig.instructions.map((step, i) => (
                    <ListItem key={i}>
                      <ListItemIcon sx={{ minWidth: 32 }}>
                        {i === 0 ? <LooksOne fontSize="small" /> : i === 1 ? <LooksTwo fontSize="small" /> : <Looks3 fontSize="small" />}
                      </ListItemIcon>
                      <ListItemText primary={step} />
                    </ListItem>
                  ))}
                </List>
              </Box>
            )}
          </motion.div>
        )}

        {activeStep === 2 && (
          <motion.div key="step-2" variants={stepVariants} initial="initial" animate="animate" exit="exit">
            <Typography variant="h6" gutterBottom>
              Configure & Connect
            </Typography>
            <TextField
              fullWidth
              size="small"
              label="MCP Server URL"
              value={serverUrl}
              onChange={(e) => setServerUrl(e.target.value)}
              sx={{ mb: 3 }}
            />

            <Typography variant="subtitle2" gutterBottom>
              Client Configuration ({clientConfig?.filename}):
            </Typography>
            <ConfigSnippet code={configCode} filename={clientConfig?.filename} />

            <Typography variant="subtitle2" sx={{ mt: 3, mb: 1 }}>
              Environment Variables:
            </Typography>
            <ConfigSnippet code={envSnippet} filename=".env" />

            <Alert severity="info" sx={{ mt: 2 }}>
              Start the MCP server with: <code>python -m server.main</code> then connect your client.
            </Alert>
          </motion.div>
        )}
      </AnimatePresence>

      <Stack direction="row" spacing={2} sx={{ mt: 3, justifyContent: 'flex-end' }}>
        <Button
          disabled={activeStep === 0}
          onClick={() => setActiveStep((s) => s - 1)}
        >
          Back
        </Button>
        {activeStep < STEPS.length - 1 && (
          <Button
            variant="contained"
            onClick={() => setActiveStep((s) => s + 1)}
          >
            Next
          </Button>
        )}
      </Stack>
    </Box>
  );
}
