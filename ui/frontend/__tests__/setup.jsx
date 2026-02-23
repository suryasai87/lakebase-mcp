import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock framer-motion to avoid animation timing issues in tests
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }) => {
      const { initial, animate, exit, variants, whileHover, whileTap, transition, ...rest } = props;
      return <div {...rest}>{children}</div>;
    },
    tr: ({ children, ...props }) => {
      const { initial, animate, exit, variants, transition, style, ...rest } = props;
      return <tr style={style} {...rest}>{children}</tr>;
    },
  },
  AnimatePresence: ({ children }) => <>{children}</>,
}));

// Mock fetch for API calls
global.fetch = vi.fn(() =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve({}),
  })
);
