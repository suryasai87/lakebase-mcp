import { Routes, Route, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import Layout from './components/Layout';
import Home from './pages/Home';
import ToolExplorer from './pages/ToolExplorer';
import ConnectionSetup from './pages/ConnectionSetup';
import GovernanceDashboard from './pages/GovernanceDashboard';
import PricingCalculator from './pages/PricingCalculator';

const pageVariants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.3, ease: 'easeOut' } },
  exit: { opacity: 0, y: -12, transition: { duration: 0.15 } },
};

function AnimatedPage({ children }) {
  return (
    <motion.div
      variants={pageVariants}
      initial="initial"
      animate="animate"
      exit="exit"
    >
      {children}
    </motion.div>
  );
}

export default function App() {
  const location = useLocation();

  return (
    <Layout>
      <AnimatePresence mode="wait">
        <Routes location={location} key={location.pathname}>
          <Route
            path="/"
            element={<AnimatedPage><Home /></AnimatedPage>}
          />
          <Route
            path="/tools"
            element={<AnimatedPage><ToolExplorer /></AnimatedPage>}
          />
          <Route
            path="/connect"
            element={<AnimatedPage><ConnectionSetup /></AnimatedPage>}
          />
          <Route
            path="/governance"
            element={<AnimatedPage><GovernanceDashboard /></AnimatedPage>}
          />
          <Route
            path="/pricing"
            element={<AnimatedPage><PricingCalculator /></AnimatedPage>}
          />
        </Routes>
      </AnimatePresence>
    </Layout>
  );
}
