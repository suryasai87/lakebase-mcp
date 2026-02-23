import { useState } from 'react';
import {
  Card, CardContent, Typography, Chip, Stack, Collapse,
  Table, TableBody, TableRow, TableCell, TableHead, IconButton, Box,
} from '@mui/material';
import { ExpandMore as ExpandIcon } from '@mui/icons-material';
import { motion } from 'framer-motion';

export default function ToolCard({ tool }) {
  const [expanded, setExpanded] = useState(false);
  const params = tool.parameters || {};
  const paramEntries = Object.entries(params);

  return (
    <motion.div whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.99 }}>
      <Card sx={{ mb: 1.5 }}>
        <CardContent sx={{ pb: expanded ? 2 : '12px !important' }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
            <Box sx={{ flex: 1 }}>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
                <Typography variant="subtitle2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                  {tool.name}
                </Typography>
                <Chip
                  label={tool.category}
                  size="small"
                  variant="outlined"
                  sx={{ fontSize: '0.7rem', height: 20 }}
                />
                {tool.readOnlyHint && (
                  <Chip label="Read Only" size="small" color="success" sx={{ fontSize: '0.7rem', height: 20 }} />
                )}
                {tool.destructiveHint && (
                  <Chip label="Destructive" size="small" color="error" sx={{ fontSize: '0.7rem', height: 20 }} />
                )}
                {!tool.readOnlyHint && !tool.destructiveHint && (
                  <Chip label="Read/Write" size="small" color="warning" sx={{ fontSize: '0.7rem', height: 20 }} />
                )}
              </Stack>
              <Typography variant="body2" color="text.secondary">
                {tool.description}
              </Typography>
            </Box>
            {paramEntries.length > 0 && (
              <IconButton
                size="small"
                onClick={() => setExpanded(!expanded)}
                sx={{
                  transform: expanded ? 'rotate(180deg)' : 'none',
                  transition: 'transform 0.2s',
                }}
              >
                <ExpandIcon />
              </IconButton>
            )}
          </Box>
          <Collapse in={expanded}>
            <Table size="small" sx={{ mt: 1 }}>
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600, py: 0.5 }}>Parameter</TableCell>
                  <TableCell sx={{ fontWeight: 600, py: 0.5 }}>Type</TableCell>
                  <TableCell sx={{ fontWeight: 600, py: 0.5 }}>Required</TableCell>
                  <TableCell sx={{ fontWeight: 600, py: 0.5 }}>Description</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {paramEntries.map(([name, info]) => (
                  <TableRow key={name}>
                    <TableCell sx={{ py: 0.5, fontFamily: 'monospace', fontSize: '0.8rem' }}>
                      {name}
                    </TableCell>
                    <TableCell sx={{ py: 0.5 }}>{info.type}</TableCell>
                    <TableCell sx={{ py: 0.5 }}>
                      {info.required ? 'Yes' : `No (default: ${info.default ?? '—'})`}
                    </TableCell>
                    <TableCell sx={{ py: 0.5 }}>{info.description || ''}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Collapse>
        </CardContent>
      </Card>
    </motion.div>
  );
}
