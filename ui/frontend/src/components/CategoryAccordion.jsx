import {
  Accordion, AccordionSummary, AccordionDetails, Typography, Chip, Stack,
} from '@mui/material';
import { ExpandMore as ExpandMoreIcon } from '@mui/icons-material';
import ToolCard from './ToolCard';

export default function CategoryAccordion({ category, tools }) {
  return (
    <Accordion defaultExpanded={false} sx={{ mb: 1, '&:before': { display: 'none' } }}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
            {category.name}
          </Typography>
          <Chip
            label={`${category.tool_count} tools`}
            size="small"
            color="primary"
            variant="outlined"
            sx={{ fontSize: '0.75rem' }}
          />
          <Typography variant="body2" color="text.secondary">
            {category.description}
          </Typography>
        </Stack>
      </AccordionSummary>
      <AccordionDetails sx={{ pt: 0 }}>
        {tools.map((tool) => (
          <ToolCard key={tool.name} tool={tool} />
        ))}
      </AccordionDetails>
    </Accordion>
  );
}
