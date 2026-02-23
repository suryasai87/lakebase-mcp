import { useState } from 'react';
import { Paper, Box, Typography, IconButton, Tooltip } from '@mui/material';
import { ContentCopy as CopyIcon, Check as CheckIcon } from '@mui/icons-material';

export default function ConfigSnippet({ code, filename }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Paper
      variant="outlined"
      sx={{
        position: 'relative',
        bgcolor: '#1e1e2e',
        color: '#cdd6f4',
        borderRadius: 2,
        overflow: 'hidden',
      }}
    >
      {filename && (
        <Box sx={{ px: 2, py: 0.5, bgcolor: '#313244', borderBottom: '1px solid #45475a' }}>
          <Typography variant="caption" sx={{ fontFamily: 'monospace', color: '#a6adc8' }}>
            {filename}
          </Typography>
        </Box>
      )}
      <Box sx={{ position: 'absolute', top: filename ? 32 : 4, right: 4 }}>
        <Tooltip title={copied ? 'Copied!' : 'Copy to clipboard'}>
          <IconButton size="small" onClick={handleCopy} sx={{ color: '#a6adc8' }}>
            {copied ? <CheckIcon fontSize="small" /> : <CopyIcon fontSize="small" />}
          </IconButton>
        </Tooltip>
      </Box>
      <Box
        component="pre"
        sx={{
          p: 2,
          m: 0,
          fontSize: '0.82rem',
          lineHeight: 1.6,
          fontFamily: '"JetBrains Mono", "Fira Code", monospace',
          overflowX: 'auto',
          whiteSpace: 'pre',
        }}
      >
        {code}
      </Box>
    </Paper>
  );
}
