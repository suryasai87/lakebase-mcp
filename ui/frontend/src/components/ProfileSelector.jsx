import { FormControl, InputLabel, Select, MenuItem, Typography, Box } from '@mui/material';

const PROFILE_DESCRIPTIONS = {
  read_only: 'SELECT, SHOW, DESCRIBE, EXPLAIN only. Read-only tool access.',
  analyst: 'Read-only tools + INSERT and SET for data analysis workflows.',
  developer: 'Full read/write tools including branches, compute, migrations, and DDL.',
  admin: 'All 17 SQL types and all 31 tools. Unrestricted access.',
};

export default function ProfileSelector({ value, onChange, label = 'Governance Profile' }) {
  return (
    <Box>
      <FormControl fullWidth size="small">
        <InputLabel>{label}</InputLabel>
        <Select value={value} label={label} onChange={(e) => onChange(e.target.value)}>
          {Object.entries(PROFILE_DESCRIPTIONS).map(([key, desc]) => (
            <MenuItem key={key} value={key}>
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {key}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {desc}
                </Typography>
              </Box>
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    </Box>
  );
}
