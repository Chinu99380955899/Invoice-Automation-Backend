import { Routes, Route, Navigate } from 'react-router-dom';
import { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';

import AppLayout from './components/layout/AppLayout.jsx';
import ProtectedRoute from './components/common/ProtectedRoute.jsx';
import Login from './pages/Login.jsx';
import Dashboard from './pages/Dashboard.jsx';
import InvoiceList from './pages/InvoiceList.jsx';
import InvoiceDetail from './pages/InvoiceDetail.jsx';
import ReviewQueue from './pages/ReviewQueue.jsx';
import NotFound from './pages/NotFound.jsx';
import { loadSession } from './store/slices/authSlice.js';

export default function App() {
  const dispatch = useDispatch();
  const { initialized } = useSelector((s) => s.auth);

  useEffect(() => {
    dispatch(loadSession());
  }, [dispatch]);

  if (!initialized) {
    return (
      <div className="app-loading">
        <div className="spinner" aria-label="Loading" />
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/invoices" element={<InvoiceList />} />
        <Route path="/invoices/:id" element={<InvoiceDetail />} />
        <Route path="/review" element={<ReviewQueue />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
