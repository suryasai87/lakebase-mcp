import { useState, useMemo } from 'react';
import { Typography, Box, CircularProgress, Alert } from '@mui/material';
import useApi from '../hooks/useApi';
import SearchBar from '../components/SearchBar';
import CategoryAccordion from '../components/CategoryAccordion';

export default function ToolExplorer() {
  const { data: toolsData, loading: toolsLoading, error: toolsError } = useApi('/tools');
  const { data: catsData, loading: catsLoading } = useApi('/categories');
  const [search, setSearch] = useState('');

  const filteredCategories = useMemo(() => {
    if (!catsData || !toolsData) return [];
    const tools = toolsData.tools || [];
    const query = search.toLowerCase();

    return (catsData.categories || [])
      .map((cat) => {
        const catTools = tools.filter((t) => t.category === cat.name);
        if (!query) return { ...cat, filteredTools: catTools };
        const matched = catTools.filter(
          (t) =>
            t.name.toLowerCase().includes(query) ||
            (t.title || '').toLowerCase().includes(query) ||
            (t.description || '').toLowerCase().includes(query) ||
            cat.name.toLowerCase().includes(query)
        );
        return { ...cat, filteredTools: matched };
      })
      .filter((cat) => cat.filteredTools.length > 0);
  }, [catsData, toolsData, search]);

  if (toolsLoading || catsLoading) {
    return <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>;
  }
  if (toolsError) {
    return <Alert severity="error">{toolsError}</Alert>;
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Tool Explorer
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {toolsData?.count || 0} tools across {catsData?.count || 0} categories.
        Expand a category to see tool details and parameters.
      </Typography>

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="Search tools by name, category, or description..."
      />

      {filteredCategories.map((cat) => (
        <CategoryAccordion
          key={cat.name}
          category={cat}
          tools={cat.filteredTools}
        />
      ))}

      {filteredCategories.length === 0 && search && (
        <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
          No tools match "{search}"
        </Typography>
      )}
    </Box>
  );
}
