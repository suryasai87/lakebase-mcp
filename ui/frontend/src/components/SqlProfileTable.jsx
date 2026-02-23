import {
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper,
} from '@mui/material';
import { CheckCircle, Cancel } from '@mui/icons-material';

const PROFILES = ['read_only', 'analyst', 'developer', 'admin'];

export default function SqlProfileTable({ data }) {
  if (!data) return null;
  const { types, profiles } = data;

  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow sx={{ bgcolor: 'grey.50' }}>
            <TableCell sx={{ fontWeight: 700, width: 180 }}>SQL Type</TableCell>
            {PROFILES.map((p) => (
              <TableCell key={p} align="center" sx={{ fontWeight: 700, textTransform: 'capitalize' }}>
                {p.replace('_', ' ')}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {types.map((sqlType) => (
            <TableRow key={sqlType} hover>
              <TableCell sx={{ fontFamily: 'monospace', textTransform: 'uppercase', fontWeight: 500 }}>
                {sqlType}
              </TableCell>
              {PROFILES.map((profile) => {
                const allowed = profiles[profile]?.[sqlType];
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
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
