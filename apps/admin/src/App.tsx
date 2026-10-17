import type { JSX } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import { isAuthenticated } from './lib/auth';
import BulkImport from './pages/BulkImportExport';
import Dashboard from './pages/Dashboard';
import Embeddings from './pages/Embeddings';
import Fragrances from './pages/Fragrances';
import Login from './pages/Login';
import { AccordsPage, BrandsPage, FamiliesPage, NotesPage, OccasionsPage } from './pages/Lookups';
import PriceHistory from './pages/PriceHistory';
import PriceLogger from './pages/PriceLogger';
import Retailers from './pages/Retailers';
import Users from './pages/Users';

const Protected = ({ children }: { children: JSX.Element }) => (isAuthenticated() ? children : <Navigate to="/login" replace />);
const Public = ({ children }: { children: JSX.Element }) => (!isAuthenticated() ? children : <Navigate to="/" replace />);

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Public><Login /></Public>} />
        <Route path="/" element={<Protected><Layout /></Protected>}>
          <Route index element={<Dashboard />} />
          <Route path="fragrances" element={<Fragrances />} />
          <Route path="brands" element={<BrandsPage />} />
          <Route path="notes" element={<NotesPage />} />
          <Route path="families" element={<FamiliesPage />} />
          <Route path="accords" element={<AccordsPage />} />
          <Route path="occasions" element={<OccasionsPage />} />
          <Route path="embeddings" element={<Embeddings />} />
          <Route path="retailers" element={<Retailers />} />
          <Route path="price-logger" element={<PriceLogger />} />
          <Route path="prices" element={<PriceHistory />} />
          <Route path="bulk-import" element={<BulkImport />} />
          <Route path="users" element={<Users />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
