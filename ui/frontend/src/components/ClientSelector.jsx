import { FormControl, InputLabel, Select, MenuItem } from '@mui/material';
import CLIENT_CONFIGS from '../data/clientConfigs';

export default function ClientSelector({ value, onChange }) {
  return (
    <FormControl fullWidth size="small">
      <InputLabel>MCP Client</InputLabel>
      <Select value={value} label="MCP Client" onChange={(e) => onChange(e.target.value)}>
        {Object.entries(CLIENT_CONFIGS).map(([key, cfg]) => (
          <MenuItem key={key} value={key}>
            {cfg.label}
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
}
