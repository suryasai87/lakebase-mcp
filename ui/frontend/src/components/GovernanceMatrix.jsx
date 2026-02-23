import React from 'react';
import {
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, Chip, Box,
} from '@mui/material';
import { CheckCircle, Cancel } from '@mui/icons-material';
import { motion } from 'framer-motion';

const PROFILES = ['read_only', 'analyst', 'developer', 'admin'];

export default function GovernanceMatrix({ matrix, categories }) {
  if (!matrix || !categories) return null;

  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow sx={{ bgcolor: 'grey.50' }}>
            <TableCell sx={{ fontWeight: 700, width: 260 }}>Tool</TableCell>
            {PROFILES.map((p) => (
              <TableCell key={p} align="center" sx={{ fontWeight: 700, textTransform: 'capitalize' }}>
                {p.replace('_', ' ')}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {categories.map((cat) => (
            <React.Fragment key={cat.name}>
              <TableRow sx={{ bgcolor: 'grey.100' }}>
                <TableCell colSpan={5} sx={{ fontWeight: 600 }}>
                  <Box component="span" sx={{ fontWeight: 600, fontSize: '0.875rem' }}>
                    {cat.name}
                    <Chip
                      label={cat.tool_count}
                      size="small"
                      sx={{ ml: 1, height: 18, fontSize: '0.7rem' }}
                    />
                  </Box>
                </TableCell>
              </TableRow>
              {cat.tools.map((toolName, idx) => (
                <motion.tr
                  key={toolName}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: idx * 0.02 }}
                  style={{ display: 'table-row' }}
                >
                  <TableCell sx={{ pl: 4, fontFamily: 'monospace', fontSize: '0.8rem' }}>
                    {toolName}
                  </TableCell>
                  {PROFILES.map((profile) => {
                    const allowed = matrix[profile]?.[toolName];
                    return (
                      <TableCell key={profile} align="center">
                        {allowed ? (
                          <CheckCircle sx={{ color: 'success.main', fontSize: 18 }} />
                        ) : (
                          <Cancel sx={{ color: 'error.main', fontSize: 18 }} />
                        )}
                      </TableCell>
                    );
                  })}
                </motion.tr>
              ))}
            </React.Fragment>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
