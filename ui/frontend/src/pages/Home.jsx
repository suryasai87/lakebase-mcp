import { useNavigate } from 'react-router-dom';
import {
  Typography, Grid, Card, CardContent, CardActionArea, Box, Stack,
} from '@mui/material';
import {
  Build as ToolsIcon, Cable as ConnectIcon, Security as GovernanceIcon,
  Storage as StorageIcon, MonetizationOn as PricingIcon,
} from '@mui/icons-material';
import { motion } from 'framer-motion';

const stats = [
  { label: 'Tools', value: 31, icon: <ToolsIcon />, color: '#FF3621' },
  { label: 'Categories', value: 14, icon: <StorageIcon />, color: '#1B3A4B' },
  { label: 'Profiles', value: 4, icon: <GovernanceIcon />, color: '#4CAF50' },
  { label: 'Prompts', value: 4, icon: <ConnectIcon />, color: '#FF9800' },
];

const quickLinks = [
  { label: 'Explore Tools', desc: 'Browse 31 tools across 14 categories', path: '/tools', icon: <ToolsIcon /> },
  { label: 'Connect', desc: 'Set up MCP client connection', path: '/connect', icon: <ConnectIcon /> },
  { label: 'Governance', desc: 'View access control matrices', path: '/governance', icon: <GovernanceIcon /> },
  { label: 'Pricing', desc: 'Estimate MCP, compute, and storage costs', path: '/pricing', icon: <PricingIcon /> },
];

const containerVariants = {
  animate: { transition: { staggerChildren: 0.08 } },
};

const itemVariants = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

export default function Home() {
  const navigate = useNavigate();

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Lakebase MCP Server
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 4, maxWidth: 700 }}>
        Model Context Protocol server for Databricks Lakebase (PostgreSQL).
        Explore tools, configure connections, and manage governance profiles
        for AI agent access to your database.
      </Typography>

      <motion.div variants={containerVariants} initial="initial" animate="animate">
        <Grid container spacing={2} sx={{ mb: 4 }}>
          {stats.map((s) => (
            <Grid item xs={6} sm={3} key={s.label}>
              <motion.div variants={itemVariants}>
                <Card>
                  <CardContent sx={{ textAlign: 'center', py: 3 }}>
                    <Box sx={{ color: s.color, mb: 1 }}>{s.icon}</Box>
                    <Typography variant="h3" sx={{ fontWeight: 700, color: s.color }}>
                      {s.value}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {s.label}
                    </Typography>
                  </CardContent>
                </Card>
              </motion.div>
            </Grid>
          ))}
        </Grid>

        <Typography variant="h5" gutterBottom>
          Quick Links
        </Typography>
        <Grid container spacing={2}>
          {quickLinks.map((link) => (
            <Grid item xs={12} sm={4} key={link.path}>
              <motion.div variants={itemVariants}>
                <Card>
                  <CardActionArea onClick={() => navigate(link.path)} sx={{ p: 2 }}>
                    <Stack direction="row" spacing={2} alignItems="center">
                      <Box sx={{ color: 'primary.main' }}>{link.icon}</Box>
                      <Box>
                        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                          {link.label}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {link.desc}
                        </Typography>
                      </Box>
                    </Stack>
                  </CardActionArea>
                </Card>
              </motion.div>
            </Grid>
          ))}
        </Grid>
      </motion.div>
    </Box>
  );
}
